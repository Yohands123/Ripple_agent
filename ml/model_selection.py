"""Frozen seven-event nested LOEO selection among three model families."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from ml.evaluation import auc_intervals
from ml.features import NUMERIC
from ml.train import Encoder, PARAMETERS, SEED, bootstrap_intervals, calibration, distance_rule, evaluation_population, lgb, nested_rounds, score

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ("distance", "logistic_regression", "lightgbm")
PROBABILITY_COLUMNS = {"distance": "distanceProbability", "logistic_regression": "logisticProbability", "lightgbm": "lightgbmProbability"}


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def logit(value):
    value = np.clip(value, 1e-12, 1 - 1e-12)
    return np.log(value / (1 - value))


class FittedCandidate:
    def __init__(self, kind, training, rounds=None):
        if kind not in CANDIDATES:
            raise ValueError("Unregistered candidate")
        self.kind, self.training = kind, training
        self.training_events = sorted(training.eventId.unique())
        self.rounds, self.stopping_event = None, None
        if training.hit.nunique() != 2:
            raise ValueError("Both classes required in candidate training")
        if kind == "distance":
            return
        self.encoder = Encoder().fit(training)
        self.x = self.encoder.transform(training)
        if kind == "logistic_regression":
            self.model = make_pipeline(SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True), StandardScaler(),
                                       LogisticRegression(C=1., solver="lbfgs", max_iter=1500, random_state=SEED))
            self.model.fit(self.x, training.hit)
        else:
            if rounds is None:
                self.rounds, self.stopping_event = nested_rounds(training)
            else:
                self.rounds = rounds
            names = [f"f{i}" for i in range(self.x.shape[1])]
            self.model = lgb.train({**PARAMETERS, "seed": SEED}, lgb.Dataset(self.x, label=training.hit.to_numpy(), feature_name=names), num_boost_round=self.rounds)

    def predict(self, frame):
        if self.kind == "distance":
            return distance_rule(self.training.distance_km, self.training.hit, frame.distance_km)
        x = self.encoder.transform(frame)
        return self.model.predict_proba(x)[:, 1] if self.kind == "logistic_regression" else self.model.predict(x, num_threads=1)

    def explain(self, frame):
        """Exact raw-score decomposition for the selected full-training refit."""
        if self.kind == "distance":
            raw = logit(self.predict(frame))
            base = float(logit(self.predict(self.training)).mean())
            return np.full(len(frame), base), {"distance_km": raw - base}, raw, "Exact single-input SHAP on clipped log odds, using the empirical training-distance background"
        x = self.encoder.transform(frame)
        if self.kind == "lightgbm":
            values = self.model.predict(x, pred_contrib=True, num_threads=1)
            base, phi = values[:, -1], values[:, :-1]
            raw = self.model.predict(x, raw_score=True, num_threads=1)
            groups = self.encoder.groups
            method = "Native TreeSHAP for the selected full-training LightGBM refit"
        else:
            imputer, scaler, estimator = self.model.steps[0][1], self.model.steps[1][1], self.model.steps[2][1]
            transformed = scaler.transform(imputer.transform(x))
            background = scaler.transform(imputer.transform(self.x)).mean(axis=0)
            phi = (transformed - background) * estimator.coef_[0]
            base = np.full(len(frame), float(estimator.intercept_[0] + background @ estimator.coef_[0]))
            raw = self.model.decision_function(x)
            groups = self.encoder.groups + [self.encoder.groups[i] for i in imputer.indicator_.features_]
            method = "Exact interventional linear SHAP in log odds with training-mean transformed-feature background; correlated-feature effects are not conditional explanations"
        grouped = {name: phi[:, [j for j, group in enumerate(groups) if group == name]].sum(axis=1) for name in NUMERIC + ["part_type"]}
        assert np.allclose(base + sum(grouped.values()), raw, atol=1e-8)
        return base, grouped, raw, method


def choose_candidate(training, cache=None, fit_factory=FittedCandidate):
    """Only the six outer-training events are accepted; no outer labels exist here."""
    events = sorted(training.eventId.unique())
    if len(events) != 6:
        raise ValueError("The frozen inner loop requires exactly six training events")
    cache = {} if cache is None else cache
    inner = []
    for held_event in events:
        fit = training[training.eventId != held_event].reset_index(drop=True)
        validation = training[training.eventId == held_event].reset_index(drop=True)
        scores = {}
        for kind in CANDIDATES:
            key = (kind, tuple(sorted(fit.eventId.unique())))
            if key not in cache:
                cache[key] = fit_factory(kind, fit)
            model = cache[key]
            assert set(model.training_events) == set(fit.eventId.unique()) and held_event not in model.training_events
            scores[kind] = score(validation.hit, model.predict(validation))["auc"]
        inner.append({"heldOutEvent": held_event, "trainingEvents": sorted(fit.eventId.unique()), "auc": scores})
    means = {kind: float(np.mean([fold["auc"][kind] for fold in inner])) for kind in CANDIDATES}
    best = max(means.values())
    selected = next(kind for kind in CANDIDATES if best - means[kind] <= 1e-12)
    return selected, means, inner


def prediction_intervals(kind, training, prediction, point_model, members=200):
    rng = np.random.default_rng(SEED + sum("|".join(sorted(training.eventId.unique())).encode()))
    events = np.array(sorted(training.eventId.unique()))
    draws = []
    for i in range(members):
        sampled = rng.choice(events, len(events), replace=True)
        resampled = pd.concat([training[training.eventId == event] for event in sampled], ignore_index=True)
        model = FittedCandidate(kind, resampled, rounds=point_model.rounds)
        draws.append(model.predict(prediction))
        if (i + 1) % 50 == 0:
            print(f"{prediction.eventId.iloc[0]}: {i+1}/{members} {kind} uncertainty refits", flush=True)
    low, high = np.quantile(draws, [.025, .975], axis=0)
    point = point_model.predict(prediction)
    expanded = (point < low) | (point > high)
    return np.minimum(low, point), np.maximum(high, point), int(expanded.sum())


def write_selection_report(selection, candidate_rows, root=ROOT):
    folder = root / "data/review"
    (folder / "nested_model_selection.json").write_text(json.dumps(selection, indent=2) + "\n", encoding="utf-8")
    pd.DataFrame(candidate_rows).to_csv(folder / "nested_candidate_evaluation.csv", index=False)
    low, high = selection["nestedAuc95"]
    lines = ["## Model selection", "",
             "The protocol was committed before this new run in `data/sources/model_selection_protocol.json`; its SHA-256 is recorded in the freeze and selection artifacts. Candidates, features, labels, tie rule and model settings were fixed. Earlier baseline results had already been seen; no claim is made that all earlier analysis was prospectively preregistered.", "",
             "Exactly seven two-class events enter this procedure. For each outer test event, the other six form six inner leave-one-event-out folds. Each candidate trains on five events and is scored on the sixth. The highest arithmetic mean inner AUC wins, with ties resolved distance, logistic, then LightGBM. The winner is refit on all six and scored once on the held-out outer event. Both 2011 events are excluded from training and selection here, as specified in the new instructions.", "",
             "| Outer test event | Distance mean inner AUC | Logistic mean inner AUC | LightGBM mean inner AUC | Picked candidate | Outer AUC (95%) |",
             "|---|---:|---:|---:|---|---:|"]
    for fold in selection["outerFolds"]:
        means = fold["innerMeanAuc"]
        ci = fold["outerAuc95"]
        lines.append(f"| {fold['eventId']} | {means['distance']:.4f} | {means['logistic_regression']:.4f} | {means['lightgbm']:.4f} | {fold['selectedModel']} | {fold['outerAuc']:.4f} [{ci[0]:.4f}, {ci[1]:.4f}] |")
    lines += ["", f"Nested pooled AUC: **{selection['nestedAuc']:.4f} [{low:.4f}, {high:.4f}]**, 95% event-bootstrap interval from 2,000 draws. The bootstrap resamples the seven saved outer-event prediction blocks, without retraining or rerunning selection; it does not include all uncertainty from model choice, correlated issuers, or retrospective data.", "",
              "Pick counts: " + "; ".join(f"{kind}: {selection['selectionCounts'][kind]}/7" for kind in CANDIDATES) + ".", "",
              selection["mainModelReason"], "",
              "The main export uses the most frequently picked family, with an own-event-held-out refit for each evaluated historical event. Selecting this family from all folds is an additional data-dependent summary. Its fixed-family outer score is descriptive; the nested fold-selected score above is the estimate for the complete training-only selection procedure. If fold choices differ, those are different sets of predictions and must not be conflated.", "",
              "All three unchanged candidates' outer refits are retained for comparison:", "",
              "| Event | Companies | Hits | Distance AUC (95%) | Logistic AUC (95%) | LightGBM AUC (95%) |", "|---|---:|---:|---:|---:|---:|"]
    def fmt(row, key):
        return f"{row[key]:.4f} [{row[key+'Low95']:.4f}, {row[key+'High95']:.4f}]"
    for row in candidate_rows:
        lines.append(f"| {row['eventId']} | {row['companies']} | {row['hits']} | {fmt(row, 'distanceAuc')} | {fmt(row, 'logisticAuc')} | {fmt(row, 'lightgbmAuc')} |")
    lines += ["", "Candidate pooled outer scores (descriptive comparisons; never used to revise the protocol):", ""]
    for kind in CANDIDATES:
        result = selection["candidateOverall"][kind]
        ci = result["auc95"]
        lines.append(f"- {kind}: {result['auc']:.4f} [{ci[0]:.4f}, {ci[1]:.4f}].")
    lines += ["", "Why the winner won: the pick table shows the training-only criterion directly. Its inner mean AUC was highest in the most outer folds; no outer score selected it within a fold. There are only 3–14 hits per event, and many geographic/financial inputs are coarse or missing. The original fixed-model replay above showed large apparent-training/held-out gaps; the new candidate table provides the relevant new out-of-event results. This is evidence of limited generalization, not proof that sparse positives alone cause overfitting or that the winning family predicts physical production losses.", "",
              "LightGBM retains its original shallow-tree settings. Training length is chosen using a further stopping event inside each candidate's training pool, followed by refitting the whole pool; neither inner-scoring nor outer-test labels supply stopping decisions. Logistic preprocessing and distance calibration are fitted on training companies only. Company/site duplicates never enter these metrics.", "",
              "Point probabilities come from the full-training refit. Per-site bounds come from 200 event-bootstrap refits of the exported family, with percentile limits conservatively expanded to include the point estimate if necessary. These are conditional model bounds, not calibrated limits on physical disruption. Feature explanations describe the full-training refit: native TreeSHAP for trees, interventional linear SHAP for logistic regression, and exact single-input SHAP for the distance rule, on numerically clipped log odds.", "",
              "The first table in this report is the archived pre-selection model. The new tables use exactly the seven-event training population and full-training point refits required for selection. The archived LightGBM model used an event-bootstrap median; comparisons therefore reflect both the specified population change and point-refit statistic. Features and CAR labels are byte-identical to their frozen inputs.", "",
              "New LightGBM point-refit diagnostic, using the same already fitted outer models:", "",
              "| Outer event | Apparent training AUC | Held-out AUC |", "|---|---:|---:|"]
    candidate_by_event = {r["eventId"]: r for r in candidate_rows}
    for fold in selection["outerFolds"]:
        lines.append(f"| {fold['eventId']} | {fold['lightgbmApparentTrainingAuc']:.4f} | {candidate_by_event[fold['eventId']]['lightgbmAuc']:.4f} |")
    lines += ["", "The new training/test gaps also support limited generalization under these fixed settings. Training AUC is apparent fit quality, not independent evidence; the inner means, rather than this diagnostic or outer test scores, made every selection."]
    path = folder / "evaluation_report.md"
    before = path.read_text(encoding="utf-8").split("## Model selection")[0].rstrip()
    path.write_text(before + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def train_selected(members=200, metric_draws=2000):
    protocol_path = ROOT / "data/sources/model_selection_protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    freeze = json.loads((ROOT / "data/review/model_selection_protocol_freeze.json").read_text(encoding="utf-8"))
    assert digest(protocol_path) == freeze["protocolSha256"]
    assert digest(ROOT / "data/processed/features.csv") == freeze["featuresSha256"]
    assert digest(ROOT / "data/processed/labels.csv") == freeze["labelsSha256"]
    assert PARAMETERS == freeze["existingLightGBMParameters"]
    assert list(CANDIDATES) == protocol["candidates"] == protocol["tieOrder"]
    if members != protocol["predictionBootstrapMembers"] or metric_draws != protocol["metricBootstrapDraws"]:
        raise ValueError("Do not override the frozen protocol's refit or bootstrap counts")
    features = pd.read_csv(ROOT / "data/processed/features.csv")
    features["part_type"] = features.part_type.fillna("unknown")
    labels = pd.read_csv(ROOT / "data/processed/labels.csv")
    valid = labels[(labels.status == "ok") & (labels.role == "supplier")].copy()
    valid["hit"] = valid.hit.astype(str).str.lower().eq("true").astype(int)
    all_data = features.merge(valid[["eventId", "companyId", "hit", "car"]], on=["eventId", "companyId"], validate="one_to_one")
    metrics_path = ROOT / "data/processed/metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    data, excluded = evaluation_population(all_data, metrics["evaluationPolicy"])
    event_ids = sorted(data.eventId.unique())
    if len(event_ids) != 7:
        raise ValueError("The frozen protocol requires exactly seven evaluated events")
    candidate_records, outer_folds, outer_models, cache = [], [], {}, {}
    with threadpool_limits(limits=1):
        for event_id in event_ids:
            training = data[data.eventId != event_id].reset_index(drop=True)
            test = features[features.eventId == event_id].reset_index(drop=True)
            selected, means, inner = choose_candidate(training, cache)
            fold = {"eventId": event_id, "trainingEvents": sorted(training.eventId.unique()), "selectedModel": selected,
                    "innerMeanAuc": means, "innerFolds": inner}
            candidates = {kind: FittedCandidate(kind, training) for kind in CANDIDATES}
            probabilities = {kind: model.predict(test) for kind, model in candidates.items()}
            for i, row in test.iterrows():
                candidate_records.append({"eventId": event_id, "companyId": row.companyId,
                                          **{PROBABILITY_COLUMNS[kind]: float(probabilities[kind][i]) for kind in CANDIDATES},
                                          "nestedProbability": float(probabilities[selected][i])})
            outer_models[event_id] = candidates
            outer_folds.append(fold)
            print(f"Selection fixed for outer {event_id}: {selected}; inner means {means}", flush=True)
        counts = {kind: sum(f["selectedModel"] == kind for f in outer_folds) for kind in CANDIDATES}
        main = next(kind for kind in CANDIDATES if counts[kind] == max(counts.values()))
        candidates_frame = pd.DataFrame(candidate_records)
        held = all_data[all_data.eventId.isin(event_ids)][["eventId", "companyId", "supplier", "hit", "car"]].merge(candidates_frame, on=["eventId", "companyId"], validate="one_to_one")
        held["pHit"] = held[PROBABILITY_COLUMNS[main]]
        nested = held.copy()
        nested["pHit"] = nested.nestedProbability
        nested_intervals = bootstrap_intervals(nested, metric_draws)
        candidate_overall = {}
        for kind in CANDIDATES:
            frame = held.copy()
            frame["pHit"] = frame[PROBABILITY_COLUMNS[kind]]
            candidate_overall[kind] = {**score(frame.hit, frame.pHit), "auc95": bootstrap_intervals(frame, metric_draws)["auc"]}
        candidate_rows = []
        for fold in outer_folds:
            frame = held[held.eventId == fold["eventId"]]
            ci = auc_intervals(frame, {"distanceAuc": "distanceProbability", "logisticAuc": "logisticProbability", "lightgbmAuc": "lightgbmProbability"})
            row = {"eventId": fold["eventId"], "companies": len(frame), "hits": int(frame.hit.sum())}
            for kind, key in [("distance", "distanceAuc"), ("logistic_regression", "logisticAuc"), ("lightgbm", "lightgbmAuc")]:
                row[key] = score(frame.hit, frame[PROBABILITY_COLUMNS[kind]])["auc"]
                row[key+"Low95"], row[key+"High95"] = ci[key]
            fold["outerAuc"] = score(frame.hit, frame.nestedProbability)["auc"]
            selected_key = {"distance": "distanceAuc", "logistic_regression": "logisticAuc", "lightgbm": "lightgbmAuc"}[fold["selectedModel"]]
            fold["outerAuc95"] = ci[selected_key]
            fold["lightgbmApparentTrainingAuc"] = score(outer_models[fold["eventId"]]["lightgbm"].training.hit,
                                                         outer_models[fold["eventId"]]["lightgbm"].predict(outer_models[fold["eventId"]]["lightgbm"].training))["auc"]
            candidate_rows.append(row)
        reason = f"{main} was picked in {counts[main]} of 7 outer training-only selection contests, the highest frequency, using mean inner-event AUC and the frozen tie rule. Its export choice was not chosen by comparing outer test AUCs."
        selection = {"protocolVersion": protocol["version"], "protocolSha256": digest(protocol_path), "selectionMetric": protocol["selectionScore"],
                     "mainModel": main, "mainModelPickCount": counts[main], "selectionCounts": counts, "outerFolds": outer_folds,
                     "nestedAuc": score(nested.hit, nested.pHit)["auc"], "nestedAuc95": nested_intervals["auc"],
                     "candidateOverall": candidate_overall, "mainModelReason": reason,
                     "scoreScope": protocol["mainModelScope"], "uncertaintyDefinition": protocol["metricInterval"]}
        predictions, manifests = [], []
        for event_id in sorted(features.eventId.unique()):
            test = features[features.eventId == event_id].reset_index(drop=True)
            training = data[data.eventId != event_id].reset_index(drop=True)
            model = outer_models[event_id][main] if event_id in outer_models else FittedCandidate(main, training)
            point = model.predict(test)
            low, high, expanded = prediction_intervals(main, training, test, model, members)
            base, phi, raw, explanation = model.explain(test)
            for i, row in test.iterrows():
                values = sorted(({"feature": name, "value": float(value[i])} for name, value in phi.items()), key=lambda p: abs(p["value"]), reverse=True)
                predictions.append({"eventId": event_id, "companyId": row.companyId, "supplier": row.supplier, "snapshotYear": int(row.snapshotYear),
                                    "pHit": float(point[i]), "ciLow": float(low[i]), "ciHigh": float(high[i]), "lowConfidence": True,
                                    "shap": values, "shapBaseValue": float(base[i]), "shapMeanRawScore": float(raw[i]),
                                    "predictionModel": main, "explanationMethod": explanation, "sources": json.loads(row.sources)})
            manifests.append({"heldOutEvent": event_id, "trainingEvents": sorted(training.eventId.unique()), "model": main,
                              "members": members, "innerValidationEvent": model.stopping_event, "earlyStoppedRounds": model.rounds,
                              "parameters": PARAMETERS if main == "lightgbm" else protocol["logistic"] if main == "logistic_regression" else {"definition": protocol["distance"]},
                              "intervalsExpandedToIncludePoint": expanded, "evaluatedEvent": event_id in event_ids,
                              "scope": "Own-event-held-out refit" if event_id in event_ids else "Company-only projection from all seven evaluated training events; not evaluated"})
    per_event = []
    for event_id, frame in held.groupby("eventId", sort=True):
        ci = auc_intervals(frame, {"auc": "pHit", "baselineAuc": "logisticProbability", "distanceAuc": "distanceProbability"})
        per_event.append({"eventId": event_id, **score(frame.hit, frame.pHit), "baselineAuc": score(frame.hit, frame.logisticProbability)["auc"],
                          "logisticBrier": score(frame.hit, frame.logisticProbability)["brier"], "distanceAuc": score(frame.hit, frame.distanceProbability)["auc"],
                          "distanceBrier": score(frame.hit, frame.distanceProbability)["brier"], "rows": len(frame), "hits": int(frame.hit.sum()), "auc95": ci})
    metrics.update(model=main, events=7, rows=len(held), loeo=per_event, overall=bootstrap_intervals(held, metric_draws), calibration=calibration(held),
                   overallPoint={**score(held.hit, held.pHit), "baselineAuc": score(held.hit, held.logisticProbability)["auc"], "distanceAuc": score(held.hit, held.distanceProbability)["auc"]},
                   modelSelection=selection, modelReason=reason, excludedFromMetrics=excluded,
                   evaluationDefinition="Seven-event nested LOEO chooses a family using six inner mean event AUCs. Nested fold-selected scores are in modelSelection. Top-level scores describe the modal exported family's own-event-held-out point refits, with post-selection family-choice limitations.",
                   probabilityDefinition="Point probability from the main family's full outer-training refit. Bounds are 200 event-bootstrap percentile refits, conservatively expanded to contain the point.",
                   shapDefinition="Exact raw-score contributions for the selected full-training refit; explanationMethod identifies TreeSHAP, interventional linear SHAP or exact single-input distance SHAP. shapMeanRawScore is the legacy field name for that explained refit's raw log odds, not a bootstrap mean.",
                   baselineDefinition="Unchanged candidate settings, each refit on six eligible training events: logistic regression with training-only imputation/scaling and a distance exponential calibrated on training prevalence",
                   predictionIntervalDefinition=protocol["predictionInterval"])
    prefixes = ("Nested selection uses exactly", "The modal exported family", "Metric event-bootstrap intervals condition")
    metrics["limitations"] = [s for s in metrics["limitations"] if "training cohorts are unchanged" not in s and not s.startswith(prefixes)]
    metrics["limitations"] += ["Nested selection uses exactly seven two-class events; both 2011 events are excluded from training as well as metrics for this procedure",
                               "The modal exported family is chosen by aggregate inner-selection frequency across all folds. Its fixed-family outer score is descriptive; modelSelection.nestedAuc evaluates the fold-wise training-only selector",
                               "Metric event-bootstrap intervals condition on saved predictions; model choice is not rerun in bootstrap draws"]
    metrics["evaluationPolicy"] = {**metrics["evaluationPolicy"],
                                   "scope": "Single-class events remain excluded from all metrics. The newer nested-selection protocol also excludes them from training, using only seven two-class events.",
                                   "trainingPolicySource": "data/sources/model_selection_protocol.json"}
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    # Keep all nine original observed company-event rows in the saved table;
    # unlocated 2011 predictions are projections, not extra evaluated events.
    extra = all_data[~all_data.eventId.isin(event_ids)][["eventId", "companyId", "supplier", "hit", "car"]].merge(
        pd.DataFrame(predictions)[["eventId", "companyId", "pHit"]], on=["eventId", "companyId"], validate="one_to_one")
    pd.concat([held, extra], ignore_index=True).to_csv(ROOT / "data/processed/held_out_predictions.csv", index=False)
    lookup = {(p["eventId"], p["companyId"]): p for p in predictions}
    actual = {(r["eventId"], r["companyId"]): r for r in valid.to_dict("records")}
    metadata = json.loads((ROOT / "data/processed/feature_metadata.json").read_text(encoding="utf-8"))
    sites = []
    fields = ["pHit", "ciLow", "ciHigh", "lowConfidence", "shap", "shapBaseValue", "shapMeanRawScore", "predictionModel", "explanationMethod"]
    for site in metadata["sites"]:
        key = (site["eventId"], site["companyId"])
        known = actual.get(key)
        sites.append({**site, **{k: lookup[key][k] for k in fields},
                      "actual": {"hit": bool(known["hit"]), "car": float(known["car"])} if known else None,
                      "predictionScope": "Company-level stock-response projection shared by disclosed sites; not site-specific damage",
                      "outcomeObservable": known is not None})
    for name, values in [("company_predictions.json", predictions), ("site_predictions.json", sites)]:
        (ROOT / "data/processed" / name).write_text(json.dumps({"sampleData": False, "predictions": values}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    manifest = {"sampleData": False, "seed": SEED, "model": main, "folds": manifests, "modelSelection": selection,
                "companyPredictions": len(predictions), "sitePredictions": len(sites), "cohorts": metrics["cohorts"],
                "evaluatedEvents": event_ids, "excludedFromMetrics": excluded,
                "inputSha256": {p: digest(ROOT / p) for p in ["data/processed/features.csv", "data/processed/labels.csv", "data/sources/model_selection_protocol.json"]}}
    (ROOT / "ml/model_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_selection_report(selection, candidate_rows)
    print(json.dumps({"mainModel": main, "selectionCounts": counts, "nestedAuc": selection["nestedAuc"], "nestedAuc95": selection["nestedAuc95"]}, indent=2))
    return metrics
