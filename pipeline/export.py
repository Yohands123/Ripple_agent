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
from pipeline.tiers import inferred_tier
from pipeline.company_registry import registry
from pipeline.backbone import attach_backbone

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "data/review/export_preview"
REAL = ROOT / "web/public/data/real"
OUTCOME = "Company market-model CAR over trading days 0 to +10; hit when t < -1.96. Not a measurement of factory damage or production loss."


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def citations(*groups):
    return list({(s["title"], s["url"]): {"title": s["title"], "url": s["url"]} for group in groups for s in group}.values())


def tier_unknown_text(nodes):
    sites = [n for n in nodes if n.get("layer") == "supplier"]
    if not sites:
        return "Production tier for an unknown share of sites (supplier locations undisclosed)"
    missing = sum(n.get("tier") is None for n in sites)
    percent = f"{100 * missing / len(sites):.1f}".rstrip("0").rstrip(".")
    return f"Production tier for {percent}% of sites"


def unlocated_company(prediction, attributes, label=None):
    result = {k: prediction[k] for k in ["companyId", "supplier", "pHit", "ciLow", "ciHigh", "lowConfidence", "shap", "shapBaseValue", "shapMeanRawScore"]}
    result.update(ticker=attributes["ticker"] or None,
                  sources=citations(prediction["sources"], json.loads(attributes["sources"]), json.loads(label["sources"]) if label else []),
                  predictionScope="Company stock-response prediction; the roster discloses no manufacturing-site coordinates",
                  outcomeObservable=label is not None,
                  actual={"hit": label["hit"].lower() == "true", "car": float(label["car"])} if label else None)
    result.update({key: prediction[key] for key in ["predictionModel", "explanationMethod"] if key in prediction})
    return result


def build_bundle(root=ROOT):
    """Build deterministic documents using processed inputs, without downloading."""
    events = list(csv.DictReader((root / "data/events.csv").open(encoding="utf-8")))
    features = {(r["eventId"], r["companyId"]): r for r in csv.DictReader((root / "data/processed/features.csv").open(encoding="utf-8"))}
    metadata = read_json(root / "data/processed/feature_metadata.json")
    provenance = {(r["eventId"], r["companyId"]): r["attributeSources"] for r in metadata["provenance"]}
    sites = read_json(root / "data/processed/site_predictions.json")["predictions"]
    companies = read_json(root / "data/processed/company_predictions.json")["predictions"]
    with (root / "data/processed/labels.csv").open(encoding="utf-8") as handle:
        labels = {(r["eventId"], r["companyId"]): r for r in csv.DictReader(handle) if r["status"] == "ok" and r["role"] == "supplier"}
    tickers = defaultdict(list)
    for record in read_json(root / "data/processed/ticker_map.json")["mapped"]:
        tickers[record["ticker"]].extend(record["sources"])
    by_event = defaultdict(list)
    for site in sites:
        by_event[site["eventId"]].append(site)
    documents, index = {}, []
    plans_path = root / "data/processed/optimizer_plans.json"
    optimization_plans = read_json(plans_path) if plans_path.exists() else None
    backbone = read_json(root / "data/processed/backbone.json")
    minerals = read_json(root / "data/processed/minerals.json")
    from pipeline.mineral_routes import attach_minerals
    from pipeline.mineral_scenario import build_scenario as mineral_scenario
    if optimization_plans is not None and optimization_plans.get("reviewOnly") is not False:
        raise ValueError("Review-only optimizer output cannot be published")
    for event in events:
        identifier, year = event["id"], int(event["snapshotYear"])
        cohort = json.loads(event["cohort"]) if event.get("cohort") else {}
        company_only = cohort.get("locationCoverage") == "company-only"
        if company_only and cohort.get("companyOnlyExportApproved") is not True:
            raise ValueError(f"{identifier}: company-only export requires the M10 decision")
        nodes, predictions, actual = [], [], []
        for site in sorted(by_event[identifier], key=lambda r: r["nodeId"]):
            if site["snapshotYear"] != year:
                raise ValueError(f"{identifier}: prediction uses another Supplier List year")
            key = (identifier, site["companyId"])
            attributes, evidence = features[key], provenance[key]
            part_type = None if attributes["part_type"] == "unknown" else attributes["part_type"]
            financial_sources = [v["source"] for v in evidence.values() if "source" in v]
            nodes.append({
                "id": site["nodeId"], "name": f"{site['supplier']} — {site['location']}",
                "kind": "supplier_major", **registry().classify(site["supplier"], part_type, inferred_tier(part_type)),
                "lon": site["lon"], "lat": site["lat"], "precision": site["precision"],
                "region": site["location"], "ticker": attributes["ticker"] or None,
                "appleRevenueShare": float(attributes["apple_revenue_share"]) if attributes["apple_revenue_share"] else None,
                "sources": citations(site["sources"], financial_sources, tickers[attributes["ticker"]], [registry().rows[site["supplier"]]["correction"]["source"]] if registry().rows.get(site["supplier"], {}).get("correction") else []),
                "companyId": site["companyId"], "locationRole": site["locationRole"],
                "sourceCompany": site["supplier"], "canonicalCompany": site["canonicalCompany"], "supplierAliases": site["supplierAliases"],
                "attributeSources": evidence,
                "partTypeScope": "Company product category, not an Apple-specific bill of materials",
            })
            prediction = {k: site[k] for k in ["nodeId", "pHit", "ciLow", "ciHigh", "lowConfidence", "shap", "shapBaseValue", "shapMeanRawScore", "predictionScope", "outcomeObservable"]}
            prediction.update({key: site[key] for key in ["predictionModel", "explanationMethod"] if key in site})
            predictions.append(prediction)
            if site["actual"] is not None:
                actual.append({"nodeId": site["nodeId"], **site["actual"], "scope": "Company-level CAR shared by disclosed sites"})
        if not nodes and not company_only:
            raise ValueError(f"{identifier}: no geocoded predictions")
        network_path = f"networks/{identifier}.json"
        documents[network_path] = {
            "snapshotYear": year, "sampleData": False, "nodes": nodes, "edges": [],
            "eventId": identifier, "asOfDate": event["knowledgeCutoffDate"],
            "scope": "Company roster; manufacturing locations undisclosed" if company_only else "Disclosed supplier locations. Physical transport links and production tiers are unavailable.",
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
        if cohort:
            documents[f"scenarios/{identifier}.json"]["cohort"] = cohort
            documents[network_path]["cohort"] = cohort
        if company_only:
            company_predictions = [unlocated_company(p, features[(identifier, p["companyId"])], labels.get((identifier, p["companyId"]))) for p in companies if p["eventId"] == identifier]
            if not company_predictions or nodes:
                raise ValueError("Company-only cohort must have company predictions and no invented mapped locations")
            documents[f"scenarios/{identifier}.json"]["companyPredictions"] = company_predictions
            documents[network_path]["coverage"].update(unlocatedCompanies=len(company_predictions), locationCoverage="undisclosed")
        if optimization_plans is not None:
            if identifier not in optimization_plans["scenarios"]:
                raise ValueError(f"{identifier}: optimizer plan missing; rerun for the full event set")
            plan = optimization_plans["scenarios"][identifier]
            if plan["optimization"]["inputRanges"].get("approved") is not True:
                raise ValueError("Unapproved optimizer assumptions cannot be published")
            documents[f"scenarios/{identifier}.json"].update(plan)
        attach_backbone(documents[network_path], documents[f"scenarios/{identifier}.json"], event, backbone)
        attach_minerals(documents[network_path], minerals)
        scenario = documents[f"scenarios/{identifier}.json"]
        scenario["unknowns"] = [tier_unknown_text(documents[network_path]["nodes"]) if value.casefold().startswith("production tier") else value for value in scenario["unknowns"]]
        index.append({key: event[key] for key in ["id", "title", "type", "start"]})
    mineral_network, mineral_event = mineral_scenario(backbone, minerals)
    documents[mineral_event['networkPath']] = mineral_network
    documents['scenarios/'+mineral_event['id']+'.json'] = mineral_event
    index.append({key:mineral_event[key] for key in ['id','title','type','start']})
    default = "suez-2021" if "networks/suez-2021.json" in documents else events[0]["id"]
    documents["network.json"] = documents[f"networks/{default}.json"]
    documents["scenarios/index.json"] = index
    documents["metrics.json"] = read_json(root / "data/processed/metrics.json")
    forecasts = root / "data/processed/forecasts.json"
    if forecasts.exists():
        documents["forecasts.json"] = read_json(forecasts)
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
