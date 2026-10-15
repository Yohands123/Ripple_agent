"""Explain the fixed pre-selection model, preserving its predictions and scores."""
import contextlib
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from ml.evaluation import auc_intervals, pair_decomposition
from ml.train import Encoder, lgb, score
from pipeline.audit_auc import audit

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = {"modelAuc": "pHit", "logisticAuc": "logisticProbability", "distanceAuc": "distanceProbability"}


def training_diagnostics(root, held, features):
    """Replay the actual saved 200-member ensembles on their training pools."""
    joined = held[["eventId", "companyId", "hit"]].merge(features, on=["eventId", "companyId"], validate="one_to_one")
    joined["part_type"] = joined["part_type"].fillna("unknown")
    result = []
    for event_id in sorted(held.eventId.unique()):
        path = root / "data/raw/model_ensembles" / event_id / "manifest.json"
        if not path.exists():
            return {"available": False, "reason": "Saved ensemble cache unavailable; no training performance invented"}
        manifest = json.loads(path.read_text(encoding="utf-8"))
        training = joined[joined.eventId != event_id].reset_index(drop=True)
        encoder = Encoder().fit(training)
        assert encoder.category.categories_[0].tolist() == manifest["encoderCategories"]
        x = encoder.transform(training)
        probabilities = []
        for member in manifest["models"]:
            model_path = root / member["file"]
            if hashlib.sha256(model_path.read_bytes()).hexdigest() != member["sha256"]:
                raise ValueError("Saved model cache does not match its manifest")
            probabilities.append(lgb.Booster(model_file=str(model_path)).predict(x, num_threads=1))
        median = np.median(probabilities, axis=0)
        test = held[held.eventId == event_id]
        result.append({"eventId": event_id, "trainingCompanies": len(training), "trainingHits": int(training.hit.sum()),
                       "apparentTrainingAuc": score(training.hit, median)["auc"], "heldOutAuc": score(test.hit, test.pHit)["auc"],
                       "rounds": manifest["earlyStoppedRounds"]})
        print("Replayed training diagnostic:", event_id, flush=True)
    return {"available": True, "folds": result,
            "definition": "Apparent AUC of the actual saved ensemble on its full outer-training pool. Some members omit events, but the ensemble as a whole was fitted to this pool; this is not independent validation."}


def write_report(root=ROOT):
    with contextlib.redirect_stdout(io.StringIO()):
        report = audit(root, prefix="evaluation_report")
    held = pd.read_csv(root / "data/processed/held_out_predictions.csv")
    features = pd.read_csv(root / "data/processed/features.csv")
    metrics = json.loads((root / "data/processed/metrics.json").read_text(encoding="utf-8"))
    eligible = held[held.eventId.isin([r["eventId"] for r in report["evaluatedEvents"]])].copy()
    for row in report["evaluatedEvents"]:
        row["auc95"] = auc_intervals(eligible[eligible.eventId == row["eventId"]], COLUMNS)
    with threadpool_limits(limits=1):
        diagnostic = training_diagnostics(root, held, features)
    decomposition = pair_decomposition(eligible)
    report.update(perEventIntervalMethod="10,000 paired stratified company bootstrap draws per event; 2.5/97.5 percentiles, seed 20261015; fixed predictions and observed hit counts",
                  overallIntervalMethod="2,000 event-cluster bootstrap draws on the seven eligible events; fixed predictions, no retraining",
                  pairDecomposition=decomposition, apparentTrainingDiagnostic=diagnostic,
                  preSelectionModel=metrics["model"], overall95=metrics["overall"])
    folder = root / "data/review"
    lines = ["# Evaluation of the fixed model before nested model selection", "",
             "This report records the existing LightGBM model before the new model-selection procedure. No predictions, settings or exclusions were changed for this audit. Companies and hits are observed counts; AUCs below include 95% bootstrap intervals.", "",
             "| Event | Companies | Hits | Model AUC (95%) | Logistic AUC (95%) | Distance AUC (95%) |",
             "|---|---:|---:|---:|---:|---:|"]
    def fmt(row, key):
        low, high = row["auc95"][key]
        return f"{row[key]:.4f} [{low:.4f}, {high:.4f}]"
    for row in report["evaluatedEvents"]:
        lines.append(f"| {row['eventId']} | {row['companies']} | {row['hits']} | {fmt(row, 'modelAuc')} | {fmt(row, 'logisticAuc')} | {fmt(row, 'distanceAuc')} |")
    lines += ["", "Within-event intervals resample companies separately among hits and non-hits, with the same 10,000 draws for all three models. This conditions on observed class counts. With only one event, an event-cluster bootstrap would produce a meaningless zero-width interval. These intervals do not refit models or account for correlated company returns, cohort uncertainty or analyst choices; three-hit events have especially limited information.", "",
              "Pooled AUCs and 95% event-bootstrap intervals:", ""]
    for label, key in [("LightGBM", "auc"), ("Logistic regression", "baselineAuc"), ("Distance", "distanceAuc")]:
        low, high = metrics["overall"][key]
        lines.append(f"- {label}: {metrics['overallPoint'][key]:.4f} [{low:.4f}, {high:.4f}].")
    lines += ["", "## Distance-baseline leak check", ""]
    lines += ["- " + finding for finding in report["findings"]]
    lines += ["", f"Duplicate company/event rows: {report['duplicateCompanyEventRows']}; duplicate ticker/event labels: {report['duplicateTickerEventRows']}. Maximum distance-rule replay error: {report['baselineReplayMaxAbsError']:.3g}; maximum reconstructed distance error: {report['distanceReconstructionMaxAbsKm']:.3g} km.", "",
              "Company labels do repeat on the map, but training and evaluation contain one row per company/event. For example, Suez's correct company-level distance AUC is 0.8808; incorrectly weighting those companies by their display sites would give 0.7583. This diagnostic demonstrates the distortion that duplicate-site evaluation would cause; it is not the method used.", "",
              "## Why pooled model AUC is below 0.5", "",
              f"The seven-event pooled score is {decomposition['pooledAuc']:.4f}; its event-bootstrap interval includes 0.5. The result does not establish that the model reliably predicts the opposite outcome. Few positives increase uncertainty but do not mathematically force AUC below 0.5. Site-shared labels cannot explain the result because they are deduplicated before fitting and scoring.", "",
              f"A concrete source of the low pooled score is ranking across different held-out event folds. {100*decomposition['crossEventPairShare']:.1f}% of all hit/non-hit pairs come from different events; their AUC is {decomposition['crossEventAuc']:.4f}. Pairs within the same event have a pair-weighted AUC of {decomposition['withinEventAuc']:.4f}. Pooling compares probabilities from separately fitted models facing events with different hit rates and predicted levels; it is not the mean of per-event AUCs. This decomposition exactly reconstructs the pooled score.", "",
              "| Event | Observed hit rate | Mean held-out probability |", "|---|---:|---:|"]
    for event_id, frame in eligible.groupby("eventId", sort=True):
        lines.append(f"| {event_id} | {frame.hit.mean():.4f} | {frame.pHit.mean():.4f} |")
    lines += ["", "The table shows the between-event prevalence/calibration shift. It is an observed explanation of cross-event ranking, not proof of a unique causal mechanism. The features describe public geographic and company attributes, while the labels are broad stock-market abnormal returns rather than measured operational disruption.", ""]
    if diagnostic["available"]:
        lines += ["The saved-ensemble training replay provides an overfitting diagnostic:", "",
                  "| Held-out event | Apparent training AUC | Held-out AUC | Boosting rounds |", "|---|---:|---:|---:|"]
        for row in diagnostic["folds"]:
            held_auc = "excluded: single class" if row["heldOutAuc"] is None else f"{row['heldOutAuc']:.4f}"
            lines.append(f"| {row['eventId']} | {row['apparentTrainingAuc']:.4f} | {held_auc} | {row['rounds']} |")
        lines += ["", diagnostic["definition"], "",
                  "A gap between apparent training and held-out performance is consistent with overfitting and event-distribution shift; these observations cannot separate their causal contributions. Shallow trees and early stopping do not guarantee transfer to a new event. The evidence does not justify reversing probabilities or tuning to the outer test results."]
    lines += ["", "The two zero-hit 2011 events remain excluded from every metric under the recorded user decision; their company predictions and observations remain exported. The evaluation has 843 company/event observations and 45 hits across seven events. Identity merging combined 201 supplied name variants (52 additional merges beyond earlier normalization); it did not remove duplicate same-event stock labels because none existed. See company_merge_comparison.md for that separate before/after comparison.", "",
              "The next step fixes a nested training-only choice among distance, logistic regression and LightGBM before running that new procedure. Existing outer scores have already been observed; they cannot be called prospectively unseen. The new selection rule must be frozen and mechanically exclude each outer event from all inner choices. No adjustment will be made based on its new outer results.", "",
              "Full intervals, replay checks, pair counts, model hashes and diagnostics are in evaluation_report.json. The original per-event audit remains in auc_audit.md and the canonical-merge audit in auc_after_merge.md."]
    (folder / "evaluation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (folder / "evaluation_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    flat = [{**{k:v for k,v in row.items() if k != "auc95"}, **{key+suffix: bounds[i] for key,bounds in row["auc95"].items() for i,suffix in enumerate(["Low95", "High95"])}} for row in report["evaluatedEvents"]]
    pd.DataFrame(flat).to_csv(folder / "evaluation_report.csv", index=False)
    print("Wrote seven-event intervals, leakage replay and generalization diagnostics")


if __name__ == "__main__":
    write_report()
