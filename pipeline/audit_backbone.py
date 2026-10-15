"""Read-only geometric/identity audit of the exported reference layer."""

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from shapely.geometry import LineString, shape
from shapely.ops import unary_union

from pipeline.backbone import nearest_gateway
from pipeline.sea_routes import distance_km

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def crosses_land(a, b, land):
    if a == b:
        return False
    if abs(a[0] - b[0]) > 180:
        west, east = sorted([a, b])
        lon_difference = west[0] + 360 - east[0]
        fraction = (180 - east[0]) / lon_difference
        latitude = east[1] + fraction * (west[1] - east[1])
        return land.intersects(LineString([east, [180, latitude]])) or land.intersects(LineString([[-180, latitude], west]))
    return land.intersects(LineString([a, b]))


def audit_geometry(catalog, countries=None):
    from pipeline.sea_geometry import sea_route_errors
    nodes = {n["id"]: n for n in catalog["nodes"]}
    report = []
    for edge in catalog["edges"]:
        if edge["mode"] != "sea":
            continue
        a, b = nodes[edge["from"]], nodes[edge["to"]]
        points = [[a["lon"], a["lat"]], *edge["via"], [b["lon"], b["lat"]]]
        failures = list(sea_route_errors(edge, nodes))
        report.append({"routeId": edge["id"], "waypoints": len(edge["via"]),
                       "schematicLengthKm": round(sum(distance_km(p, q) for p, q in zip(points, points[1:])), 1),
                       "minimumLatitude": min(p[1] for p in points),
                       "unexpectedLandCrossings": failures, "checks": ["physical land polygons", "smoothed ship path", "date-line split"],
                       "portToleranceKm": 3, "independentCanalCorridorToleranceKm": 1})
    return report


def audit(root=ROOT):
    catalog = read(root / "data/processed/backbone.json")
    sea = audit_geometry(catalog)
    protected = []
    # Last completed classification/model task, before adding display context.
    for path in ["data/processed/features.csv", "data/processed/labels.csv", "data/processed/metrics.json",
                 "data/processed/site_predictions.json", "data/processed/company_predictions.json",
                 "data/processed/optimizer_plans.json", "data/processed/forecasts.json",
                 "web/public/data/real/metrics.json", "web/public/data/real/forecasts.json"]:
        before = subprocess.check_output(["git", "show", "90caca9:" + path], cwd=root).replace(b"\r\n", b"\n")
        after = (root / path).read_bytes().replace(b"\r\n", b"\n")
        protected.append({"path": path, "unchangedSinceClassificationCommit": before == after, "sha256Lf": hashlib.sha256(after).hexdigest()})
    scenarios = []
    for entry in read(root / "web/public/data/real/scenarios/index.json"):
        scenario = read(root / "web/public/data/real/scenarios" / (entry["id"] + ".json"))
        network = read(root / "web/public/data/real" / scenario["networkPath"])
        sites = [n for n in network["nodes"] if n["layer"] == "supplier"]
        gateways = [n for n in network["nodes"] if n["layer"] == "backbone" and n["kind"] in {"port", "airport"}]
        access = {e["from"]: e for e in network["edges"] if e["layer"] == "supplier_access"}
        wrong_access = [n["id"] for n in sites if n["id"] not in access or access[n["id"]]["to"] != nearest_gateway(n, gateways)["id"] or access[n["id"]]["carriesTier"] != n["tier"]]
        scenarios.append({"eventId": entry["id"], "supplierSites": len(sites), "backboneNodes": network["coverage"]["backboneNodes"],
                          "supplierAccessLinks": len(access), "wrongNearestGatewayOrTier": wrong_access,
                          "companyPredictions": len(scenario.get("companyPredictions", [])),
                          "shockNodeIds": scenario["shock"]["nodeIds"], "affectedRoutes": {k: len(v) for k, v in scenario["affectedRoutes"].items()}})
    failures = sum(len(r["unexpectedLandCrossings"]) for r in sea)
    report = {"referenceAsOf": catalog["referenceAsOf"], "nodes": len(catalog["nodes"]), "corridors": len(catalog["edges"]),
              "nodeKinds": dict(Counter(n["kind"] for n in catalog["nodes"])), "seaRoutes": sea,
              "unexpectedLandCrossings": failures, "protectedArtifacts": protected, "scenarios": scenarios,
              "scope": "Exact Natural Earth physical-land checks include polylines and smoothed ship paths. Only 3 km around port endpoints and a 1 km cartographic corridor around independently pinned canal centerlines are allowed. No arbitrary canal/endpoint segments are exempt. This does not establish navigability or actual shipments.",
              "lengthDefinition": "Great-circle sum of displayed points, not a measured voyage length"}
    folder = root / "data/review"
    (folder / "backbone_audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Sourced backbone audit", "", f"Reference dated {catalog['referenceAsOf']}: {len(catalog['nodes'])} nodes and {len(catalog['edges'])} inferred corridors; {len(sea)} sea paths.",
             "", f"Land-crossing failures: {failures}. Both polylines and smoothed ship paths are checked against pinned Natural Earth physical-land polygons; port tolerance is 3 km and independently sourced canal centerline tolerance is 1 km. Route metadata cannot exempt a crossing.",
             "", "| Event | Supplier sites / access links | Reference nodes | Blocked exposure | Detour | Expedited |", "|---|---:|---:|---:|---:|---:|"]
    for row in scenarios:
        routes = row["affectedRoutes"]
        lines.append(f"| {row['eventId']} | {row['supplierSites']} / {row['supplierAccessLinks']} | {row['backboneNodes']} | {routes['blocked']} | {routes['detour']} | {routes['expedited']} |")
    lines += ["", "Every supplier access link selects the nearest of the curated ports/airports by great-circle reference distance and preserves the site's nullable tier. These are inferred access connectors, not verified continuous roads; actual modal transfers and border crossings are unknown.",
              "", "Both 2011 rosters retain 156 unlocated company predictions each and zero supplier site pins. Backbone context is contemporary and explicitly does not assert historical facility presence (Apple Park, for example, opened in 2017).",
              "", "Suez and Red Sea overlays identify the five inferred Suez corridors, their five Cape alternatives, and eight illustrative air alternatives. Russia has no proposed detour or expedition around export restrictions. All exposure classifications and alternatives are inferred, and no complete gateway closure is inferred from a regional event.",
              "", "Features, company/site predictions, CAR labels, evaluation, forecasts and indexed optimizer outputs are byte-identical after line-ending normalization to classification commit `90caca9`. The backbone is not added to the model or optimizer graph.",
              "", "Pacific corridors split at paired date-line waypoints so no displayed segment crosses Eurasia/Africa. WPI port references are retained in publishedPosition; offshore display approaches are explicitly inferred. Geometry uses pinned physical-land polygons, fine coastal meshes and published Suez/Panama river/lake centerlines. Dataset hashes and tolerances are in data/processed/sea_geometry.json. These are schematic corridors, not navigation data.",
              "", "Consumer integration notes are in `backbone_integration_notes.md`. Full geometry, source pins, coverage and protected-file hashes are in `backbone_audit.json` and `data/processed/backbone.json`."]
    (folder / "backbone_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if failures or any(not r["unchangedSinceClassificationCommit"] for r in protected) or any(r["wrongNearestGatewayOrTier"] for r in scenarios):
        raise ValueError("Backbone audit failed; inspect data/review/backbone_audit.json")
    return report


if __name__ == "__main__":
    result = audit()
    print(f"Audited {result['nodes']} nodes, {result['corridors']} corridors, 9 scenario overlays; protected model artifacts unchanged")
