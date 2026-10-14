"""Read-only audit of saved company-level evaluation and distance predictions."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from ml.features import haversine
from ml.train import distance_rule

ROOT = Path(__file__).resolve().parents[1]


def audit(root=ROOT, prefix="auc_audit"):
    protected = ["ml/train.py", "ml/features.py", "ml/model_manifest.json", "data/events.csv",
                 "data/processed/features.csv", "data/processed/labels.csv", "data/processed/metrics.json",
                 "data/processed/held_out_predictions.csv", "data/processed/company_predictions.json",
                 "data/processed/site_predictions.json"]
    hashes = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in protected}
    metrics = json.loads((root / "data/processed/metrics.json").read_text())
    features = pd.read_csv(root / "data/processed/features.csv")
    held = pd.read_csv(root / "data/processed/held_out_predictions.csv")
    labels = pd.read_csv(root / "data/processed/labels.csv")
    valid = labels[(labels["status"] == "ok") & (labels["role"] == "supplier")]
    assert not features.duplicated(["eventId", "companyId"]).any()
    assert not held.duplicated(["eventId", "companyId"]).any()
    assert not valid.duplicated(["eventId", "ticker"]).any()
    assert len(valid) == len(held)
    data = held.merge(features[["eventId", "companyId", "distance_km", "matchedManufacturingLocations"]],
                      on=["eventId", "companyId"], validate="one_to_one")
    events = {e["id"]: e for e in csv.DictReader((root / "data/events.csv").open(encoding="utf-8"))}
    site_records = json.loads((root / "data/processed/site_predictions.json").read_text())["predictions"]
    sites = defaultdict(list)
    for site in site_records:
        sites[(site["eventId"], site["companyId"])].append(site)
    manifest = json.loads((root / "ml/model_manifest.json").read_text())
    assert all(f["heldOutEvent"] not in f["trainingEvents"] for f in manifest["folds"])
    replay_error, distance_error = 0.0, 0.0
    rows = []
    for fold in metrics["loeo"]:
        event_id = fold["eventId"]
        frame = data[data["eventId"] == event_id]
        training = data[data["eventId"] != event_id]
        replay = distance_rule(training["distance_km"], training["hit"], frame["distance_km"])
        replay_error = max(replay_error, float(np.max(np.abs(replay - frame["distanceProbability"].to_numpy()))))
        event = events[event_id]
        weights = []
        for record in frame.to_dict("records"):
            disclosed = sites[(event_id, record["companyId"])]
            manufacturing = [s for s in disclosed if s["locationRole"] == "manufacturing"]
            distances = [haversine(s["lon"], s["lat"], float(event["lon"]), float(event["lat"])) for s in manufacturing]
            if distances:
                assert np.isfinite(record["distance_km"])
                distance_error = max(distance_error, abs(min(distances) - record["distance_km"]))
            else:
                assert not np.isfinite(record["distance_km"])
            weights.append(len(disclosed))
        actual = frame["hit"]
        computed = {"modelAuc": float(roc_auc_score(actual, frame["pHit"])),
                    "distanceAuc": float(roc_auc_score(actual, frame["distanceProbability"])),
                    "logisticAuc": float(roc_auc_score(actual, frame["logisticProbability"]))}
        for key, stored in [("modelAuc", "auc"), ("distanceAuc", "distanceAuc"), ("logisticAuc", "baselineAuc")]:
            assert np.isclose(computed[key], fold[stored], atol=1e-12)
        positive_weight = np.asarray(weights) > 0
        site_auc = float(roc_auc_score(actual[positive_weight], frame.loc[positive_weight, "distanceProbability"],
                                      sample_weight=np.asarray(weights)[positive_weight]))
        rows.append({"eventId": event_id, "companies": len(frame), "hits": int(actual.sum()), **computed,
                     "missingDistances": int(frame["distance_km"].isna().sum()),
                     "companySiteProjections": sum(weights), "maxSitesPerCompany": max(weights),
                     "siteWeightedDistanceAucDiagnostic": site_auc})
    assert replay_error < 1e-12 and distance_error < 1e-8
    company_events = held.groupby("companyId")["eventId"].nunique()
    report = {"inputSha256": hashes, "modelChanged": False, "evaluatedEvents": rows,
              "duplicateCompanyEventRows": 0, "duplicateTickerEventRows": 0,
              "baselineReplayMaxAbsError": replay_error, "distanceReconstructionMaxAbsKm": distance_error,
              "companiesObservedInMultipleEvents": int((company_events > 1).sum()),
              "excludedFromMetrics": metrics["excludedFromMetrics"], "overall": metrics["overallPoint"],
              "findings": [
                  "No direct held-out-label leakage detected: evaluation has one row per company/event and one valid supplier per ticker/event.",
                  "Sites share company labels only in display projections; these repeated site rows do not enter metrics or training. Site-weighted AUC is a diagnostic of the distortion that would occur if they did.",
                  "All saved evaluated distances reconstruct from disclosed manufacturing locations and independently sourced event anchors, without hit labels or a fitted hit-cluster center. Headquarters are excluded.",
                  "Saved distance probabilities reproduce using other events' labeled companies only: median known training distance and training prevalence. No held-out labels select the scale or calibration.",
                  "The same issuer appears in other events during training. Leave-one-event-out tests a new event, not a new company; company dependence and within-event market correlation remain.",
                  "Minimum distance favors firms with more disclosed sites; varying disclosure coverage and coarse centroids may confound it. Straight-line distance to Suez or the Red Sea is not observed route exposure.",
                  "Public shock anchors and retrospective supplier cohorts were analyst-defined, not prospectively preregistered. Code/data checks cannot prove that no analyst selection was influenced by later knowledge.",
                  "The approved removal of single-class events conditions pooled metrics on observed outcomes. Few hits, current-universe survivorship, and repeated companies limit inference.",
                  "ReplaySection.tsx currently labels baselineAuc as distance alone, but baselineAuc is logistic regression. This is a display-label error, not leakage in the saved distance predictions. Web code was not changed."
              ]}
    output = root / "data/review"
    with (output / f"{prefix}.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output / f"{prefix}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# Company-level AUC and distance leakage audit", "", "Saved model, features, labels, and predictions were not changed.", "",
             "| Event | Companies | Hits | Model AUC | Distance AUC | Logistic AUC |", "|---|---:|---:|---:|---:|---:|"]
    lines += [f"| {r['eventId']} | {r['companies']} | {r['hits']} | {r['modelAuc']:.4f} | {r['distanceAuc']:.4f} | {r['logisticAuc']:.4f} |" for r in rows]
    lines += ["", f"Pooled AUC: model {metrics['overallPoint']['auc']:.4f}; distance {metrics['overallPoint']['distanceAuc']:.4f}; logistic {metrics['overallPoint']['baselineAuc']:.4f}.", "",
              "`baselineAuc` means logistic regression; `distanceAuc` is the separate distance rule. Both 2011 events remain excluded from metrics under the user's decision.", ""]
    lines += ["- " + finding for finding in report["findings"]]
    lines += ["", f"Distance replay maximum absolute probability error: {replay_error:.3g}. Reconstructed minimum-distance error: {distance_error:.3g} km.", "",
              f"Audit inputs and their SHA-256 hashes are in `{prefix}.json`. `{prefix}.csv` also records missing distances, site projection multiplicity, and hypothetical site-weighted distance AUCs.", "",
              "Evidence: `ml/features.py` builds distances before outcomes are joined; `ml/train.py` joins one-to-one company/event labels, excludes the outer event before fitting, and calibrates the distance rule on training data. `data/events.csv` retains the source and location basis for each shock."]
    (output / f"{prefix}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert hashes == {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in protected}
    print(json.dumps({"events": rows, "baselineReplayMaxAbsError": replay_error, "distanceReconstructionMaxAbsKm": distance_error}, indent=2))
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", choices=["auc_audit", "auc_after_merge"], default="auc_audit")
    audit(prefix=parser.parse_args().prefix)
