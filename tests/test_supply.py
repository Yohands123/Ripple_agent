import json
from collections import Counter
from pathlib import Path

from pipeline.supply import build_supply_edges, categories
from pipeline.export import build_bundle

ROOT = Path(__file__).resolve().parents[1]


def test_compatibility_excludes_unknown_and_unverified_categories():
    assert categories(None) == categories("precision components (unverified)") == set()
    assert categories("keyboard components") == {"keyboard"}
    assert "pcb" in categories("printed circuit boards and IC substrates")


def test_company_has_only_three_nearest_qualifying_hubs_and_no_guessed_tier_two_edges():
    source = {"title": "Synthetic test source", "url": "https://example.org/test"}
    site = {"id": "site", "companyId": "company", "locationRole": "manufacturing", "tier": 3,
            "partType": "image sensors", "partTypeStatus": "sourced", "lon": 0, "lat": 0, "sources": [source],
            "attributeSources": {"partType": {"filedOn": "2010-01-01", "source": source}}}
    assemblies = [{"id": f"assembly-{i}", "products": ["phone"], "lon": i, "lat": 0, "sources": [source],
                   "productEvidence": {"availableOn": "2010-01-01", "source": source}} for i in [4, 1, 3, 2, 5]]
    rules = {"products": {"phone": {"categories": ["sensor"], "availableOn": "2010-01-01", "source": source}}, "supportedTier2Links": []}
    edges = build_supply_edges([site, {**site, "id": "second-site", "lon": -20}, {**site, "id": "material", "tier": 2}], assemblies, "2016-01-01", rules)
    assert len(edges) == 3 and {e["to"] for e in edges} == {"assembly-1", "assembly-2", "assembly-3"}
    assert all(e["from"] == "site" and e["modelEligible"] and e["mode"] is None and e["relation"] == "supply" for e in edges)
    # An unavailable nearest hub cannot push a dated fourth hub out of the
    # model graph merely because the contemporary reference layer includes it.
    next(a for a in assemblies if a["id"] == "assembly-1")["productEvidence"]["availableOn"] = "2025-01-01"
    historical = build_supply_edges([site], assemblies, "2016-01-01", rules)
    assert {e["to"] for e in historical} == {"assembly-2", "assembly-3", "assembly-4"}


def test_current_model_classes_and_future_assembly_evidence_do_not_enter_historical_hops():
    rules = json.loads((ROOT / "data/reference/product_components.json").read_text(encoding="utf-8"))
    bundle = build_bundle()
    for entry in bundle["scenarios/index.json"]:
        network = bundle[f"networks/{entry['id']}.json"]
        nodes = {n["id"]: n for n in network["nodes"]}
        edges = [e for e in network["edges"] if e.get("relation") == "supply"]
        assert all(count <= 3 for count in Counter(e["companyId"] for e in edges).values())
        for edge in edges:
            a, b = nodes[edge["from"]], nodes[edge["to"]]
            assert a["tier"] == 3 and b["tier"] == 4 and b["products"]
            assert categories(a["partType"]) & set(rules["products"][edge["products"][0]]["categories"])
            assert edge["sources"] and edge["confidence"] == "low" and edge["basis"]
            if edge["modelEligible"]:
                assert a["partTypeStatus"] == "sourced" and edge["availableOn"] <= entry["start"]
            else:
                assert edge["supplierCategoryInferred"] or edge["availableOn"] > entry["start"]


def test_feature_graph_uses_exactly_the_dated_supply_edges_in_each_export():
    metadata = json.loads((ROOT / "data/processed/feature_metadata.json").read_text(encoding="utf-8"))
    bundle = build_bundle()
    for graph in metadata["graphs"]:
        network = bundle[f"networks/{graph['eventId']}.json"]
        expected = {e["id"] for e in network["edges"] if e.get("relation") == "supply" and e["modelEligible"]}
        assert set(graph["supplyEdgeIds"]) == expected
