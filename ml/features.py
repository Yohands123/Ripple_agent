"""Build timestamp-filtered attributes and a sourced disclosure-graph topology."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import defaultdict, deque
from pathlib import Path

from shapely.geometry import Point, shape

from pipeline.event_study import supplier_mapping_index, listing_for_event
from pipeline.prices import company_key

ROOT = Path(__file__).resolve().parents[1]
NUMERIC = ["hops_from_shock", "distance_km", "location_share_in_zone", "apple_revenue_share", "sourcing_hhi", "chokepoint_dependence", "size"]


def company_id(name: str) -> str:
    return "supplier-" + hashlib.sha256(company_key(name).encode()).hexdigest()[:16]


def node_id(row: dict) -> str:
    identity = "\0".join([company_key(row["supplier"]), row["location"].casefold(), row["country"], row["locationRole"]])
    return "location-" + hashlib.sha256(identity.encode()).hexdigest()[:16]


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (lon1, lat1, lon2, lat2))
    term = math.sin((lat2 - lat1) / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2)**2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1.0, max(0.0, term))))


def disclosed_hhi(locations: list[dict]) -> float | None:
    if not locations:
        return None
    counts = defaultdict(int)
    for row in locations:
        counts[row["country"]] += 1
    return sum((count / len(locations))**2 for count in counts.values())


def latest_profile(profiles: list[dict], name: str, event_date: str, mapping: dict) -> dict | None:
    keys = {company_key(name)}
    # Equality through a verified ticker/issuer alias permits the old legal
    # name's report to be used after a rename, without inventing subsidiaries.
    target = {r["ticker"] for r in mapping.get(company_key(name), [])}
    candidates = [p for p in profiles if p.get("filedOn") and p["filedOn"] < event_date
                  and (company_key(p["supplier"]) in keys or target & {r["ticker"] for r in mapping.get(company_key(p["supplier"]), [])})]
    return max(candidates, key=lambda p: (p["filedOn"], p.get("reportDate") or "")) if candidates else None


def latest_assets(document: dict, event_date: str) -> dict | None:
    facts = document.get("facts", {}).get("us-gaap", {}).get("Assets", {}).get("units", {}).get("USD", [])
    eligible = [r for r in facts if r.get("filed", "9999") < event_date and r.get("end", "9999") < event_date
                and r.get("form") in {"10-K", "10-Q", "20-F", "40-F"} and isinstance(r.get("val"), (float, int))
                and math.isfinite(r["val"]) and r["val"] > 0]
    return max(eligible, key=lambda r: (r["end"], r["filed"])) if eligible else None


def chokepoint_evidence(name: str, event: dict, registry: dict) -> dict | None:
    matches = [entry for entry in registry["entries"] if company_key(entry["supplier"]) == company_key(name)
               and event["id"] in entry["eventIds"] and entry["availableOn"] < event["start"]]
    if not matches:
        return None
    record = max(matches, key=lambda r: r["availableOn"])
    if not isinstance(record.get("depends"), bool) or not record.get("sources"):
        raise ValueError("Chokepoint evidence requires an explicit boolean and public sources")
    return record


def zone_overlap(row: dict, event: dict, provinces: dict) -> bool | None:
    zone = json.loads(event["zone"])
    if not zone["country"] or row["country"] != zone["country"]:
        return False
    if not zone["names"]:
        return True
    if any(re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", row["location"], re.I) for name in zone["names"]):
        return True
    if row["precision"] == "country" or row["matchStatus"] != "matched":
        return None
    if row["precision"] == "province":
        polygon = provinces.get(str(row["geoId"]))
        if polygon is not None and polygon.covers(Point(float(event["lon"]), float(event["lat"]))):
            return None  # Province contains the city/epicenter, site is unknown.
    return False


def breadth_first(adjacency: dict, start: str) -> dict[str, int]:
    distances, queue = {start: 0}, deque([start])
    while queue:
        current = queue.popleft()
        for neighbor in adjacency.get(current, []):
            if neighbor not in distances:
                distances[neighbor] = distances[current] + 1
                queue.append(neighbor)
    return distances


def build() -> dict:
    events = list(csv.DictReader((ROOT / "data/events.csv").open(encoding="utf-8")))
    profiles = json.loads((ROOT / "data/processed/supplier_profiles.json").read_text(encoding="utf-8"))["profiles"]
    historical = ROOT / "data/processed/historical_profiles.json"
    if historical.exists():
        profiles.extend(json.loads(historical.read_text(encoding="utf-8"))["profiles"])
    ticker_map = json.loads((ROOT / "data/processed/ticker_map.json").read_text(encoding="utf-8"))
    mappings = supplier_mapping_index(ticker_map)
    route_registry = json.loads((ROOT / "data/sources/chokepoint_evidence.json").read_text(encoding="utf-8"))
    geo_config = json.loads((ROOT / "data/sources/natural_earth.json").read_text(encoding="utf-8"))
    admin = next(r for r in geo_config["datasets"] if r["id"] == "admin1")
    document = json.loads((ROOT / "data/raw/natural_earth" / admin["file"]).read_text(encoding="utf-8"))
    polygons = {str(r["properties"]["ne_id"]): shape(r["geometry"]) for r in document["features"]}
    manifests = {r["snapshotYear"]: r for r in json.loads((ROOT / "data/interim/supplier_list_manifest.json").read_text(encoding="utf-8"))["editions"]}
    facts, rows, sites, graphs, provenance = {}, [], [], [], []
    graph_dir = ROOT / "data/raw/disclosure_graphs"
    graph_dir.mkdir(parents=True, exist_ok=True)
    for event in events:
        year = int(event["snapshotYear"])
        cutoff = event.get("knowledgeCutoffDate") or event["start"]
        locations = list(csv.DictReader((ROOT / f"data/interim/geocoded_{year}.csv").open(encoding="utf-8")))
        companies = defaultdict(list)
        for row in locations:
            companies[company_id(row["supplier"])].append(row)
        adjacency = defaultdict(set)
        graph_nodes = [{"id": "apple-company", "kind": "customer", "sources": manifests[year]["sources"]},
                       {"id": event["id"], "kind": "shock", "sources": json.loads(event["sources"])}]
        graph_edges, overlaps = [], {}

        def connect(left, right, relation, status, sources):
            adjacency[left].add(right)
            adjacency[right].add(left)
            graph_edges.append({"from": left, "to": right, "relation": relation, "status": status, "sources": sources})

        for identifier, company_locations in companies.items():
            graph_nodes.append({"id": identifier, "kind": "supplier_company", "sources": manifests[year]["sources"]})
            connect(identifier, "apple-company", "listed procurement relationship", "known", manifests[year]["sources"])
            for location in company_locations:
                if not location["location"]:
                    continue  # A company roster does not disclose a physical site.
                site = node_id(location)
                source = json.loads(location["sources"])
                graph_nodes.append({"id": site, "kind": "disclosed_location", "sources": source})
                connect(identifier, site, "supplier's disclosed location", "known", source)
                overlap = zone_overlap(location, event, polygons) if location["locationRole"] == "manufacturing" else None
                overlaps[site] = overlap
                if overlap is True:
                    connect(event["id"], site, "geographic exposure proxy, not confirmed damage", "inferred", source + json.loads(event["sources"]))
        hops = breadth_first(adjacency, event["id"])
        path = graph_dir / f"{event['id']}.json"
        path.write_text(json.dumps({"sampleData": False, "scope": "Supplier disclosure graph; not a material-flow or transport network", "nodes": graph_nodes, "edges": graph_edges}) + "\n", encoding="utf-8")
        graphs.append({"eventId": event["id"], "file": str(path.relative_to(ROOT)).replace("\\", "/"), "nodes": len(graph_nodes), "edges": len(graph_edges),
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "geographicExposureEdges": sum(e["status"] == "inferred" for e in graph_edges)})
        for identifier, company_locations in companies.items():
            name = company_locations[0]["supplier"]
            manufacturing = [r for r in company_locations if r["locationRole"] == "manufacturing"]
            matched = [r for r in manufacturing if r["matchStatus"] == "matched"]
            distances = [haversine(float(r["lon"]), float(r["lat"]), float(event["lon"]), float(event["lat"])) for r in matched]
            classifications = [overlaps[node_id(r)] for r in manufacturing]
            lower = sum(v is True for v in classifications) / len(classifications) if classifications else None
            upper = sum(v is not False for v in classifications) / len(classifications) if classifications else None
            fraction = lower if lower == upper else None
            ticker_records = {r["ticker"]: r for r in mappings.get(company_key(name), [])}
            listing = next(iter(ticker_records.values())) if len(ticker_records) == 1 else {}
            listing = listing_for_event(listing, name, event["start"])
            profile = None if listing.get("mappingUnavailableReason") == "legacy_issuer_price_series_unverified" else latest_profile(profiles, name, cutoff, mappings)
            cik = listing.get("cik")
            asset_fact = None
            if cik:
                if cik not in facts:
                    fact_path = ROOT / f"data/raw/company_facts/CIK{cik:010d}.json"
                    facts[cik] = json.loads(fact_path.read_text(encoding="utf-8")) if fact_path.exists() else {}
                asset_fact = latest_assets(facts[cik], cutoff)
            source_list = list({(s["title"], s["url"]): s for loc in company_locations for s in json.loads(loc["sources"])}.values()) + json.loads(event["sources"])
            attribute_sources = {}
            route = chokepoint_evidence(name, {**event, "start": cutoff}, route_registry)
            if route:
                source_list.extend(route["sources"])
                attribute_sources["chokepoint_dependence"] = {"sources": route["sources"], "filedOn": route["availableOn"]}
            if profile:
                for field in ("partType", "appleRevenueShare"):
                    source = profile.get(field + "Source")
                    if source:
                        source_list.append(source)
                        attribute_sources[field] = {"source": source, "filedOn": profile["filedOn"]}
            if asset_fact:
                source = {"title": f"SEC company facts: total assets in USD, filed {asset_fact['filed']}", "url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"}
                source_list.append(source)
                attribute_sources["size"] = {"source": source, "filedOn": asset_fact["filed"], "periodEnd": asset_fact["end"], "assetsUsd": asset_fact["val"]}
            record = {"eventId": event["id"], "eventStart": event["start"], "financialCutoffDate": cutoff, "snapshotYear": year, "companyId": identifier, "supplier": name,
                      "ticker": listing.get("ticker", ""), "hops_from_shock": hops.get(identifier), "distance_km": min(distances) if distances else None,
                      "location_share_in_zone": fraction, "apple_revenue_share": profile.get("appleRevenueShare") if profile else None,
                      "part_type": profile.get("partType") or "unknown" if profile else "unknown", "sourcing_hhi": disclosed_hhi(manufacturing),
                      "chokepoint_dependence": int(route["depends"]) if route else None, "size": math.log(asset_fact["val"]) if asset_fact else None,
                      "locationShareLow": lower, "locationShareHigh": upper, "disclosedManufacturingLocations": len(manufacturing), "matchedManufacturingLocations": len(matched),
                      "sources": json.dumps(list({(s["title"], s["url"]): s for s in source_list}.values()), ensure_ascii=False)}
            rows.append(record)
            provenance.append({"eventId": event["id"], "companyId": identifier, "attributeSources": attribute_sources,
                               "chokepointStatus": "Verified pre-event disclosure" if route else "Unavailable: no verified transport-route dependence supplied", "locationShareBounds": [lower, upper] if lower is not None else None})
            for location in company_locations:
                if location["matchStatus"] == "matched":
                    sites.append({"eventId": event["id"], "snapshotYear": year, "companyId": identifier, "nodeId": node_id(location), "supplier": name,
                                  "location": location["location"], "country": location["country"], "locationRole": location["locationRole"], "precision": location["precision"],
                                  "lon": float(location["lon"]), "lat": float(location["lat"]), "sources": json.loads(location["sources"])})
    with (ROOT / "data/processed/features.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    metadata = {"sampleData": False, "numericFeatures": NUMERIC, "categoricalFeatures": ["part_type"], "rows": len(rows), "sites": sites, "graphs": graphs,
                "definitions": {"hops_from_shock": "Undirected hops in sourced supplier-location/customer disclosure graph with inferred geographic exposure edges; not transport/material-flow hops",
                                "distance_km": "Minimum haversine distance from matched manufacturing-location centroid to sourced shock anchor; headquarters are excluded",
                                "location_share_in_zone": "Share of disclosed manufacturing rows explicitly in named geographic proxy zone; null if source granularity leaves overlap unresolved, with bounds retained",
                                "apple_revenue_share": "Latest explicitly named Apple revenue disclosure from a report published before event",
                                "part_type": "Latest sourced company product category published before event; not an Apple-specific bill of materials",
                                "sourcing_hhi": "Country HHI of disclosed manufacturing-location row counts, not actual production/procurement shares; list granularity differs across years",
                                "chokepoint_dependence": "Unavailable without verified transport-route evidence; never silently assumed zero",
                                "size": "Natural log of reported total assets in USD, most recent period filed before event; unavailable currencies are not converted with invented rates"},
                "retrospectiveScope": "Supplier lists were published retrospectively. The two 2011 events use the approved January 2012 names-only roster approximation, with missing manufacturing geography. Financial attributes are publication-filtered; this is a retrospective backtest, not a real-time reconstruction.",
                "provenance": provenance}
    (ROOT / "data/processed/feature_metadata.json").write_text(json.dumps(metadata, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Features: {len(rows)} company/event rows, {len(sites)} matched location/event records")
    return metadata


if __name__ == "__main__":
    build()
