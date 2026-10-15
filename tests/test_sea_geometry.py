import json
from pathlib import Path

from pipeline.sea_geometry import check_path, sea_route_errors
from pipeline.validate import Validator

ROOT = Path(__file__).resolve().parents[1]


def test_land_crossings_cannot_be_hidden_by_canal_metadata_or_long_port_connectors():
    nodes = {
        "a": {"id": "a", "kind": "port", "lon": 120, "lat": 35},
        "b": {"id": "b", "kind": "port", "lon": 100, "lat": 35},
    }
    edge = {"from": "a", "to": "b", "via": [], "narrowPassages": [{"points": [[120, 35], [100, 35]]}]}
    assert any("crosses land" in e for e in sea_route_errors(edge, nodes))


def test_raw_dateline_jump_is_rejected_even_though_its_short_geographic_arc_is_water():
    assert "unsplit date-line" in check_path(((170, 30), (-170, 30)), ())[0]


def test_all_catalog_routes_and_curved_ship_paths_are_safe_and_pacific_lanes_have_two_segments():
    catalog = json.loads((ROOT / "data/processed/backbone.json").read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in catalog["nodes"]}
    lanes = {}
    for edge in catalog["edges"]:
        if edge["mode"] != "sea":
            continue
        assert not sea_route_errors(edge, nodes), edge["id"]
        lanes.setdefault(edge["laneId"], []).append(edge)
    pacific = [parts for lane, parts in lanes.items() if "-pacific" in lane or "-panama" in lane]
    assert len(pacific) == 6
    for parts in pacific:
        parts.sort(key=lambda e: e["segmentIndex"])
        assert len(parts) == 2
        east, west = nodes[parts[0]["to"]], nodes[parts[1]["from"]]
        assert east["lon"] == 180 and west["lon"] == -180
        assert east["lat"] == west["lat"] and east["seamId"] == west["seamId"]
        assert parts[0]["laneName"] == parts[1]["laneName"]


def test_validator_rejects_a_regression_across_china():
    network = json.loads((ROOT / "contracts/fixtures/network.json").read_text(encoding="utf-8"))
    a, b = network["nodes"][:2]
    a.update(lon=120, lat=35)
    b.update(lon=100, lat=35)
    edge = next(e for e in network["edges"] if e["mode"] == "sea")
    edge.update(via=[], **{"from": a["id"], "to": b["id"]})
    validator = Validator(ROOT)
    validator.network(network, "test")
    assert any("crosses land" in e for e in validator.errors)
