"""Compare the saved pre-merge audit with the user-requested canonical retrain."""

from __future__ import annotations

import csv
import io
import json
import math
import subprocess
from pathlib import Path

from pipeline.company_registry import registry
from pipeline.prices import company_key

ROOT = Path(__file__).resolve().parents[1]
BEFORE_COMMIT = "cb7985a"


def previous_csv(path):
    text = subprocess.check_output(["git", "show", f"{BEFORE_COMMIT}:{path}"], cwd=ROOT, text=True, encoding="utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def compare():
    classes = registry()
    before = json.loads((ROOT / "data/review/auc_audit.json").read_text())
    after = json.loads((ROOT / "data/review/auc_after_merge.json").read_text())
    old_features = previous_csv("data/processed/features.csv")
    new_features = list(csv.DictReader((ROOT / "data/processed/features.csv").open(encoding="utf-8")))
    old_labels = {(r["eventId"], r["ticker"]): r for r in previous_csv("data/processed/labels.csv") if r["role"] == "supplier" and r["status"] == "ok"}
    new_labels = {(r["eventId"], r["ticker"]): r for r in csv.DictReader((ROOT / "data/processed/labels.csv").open(encoding="utf-8")) if r["role"] == "supplier" and r["status"] == "ok"}
    common = old_labels.keys() & new_labels.keys()
    assert all(math.isclose(float(old_labels[k]["car"]), float(new_labels[k]["car"]), abs_tol=1e-10)
               and old_labels[k]["hit"] == new_labels[k]["hit"] for k in common)
    assert not old_labels.keys() - new_labels.keys()
    merged = []
    old_events = {r["eventId"]: r for r in before["evaluatedEvents"]}
    for new in after["evaluatedEvents"]:
        old = old_events[new["eventId"]]
        record = {"eventId": new["eventId"], "companiesBefore": old["companies"], "companiesAfter": new["companies"],
                  "hitsBefore": old["hits"], "hitsAfter": new["hits"]}
        for key in ["modelAuc", "distanceAuc", "logisticAuc"]:
            record[key + "Before"] = old[key]
            record[key + "After"] = new[key]
            record[key + "Change"] = new[key] - old[key]
        merged.append(record)
    report = {"beforeModelCommit": BEFORE_COMMIT, "originalSourceNames": len(classes.rows),
              "currentCanonicalGroups": len(classes.groups), "sourceNameVariantsCombined": len(classes.rows) - len(classes.groups),
              "normalizedNamesBefore": len({company_key(n) for n in classes.rows}),
              "additionalCurrentIdentityMerges": len({company_key(n) for n in classes.rows}) - len(classes.groups),
              "modelCompanyIdsBefore": len({r["companyId"] for r in old_features}),
              "modelCompanyIdsAfter": len({r["companyId"] for r in new_features}),
              "companyEventRowsBefore": len(old_features), "companyEventRowsAfter": len(new_features),
              "withinEventDuplicatesRemoved": len(old_features) - len(new_features),
              "unchangedCommonStockLabels": len(common), "additionalObservedLabels": len(new_labels.keys() - old_labels.keys()),
              "changedCommonCarsOrHits": 0, "events": merged, "overallBefore": before["overall"], "overallAfter": after["overall"],
              "cautions": ["AUC changes include increased observation coverage and updated dated filing selection through inferred aliases, not just spelling cleanup.",
                           "No old company/event duplicate ticker labels were present; inferred aliases primarily align company identities across years.",
                           "Model-provided display classifications are not used as pre-event model product features.",
                           "The approved Unimicron correction and pre-2017 Mitsumi/Minebea separation prevent false issuer merges.",
                           "No hyperparameters or metric exclusions were tuned using the comparison. Small hit counts and retrospective inferred identities limit conclusions."]}
    output = ROOT / "data/review"
    (output / "company_merge_comparison.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with (output / "company_merge_comparison.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(merged[0]))
        writer.writeheader()
        writer.writerows(merged)
    lines = ["# Canonical-company retrain versus the original AUC audit", "",
             "Values below are before → after. Distance and logistic baselines are separately named.", "",
             "| Event | Companies | Hits | Model AUC | Distance AUC | Logistic AUC |", "|---|---:|---:|---:|---:|---:|"]
    for r in merged:
        lines.append(f"| {r['eventId']} | {r['companiesBefore']} → {r['companiesAfter']} | {r['hitsBefore']} → {r['hitsAfter']} | {r['modelAucBefore']:.4f} → {r['modelAucAfter']:.4f} | {r['distanceAucBefore']:.4f} → {r['distanceAucAfter']:.4f} | {r['logisticAucBefore']:.4f} → {r['logisticAucAfter']:.4f} |")
    lines += ["", f"The supplied {report['originalSourceNames']} names become {report['currentCanonicalGroups']} current canonical groups: {report['sourceNameVariantsCombined']} spelling/name variants are combined, including {report['additionalCurrentIdentityMerges']} additional identities beyond prior normalization.", "",
              f"Historical model identities go from {report['modelCompanyIdsBefore']} to {report['modelCompanyIdsAfter']}; dated Mitsumi/Minebea separation is retained. Company/event rows remain {report['companyEventRowsAfter']}, so {report['withinEventDuplicatesRemoved']} same-event company rows were removed. The original audit already found no repeated ticker/event labels.", "",
              f"All {len(common)} original observed CARs and hit flags are unchanged. {report['additionalObservedLabels']} previously unresolved company/event labels become observable through explicit aliases. Model classes fill display values only; financial/product features still require dated public reports.", ""]
    for label, key in [("Model", "auc"), ("Distance", "distanceAuc"), ("Logistic", "baselineAuc")]:
        lines.append(f"{label} pooled AUC: {before['overall'][key]:.4f} → {after['overall'][key]:.4f}.")
    lines += ["", "Both 2011 events remain excluded from metrics because they have no supplier hits. Their company predictions and CARs are still exported.", ""]
    lines += ["- " + text for text in report["cautions"]]
    lines += ["", "The original check is `auc_audit.md`; the new leakage/replay check is `auc_after_merge.md`. Full numeric changes and counts are in the corresponding CSV/JSON artifacts."]
    (output / "company_merge_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "events"}, indent=2))
    return report


if __name__ == "__main__":
    compare()
