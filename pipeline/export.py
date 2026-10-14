"""Export processed public evidence using the user-approved M7 contract extensions.

Production export validates the complete bundle before writing any web files.
The review switch writes a copy in data/review/export_preview/.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.validate import validate_folder

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "data/review/export_preview"
REAL = ROOT / "web/public/data/real"
OUTCOME = "Company market-model CAR over trading days 0 to +10; hit when t < -1.96. Not a measurement of factory damage or production loss."


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def citations(*groups):
    return list({(s["title"], s["url"]): {"title": s["title"], "url": s["url"]} for group in groups for s in group}.values())


def build_bundle(root=ROOT):
    """Build deterministic documents using processed inputs, without downloading."""
    events = list(csv.DictReader((root / "data/events.csv").open(encoding="utf-8")))
    features = {(r["eventId"], r["companyId"]): r for r in csv.DictReader((root / "data/processed/features.csv").open(encoding="utf-8"))}
    metadata = read_json(root / "data/processed/feature_metadata.json")
    provenance = {(r["eventId"], r["companyId"]): r["attributeSources"] for r in metadata["provenance"]}
    sites = read_json(root / "data/processed/site_predictions.json")["predictions"]
    tickers = defaultdict(list)
    for record in read_json(root / "data/processed/ticker_map.json")["mapped"]:
        tickers[record["ticker"]].extend(record["sources"])
    by_event = defaultdict(list)
    for site in sites:
        by_event[site["eventId"]].append(site)
    documents, index = {}, []
    for event in events:
        identifier, year = event["id"], int(event["snapshotYear"])
        nodes, predictions, actual = [], [], []
        for site in sorted(by_event[identifier], key=lambda r: r["nodeId"]):
            if site["snapshotYear"] != year:
                raise ValueError(f"{identifier}: prediction uses another Supplier List year")
            key = (identifier, site["companyId"])
            attributes, evidence = features[key], provenance[key]
            financial_sources = [v["source"] for v in evidence.values() if "source" in v]
            nodes.append({
                "id": site["nodeId"], "name": f"{site['supplier']} — {site['location']}",
                "kind": "supplier_major", "tier": None,
                "lon": site["lon"], "lat": site["lat"], "precision": site["precision"],
                "region": site["location"], "ticker": attributes["ticker"] or None,
                "partType": None if attributes["part_type"] == "unknown" else attributes["part_type"],
                "appleRevenueShare": float(attributes["apple_revenue_share"]) if attributes["apple_revenue_share"] else None,
                "sources": citations(site["sources"], financial_sources, tickers[attributes["ticker"]]),
                "companyId": site["companyId"], "locationRole": site["locationRole"],
                "attributeSources": evidence,
                "partTypeScope": "Company product category, not an Apple-specific bill of materials",
                "tierBasis": "Production tier is not disclosed in the Supplier List",
            })
            prediction = {k: site[k] for k in ["nodeId", "pHit", "ciLow", "ciHigh", "lowConfidence", "shap", "shapBaseValue", "shapMeanRawScore", "predictionScope", "outcomeObservable"]}
            predictions.append(prediction)
            if site["actual"] is not None:
                actual.append({"nodeId": site["nodeId"], **site["actual"], "scope": "Company-level CAR shared by disclosed sites"})
        if not nodes:
            raise ValueError(f"{identifier}: no geocoded predictions")
        network_path = f"networks/{identifier}.json"
        documents[network_path] = {
            "snapshotYear": year, "sampleData": False, "nodes": nodes, "edges": [],
            "eventId": identifier, "asOfDate": event["knowledgeCutoffDate"],
            "scope": "Disclosed supplier locations. Physical transport links and production tiers are unavailable.",
            "cohortBasis": metadata["retrospectiveScope"],
            "coverage": {"matchedLocations": len(nodes), "manufacturingLocations": sum(n["locationRole"] == "manufacturing" for n in nodes)},
        }
        documents[f"scenarios/{identifier}.json"] = {
            "id": identifier, "title": event["title"], "type": event["type"],
            "start": event["start"], "end": event["end"], "snapshotYear": year,
            "sampleData": False, "networkPath": network_path,
            "shock": {"nodeIds": [], "capacityLoss": None, "location": {
                "lon": float(event["lon"]), "lat": float(event["lat"]),
                "precision": event["locationPrecision"], "basis": event["locationBasis"],
                "sources": json.loads(event["sources"]),
            }},
            "headline": event["title"] + ". Supplier stock responses are shown; production losses are unknown.",
            "predictions": predictions, "actual": actual, "options": [], "quota": None,
            "money": {"coinUsd": 500000000, "revenueAtRisk": None, "delayedShare": None, "assumption": False},
            "affectedRoutes": {"blocked": [], "detour": [], "expedited": []}, "sensitivity": [],
            "outcomeDefinition": OUTCOME,
            "unknowns": ["Apple production capacity loss", "Production quota and recovery plan", "Apple revenue at risk and delayed share", "Physical supplier transport routes", "Production tier"],
            "dateBasis": event["dateBasis"], "endBasis": event["endBasis"],
            "sources": json.loads(event["sources"]),
        }
        index.append({key: event[key] for key in ["id", "title", "type", "start"]})
    default = "suez-2021" if "networks/suez-2021.json" in documents else events[0]["id"]
    documents["network.json"] = documents[f"networks/{default}.json"]
    documents["scenarios/index.json"] = index
    documents["metrics.json"] = read_json(root / "data/processed/metrics.json")
    return documents


def write_bundle(documents, folder):
    for relative, document in documents.items():
        path = folder / relative
        if not path.resolve().is_relative_to(folder.resolve()):
            raise ValueError(f"Unsafe export path: {relative}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")


def export(review=False, root=ROOT):
    documents = build_bundle(root)
    # Validate a complete candidate before the loader can see any real files.
    raw = root / "data/raw"
    raw.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="export-check-", dir=raw) as temporary:
        stage = Path(temporary)
        write_bundle(documents, stage)
        errors = validate_folder(stage)
    if errors:
        raise ValueError("Export withheld: " + "; ".join(errors[:8]) + (f"; {len(errors)} validation errors total" if len(errors) > 8 else ""))
    destination = root / ("data/review/export_preview" if review else "web/public/data/real")
    write_bundle(documents, destination)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", action="store_true", help="Write a review copy in data/ instead of the app folder")
    args = parser.parse_args()
    try:
        destination = export(args.review)
    except ValueError as exc:
        parser.exit(1, str(exc) + "\n")
    print(f"Exported to {destination}" + (" (review copy)" if args.review else ""))
