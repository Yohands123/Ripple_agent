import copy
import json
from pathlib import Path

import pytest

from pipeline.backbone import dms, nearest_gateway
from pipeline.export import build_bundle, write_bundle
from pipeline.sea_routes import WaterRouter, distance_km
from pipeline.validate import validate_folder

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bundle():
    return build_bundle()


def test_wpi_coordinate_conversion_rejects_unrecognized_values():
    assert dms('79\ufffd34\'00"W') == pytest.approx(-79 - 34 / 60)
    assert dms('20\ufffd55\'00"N') == pytest.approx(20 + 55 / 60)
    with pytest.raises(ValueError):
        dms("unknown")


def test_water_mesh_routes_around_land_and_crosses_dateline_by_short_arc():
    countries = {"features": [{"geometry": {"type": "Polygon", "coordinates": [[[-1, -2], [1, -2], [1, 2], [-1, 2], [-1, -2]]]}}]}
    router = WaterRouter(countries, step=1)
    path = router.route([-4, 0], [4, 0])
    assert max(abs(p[1]) for p in path) > 2
    from pipeline.audit_backbone import crosses_land
    assert not any(crosses_land(a, b, router.land) for a, b in zip(path, path[1:]))
    crossing = router.route([179, 20], [-179, 20])
    assert sum(distance_km(a, b) for a, b in zip(crossing, crossing[1:])) < 250


def test_all_requested_reference_places_have_sources_and_null_unknown_tiers(bundle):
    network = bundle["network.json"]
    nodes = {n["id"]: n for n in network["nodes"] if n["layer"] == "backbone"}
    assert len([n for n in nodes.values() if not n.get("waypoint")]) == 55
    assert len([n for n in nodes.values() if n.get("waypoint")]) == 2
    assert {n["salesRegion"] for n in nodes.values() if n["kind"] == "sales_region"} == {"Americas", "Europe", "Greater China", "Japan", "Rest of Asia Pacific"}
    for key in ["apple-park", "assembly-zhengzhou", "assembly-shenzhen", "assembly-chennai", "assembly-bengaluru", "assembly-northern-vietnam", "suez", "panama", "malacca", "bab-el-mandeb", "taiwan-strait"]:
        assert nodes["backbone-" + key]["sources"]
    for node in nodes.values():
        assert node["historicalPresenceAsserted"] is False
        assert node["referenceAsOf"] == "2026-10-14"
        assert "companyId" not in node and node["ticker"] is None
        assert node["tier"] == (4 if node["partType"] == "assembly" else None)


def test_supplier_access_uses_each_site_once_and_really_selects_nearest_curated_gateway(bundle):
    for entry in bundle["scenarios/index.json"]:
        network = bundle["networks/" + entry["id"] + ".json"]
        sites = [n for n in network["nodes"] if n["layer"] == "supplier"]
        gateways = [n for n in network["nodes"] if n["layer"] == "backbone" and n["kind"] in {"port", "airport"}]
        links = [e for e in network["edges"] if e["layer"] == "supplier_access"]
        assert len(links) == len(sites) == len({e["from"] for e in links})
        by_site = {e["from"]: e for e in links}
        for site in sites:
            edge = by_site[site["id"]]
            target = nearest_gateway(site, gateways)
            assert edge["to"] == target["id"]
            assert edge["carriesTier"] == site["tier"]
            assert edge["distanceKm"] == pytest.approx(distance_km((site["lon"], site["lat"]), (target["lon"], target["lat"])), abs=0.000501)
            assert edge["status"] == "inferred" and edge["routingVerified"] is False


def test_every_scenario_has_a_sourced_hit_node_and_nonoverlapping_inferred_exposures(bundle):
    for entry in bundle["scenarios/index.json"]:
        scenario = bundle["scenarios/" + entry["id"] + ".json"]
        network = bundle[scenario["networkPath"]]
        nodes = {n["id"]: n for n in network["nodes"]}
        edges = {e["id"]: e for e in network["edges"]}
        assert scenario["shock"]["nodeIds"]
        assert all(nodes[n]["layer"] == "backbone" and nodes[n]["sources"] for n in scenario["shock"]["nodeIds"])
        assert scenario["shock"]["capacityLoss"] is None
        assert scenario["affectedRoutesStatus"] == "inferred" and scenario["affectedRoutesSources"]
        routes = scenario["affectedRoutes"]
        assert routes["blocked"]
        assert not set(routes["blocked"]) & (set(routes["detour"]) | set(routes["expedited"]))
        assert all(edges[e]["mode"] == "air" for e in routes["expedited"])
        if entry["id"] == "russia-2022":
            assert routes["detour"] == routes["expedited"] == []
        else:
            assert routes["detour"] and routes["expedited"]


def test_cape_alternatives_preserve_origins_and_destinations_and_avoid_the_blocked_chokepoints(bundle):
    for event in ["suez-2021", "red-sea-2023"]:
        scenario = bundle[f"scenarios/{event}.json"]
        edges = {e["id"]: e for e in bundle[scenario["networkPath"]]["edges"]}
        assert len(scenario["affectedRoutes"]["blocked"]) == len(scenario["affectedRoutes"]["detour"]) == 5
        for identifier in scenario["affectedRoutes"]["detour"]:
            alternative = edges[identifier]
            original = edges[alternative["alternativeTo"]]
            assert (alternative["from"], alternative["to"]) == (original["from"], original["to"])
            assert not {"backbone-suez", "backbone-bab-el-mandeb"} & set(alternative["viaNodeIds"])
            assert min(p[1] for p in alternative["via"]) <= -35
            assert min(p[1] for p in original["via"]) >= 0  # No accidental Cape/Sunda diversion.


def test_geometry_audit_records_no_unexpected_land_crossings():
    report = json.loads((ROOT / "data/review/backbone_audit.json").read_text(encoding="utf-8"))
    assert len(report["seaRoutes"]) == 30
    assert report["unexpectedLandCrossings"] == 0
    assert all(r["invariantSatisfied"] for r in report["protectedArtifacts"])


@pytest.mark.parametrize("mutation,expected", [
    ("context_prediction", "supplier prediction cannot attach to backbone"),
    ("transit", "dangling route transit"),
    ("known_route", "unverified backbone route must be inferred"),
    ("blocked_detour", "blocked route cannot be an available alternative"),
    ("invented_2011_site", "no invented sites"),
    ("supply_route", "affectedRoutes must reference physical route edges"),
])
def test_reference_layer_cannot_turn_into_observed_supplier_data(bundle, tmp_path, mutation, expected):
    candidate = copy.deepcopy(bundle)
    scenario = candidate["scenarios/suez-2021.json"]
    network = candidate[scenario["networkPath"]]
    edge = next(e for e in network["edges"] if e["mode"] == "sea")
    if mutation == "context_prediction":
        scenario["predictions"][0]["nodeId"] = "backbone-apple-park"
    elif mutation == "transit":
        edge["viaNodeIds"].append("absent-waterway")
    elif mutation == "known_route":
        edge["status"] = "known"
    elif mutation == "blocked_detour":
        scenario["affectedRoutes"]["detour"].append(scenario["affectedRoutes"]["blocked"][0])
    elif mutation == "supply_route":
        scenario["affectedRoutes"]["blocked"].append(next(e["id"] for e in network["edges"] if e.get("relation") == "supply"))
    else:
        candidate["networks/japan-2011.json"]["nodes"].append(copy.deepcopy(network["nodes"][0]))
    write_bundle(candidate, tmp_path)
    assert any(expected in error for error in validate_folder(tmp_path))
