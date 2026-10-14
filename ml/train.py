"""Nested leave-one-event-out evaluation and 200-model event-bootstrap ensembles."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from threadpoolctl import threadpool_limits

from ml.features import NUMERIC
from ml.runtime import ensure_openmp

ensure_openmp()
import lightgbm as lgb

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261014
PARAMETERS = {"objective": "binary", "metric": "binary_logloss", "max_depth": 3, "num_leaves": 7, "min_data_in_leaf": 20,
              "learning_rate": 0.04, "lambda_l1": 0.1, "lambda_l2": 1.0, "verbosity": -1, "num_threads": 1,
              "deterministic": True, "force_col_wise": True, "feature_pre_filter": False}


class Encoder:
    def __init__(self):
        self.category = OneHotEncoder(handle_unknown="ignore", sparse_output=False, dtype=np.float64)

    def fit(self, frame):
        self.category.fit(frame[["part_type"]])
        self.groups = NUMERIC + ["part_type"] * len(self.category.categories_[0])
        return self

    def transform(self, frame):
        numeric = frame[NUMERIC].to_numpy(dtype=np.float64)
        return np.column_stack([numeric, self.category.transform(frame[["part_type"]])])


def score(y, probability, weights=None):
    mask = np.ones(len(y), dtype=bool) if weights is None else weights > 0
    weight = None if weights is None else weights[mask]
    actual = np.asarray(y)[mask]
    predicted = np.asarray(probability)[mask]
    return {"auc": float(roc_auc_score(actual, predicted, sample_weight=weight)) if len(np.unique(actual)) == 2 else None,
            "brier": float(brier_score_loss(actual, predicted, sample_weight=weight))}


def distance_rule(training_distance, y, prediction_distance):
    """Monotone distance rule, calibrated to training prevalence only."""
    train = np.asarray(training_distance, dtype=float)
    predict = np.asarray(prediction_distance, dtype=float)
    known = np.isfinite(train)
    prevalence = float(np.mean(y))
    scale = float(np.median(train[known])) if known.any() else 1.0
    scale = max(scale, 1.0)
    base = np.exp(-np.nan_to_num(train, nan=scale) / scale)
    low, high = 0.0, 1000.0
    for _ in range(60):
        mid = (low + high) / 2
        if np.mean(np.minimum(1, base * mid)) < prevalence:
            low = mid
        else:
            high = mid
    result = np.minimum(1, np.exp(-np.nan_to_num(predict, nan=scale) / scale) * ((low + high) / 2))
    result[~np.isfinite(predict)] = prevalence
    return result


def bootstrap_intervals(frame, draws=2000):
    rng = np.random.default_rng(SEED)
    events = np.array(sorted(frame["eventId"].unique()))
    y = frame["hit"].to_numpy()
    intervals = {"auc": [], "brier": [], "baselineAuc": [], "distanceAuc": []}
    for _ in range(draws):
        sampled = Counter(rng.choice(events, len(events), replace=True))
        weights = frame["eventId"].map(sampled).fillna(0).to_numpy(dtype=float)
        model = score(y, frame["pHit"], weights)
        logistic = score(y, frame["logisticProbability"], weights)
        distance = score(y, frame["distanceProbability"], weights)
        for key, value in [("auc", model["auc"]), ("brier", model["brier"]), ("baselineAuc", logistic["auc"]), ("distanceAuc", distance["auc"])]:
            if value is not None:
                intervals[key].append(value)
    return {key: [float(v) for v in np.quantile(values, [0.025, 0.975])] if values else None for key, values in intervals.items()}


def calibration(frame):
    result = []
    probability = frame["pHit"].to_numpy()
    for i in range(10):
        mask = (probability >= i / 10) & ((probability < (i + 1) / 10) if i != 9 else (probability <= 1))
        if mask.any():
            result.append({"binMid": (i + 0.5) / 10, "predicted": float(probability[mask].mean()), "observed": float(frame.loc[mask, "hit"].mean()), "n": int(mask.sum())})
    return result


def evaluation_population(frame, policy):
    """Apply the user's event-level exclusion to every reported metric."""
    excluded = []
    for event_id, rows in frame.groupby("eventId", sort=True):
        if rows["hit"].nunique() < 2:
            excluded.append({"eventId": event_id, "rows": len(rows), "hits": int(rows["hit"].sum()),
                             "reason": "Single observed supplier outcome class; excluded from all metrics by the user's decision"})
    if excluded and (policy.get("approved") is not True or policy.get("singleClassEvents") != "exclude-from-metrics"):
        raise ValueError("Single-class metric exclusions require the user's recorded evaluation decision")
    identifiers = {row["eventId"] for row in excluded}
    eligible = frame[~frame["eventId"].isin(identifiers)].copy()
    if eligible.empty:
        raise ValueError("No events with both outcome classes remain for evaluation")
    return eligible, excluded


def nested_rounds(training):
    events = sorted(training["eventId"].unique())
    validation_event = events[-1]
    fit = training[training["eventId"] != validation_event]
    validation = training[training["eventId"] == validation_event]
    encoder = Encoder().fit(fit)
    names = [f"f{i}" for i in range(len(encoder.groups))]
    dataset = lgb.Dataset(encoder.transform(fit), label=fit["hit"].to_numpy(), feature_name=names)
    validate = lgb.Dataset(encoder.transform(validation), label=validation["hit"].to_numpy(), reference=dataset, feature_name=names)
    booster = lgb.train({**PARAMETERS, "seed": SEED}, dataset, num_boost_round=400, valid_sets=[validate],
                        callbacks=[lgb.early_stopping(20, first_metric_only=True, verbose=False)])
    return max(1, booster.best_iteration), validation_event


def fit_fold(training, prediction, event_id, members=200):
    rounds, validation_event = nested_rounds(training)
    encoder = Encoder().fit(training)
    x, xp = encoder.transform(training), encoder.transform(prediction)
    y = training["hit"].to_numpy()
    logistic = make_pipeline(SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True), StandardScaler(),
                             LogisticRegression(C=1.0, solver="lbfgs", max_iter=1500, random_state=SEED))
    logistic.fit(x, y)
    logistic_probability = logistic.predict_proba(xp)[:, 1]
    distance_probability = distance_rule(training["distance_km"], y, prediction["distance_km"])
    rng = np.random.default_rng(SEED + sum(event_id.encode()))
    events = np.array(sorted(training["eventId"].unique()))
    probability = np.empty((members, len(prediction)))
    contributions = np.zeros((len(prediction), len(encoder.groups) + 1))
    base = ROOT / "data/raw/model_ensembles" / event_id
    base.mkdir(parents=True, exist_ok=True)
    manifest = {"heldOutEvent": event_id, "trainingEvents": events.tolist(), "innerValidationEvent": validation_event, "earlyStoppedRounds": rounds,
                "members": members, "parameters": PARAMETERS, "encoderCategories": encoder.category.categories_[0].tolist(), "featureGroups": encoder.groups, "models": []}
    names = [f"f{i}" for i in range(len(encoder.groups))]
    for i in range(members):
        sampled = rng.choice(events, len(events), replace=True)
        indices = np.concatenate([np.flatnonzero(training["eventId"].to_numpy() == event) for event in sampled])
        dataset = lgb.Dataset(x[indices], label=y[indices], feature_name=names)
        booster = lgb.train({**PARAMETERS, "seed": SEED + i}, dataset, num_boost_round=rounds)
        probability[i] = booster.predict(xp, num_threads=1)
        contributions += booster.predict(xp, pred_contrib=True, num_threads=1)
        path = base / f"member_{i:03d}.txt"
        booster.save_model(str(path))
        manifest["models"].append({"file": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "sampledEvents": sampled.tolist()})
        if (i + 1) % 50 == 0:
            print(f"{event_id}: {i + 1}/{members} event-bootstrap models", flush=True)
    contributions /= members
    intervals = np.quantile(probability, [0.025, 0.5, 0.975], axis=0)
    phi = {feature: contributions[:, [j for j, group in enumerate(encoder.groups) if group == feature]].sum(axis=1) for feature in NUMERIC + ["part_type"]}
    result = []
    for position, (_, record) in enumerate(prediction.iterrows()):
        values = sorted(({"feature": feature, "value": float(phi[feature][position])} for feature in phi), key=lambda p: abs(p["value"]), reverse=True)
        result.append({"eventId": event_id, "companyId": record["companyId"], "supplier": record["supplier"], "snapshotYear": int(record["snapshotYear"]),
                       "pHit": float(intervals[1, position]), "ciLow": float(intervals[0, position]), "ciHigh": float(intervals[2, position]),
                       "lowConfidence": True, "shap": values, "shapBaseValue": float(contributions[position, -1]),
                       "shapMeanRawScore": float(contributions[position].sum()), "logisticProbability": float(logistic_probability[position]),
                       "distanceProbability": float(distance_probability[position]), "sources": json.loads(record["sources"])})
    (base / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return result, manifest


def train(members=200, metric_draws=2000):
    features = pd.read_csv(ROOT / "data/processed/features.csv", keep_default_na=True)
    features["part_type"] = features["part_type"].fillna("unknown")
    labels = pd.read_csv(ROOT / "data/processed/labels.csv")
    valid = labels[(labels["status"] == "ok") & (labels["role"] == "supplier")].copy()
    valid["hit"] = valid["hit"].astype(str).str.lower().eq("true").astype(int)
    training_data = features.merge(valid[["eventId", "companyId", "hit", "car"]], on=["eventId", "companyId"], how="inner", validate="one_to_one")
    if len(training_data) != len(valid):
        raise ValueError("At least one valid company label has no unique feature record")
    event_ids = sorted(training_data["eventId"].unique())
    policy_path = ROOT / "data/sources/evaluation_policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8")) if policy_path.exists() else {}
    evaluation_population(training_data, policy)  # Fail before fitting if a decision is missing.
    if len(event_ids) < 3:
        raise ValueError("At least three events are required for nested event-held-out fitting")
    company_predictions, manifests = [], []
    with threadpool_limits(limits=1):
        for event_id in event_ids:
            training = training_data[training_data["eventId"] != event_id].reset_index(drop=True)
            prediction = features[features["eventId"] == event_id].reset_index(drop=True)
            if training["hit"].nunique() < 2:
                raise ValueError("Training events contain no positive or no negative labels")
            result, manifest = fit_fold(training, prediction, event_id, members)
            company_predictions.extend(result)
            manifests.append(manifest)
    prediction_frame = pd.DataFrame([{k: p[k] for k in ["eventId", "companyId", "pHit", "logisticProbability", "distanceProbability"]} for p in company_predictions])
    held_out = training_data[["eventId", "companyId", "supplier", "hit", "car"]].merge(prediction_frame, on=["eventId", "companyId"], validate="one_to_one")
    held_out.to_csv(ROOT / "data/processed/held_out_predictions.csv", index=False)
    evaluation, metric_exclusions = evaluation_population(held_out, policy)
    per_event = []
    for event_id, frame in evaluation.groupby("eventId"):
        evaluated = score(frame["hit"], frame["pHit"])
        logistic = score(frame["hit"], frame["logisticProbability"])
        distance = score(frame["hit"], frame["distanceProbability"])
        result = {"eventId": event_id, **evaluated, "baselineAuc": logistic["auc"], "logisticBrier": logistic["brier"],
                  "distanceAuc": distance["auc"], "distanceBrier": distance["brier"], "rows": len(frame), "hits": int(frame["hit"].sum())}
        per_event.append(result)
    event_rows = list(csv.DictReader((ROOT / "data/events.csv").open(encoding="utf-8")))
    cohorts = [{"eventId": e["id"], **json.loads(e["cohort"])} for e in event_rows if e.get("cohort")]
    excluded_path = ROOT / "data/review/event_gaps.json"
    excluded = json.loads(excluded_path.read_text(encoding="utf-8"))["events"] if excluded_path.exists() else []
    metrics = {"model": "lightgbm", "sampleData": False, "events": int(evaluation["eventId"].nunique()), "rows": len(evaluation), "loeo": per_event,
               "predictionEvents": len(event_ids), "evaluationPolicy": policy, "excludedFromMetrics": metric_exclusions,
               "cohorts": cohorts, "excludedEvents": excluded,
               "overall": bootstrap_intervals(evaluation, metric_draws), "calibration": calibration(evaluation), "bootstrapEventDraws": metric_draws,
               "ensembleMembersPerFold": members, "probabilityDefinition": "Median of event-bootstrap probabilities; per-node intervals are 2.5/97.5 percentiles",
               "overallPoint": {**score(evaluation["hit"], evaluation["pHit"]), "baselineAuc": score(evaluation["hit"], evaluation["logisticProbability"])["auc"],
                                "distanceAuc": score(evaluation["hit"], evaluation["distanceProbability"])["auc"]},
               "baselineDefinition": "Logistic regression with training-only median imputation and scaling; distance-only exponential rule calibrated to training prevalence",
               "evaluationDefinition": "Entire target event excluded from every training model. Tree count selected by early stopping on another event inside training; bootstrap refits use that tree count.",
               "shapDefinition": "Mean TreeSHAP contributions to raw log odds across bootstrap models; categorical dummy contributions are summed. Mean raw score is distinct from logit of median probability.",
               "lowConfidenceRule": "All predictions flagged while public route dependence is unavailable; coarse geography, limited event clusters, and extrapolation to unlisted firms add uncertainty",
               "limitations": ["Retrospective cohorts and a current listing universe; delisted issuers and unverified mappings are underrepresented",
                               "Reported metrics exclude single-class events by user decision; this outcome-based selection conditions the evaluation population and omits both 2011 events",
                               "2011 uses the approved January 2012 company roster approximation; factory locations and all geographic predictors are unavailable for those events",
                               "FY2019 and FY2024 Supplier Lists are unavailable; Japan-Korea 2019, Taiwan 2024, and Helene 2024 remain excluded",
                               "Stock-market abnormal-return labels are proxies, not causal disruption losses or observed factory damage",
                               "Country concentration uses disclosed location counts, not actual sourcing volumes",
                               "Transport-route chokepoint dependence is unavailable; graph hops describe disclosure relationships",
                               "Bootstrap intervals condition on the public-data model and do not quantify unreported routes or location measurement error"]}
    (ROOT / "data/processed/metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    company_lookup = {(p["eventId"], p["companyId"]): p for p in company_predictions}
    metadata = json.loads((ROOT / "data/processed/feature_metadata.json").read_text(encoding="utf-8"))
    actual = {(r["eventId"], r["companyId"]): r for r in valid.to_dict("records")}
    site_predictions = []
    for site in metadata["sites"]:
        prediction = company_lookup[(site["eventId"], site["companyId"])]
        known = actual.get((site["eventId"], site["companyId"]))
        site_predictions.append({**site, **{k: prediction[k] for k in ["pHit", "ciLow", "ciHigh", "lowConfidence", "shap", "shapBaseValue", "shapMeanRawScore"]},
                                 "actual": {"hit": bool(known["hit"]), "car": float(known["car"])} if known else None,
                                 "predictionScope": "Company-level market-response projection shared by disclosed sites; not a site-specific damage observation",
                                 "outcomeObservable": known is not None})
    (ROOT / "data/processed/company_predictions.json").write_text(json.dumps({"sampleData": False, "predictions": company_predictions}, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    (ROOT / "data/processed/site_predictions.json").write_text(json.dumps({"sampleData": False, "predictions": site_predictions}, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {"sampleData": False, "seed": SEED, "folds": [{k: m[k] for k in ["heldOutEvent", "trainingEvents", "innerValidationEvent", "earlyStoppedRounds", "members", "parameters", "featureGroups"]} for m in manifests],
               "inputSha256": {str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                               for path in [ROOT / "data/processed/features.csv", ROOT / "data/processed/labels.csv"] + ([policy_path] if policy_path.exists() else [])},
               "modelCache": "data/raw/model_ensembles/", "companyPredictions": len(company_predictions), "sitePredictions": len(site_predictions), "cohorts": cohorts,
               "evaluatedEvents": sorted(evaluation["eventId"].unique()), "excludedFromMetrics": metric_exclusions}
    (ROOT / "ml/model_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"events": metrics["events"], "rows": metrics["rows"], "overall": metrics["overall"], "sites": len(site_predictions)}, indent=2))
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--members", type=int, default=200)
    parser.add_argument("--metric-draws", type=int, default=2000)
    args = parser.parse_args()
    train(args.members, args.metric_draws)
