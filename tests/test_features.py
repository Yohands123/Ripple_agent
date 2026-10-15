import math
import csv
import json
from pathlib import Path

import pytest

from ml.features import breadth_first, chokepoint_evidence, disclosed_hhi, haversine, latest_assets, latest_profile, zone_overlap, supply_graph
from pipeline.historical_profiles import filing_years


def test_haversine_and_disclosed_location_concentration():
    assert haversine(10, 20, 10, 20) == pytest.approx(0)
    assert haversine(0, 0, 0, 1) == pytest.approx(111.19508, abs=0.00001)
    assert haversine(10, 20, -170, -20) == pytest.approx(math.pi * 6371.0088)
    assert disclosed_hhi([{"country": "China"}, {"country": "China"}, {"country": "Japan"}]) == pytest.approx(5 / 9)
    assert disclosed_hhi([]) is None


def test_disconnected_disclosure_graph_does_not_invent_hops():
    graph = {"shock": {"site"}, "site": {"shock", "company"}, "company": {"site"}, "unlinked": set()}
    result = breadth_first(graph, "shock")
    assert result["company"] == 2
    assert "unlinked" not in result


def test_hops_count_supply_edges_and_leave_unknown_or_future_links_disconnected():
    source = {"title": "Synthetic dated evidence", "url": "https://example.org/test"}
    base = {"locationRole": "manufacturing", "tier": 3, "partType": "image sensors", "partTypeStatus": "sourced",
            "lon": 0, "lat": 0, "sources": [source], "attributeSources": {"partType": {"filedOn": "2010-01-01", "source": source}}}
    sites = [{**base, "id": n, "companyId": n} for n in ["exposed", "connected", "unverified"]]
    sites[-1]["partTypeStatus"] = "inferred"
    assemblies = [{"id": "hub", "products": ["phone"], "lon": 1, "lat": 1, "sources": [source],
                   "productEvidence": {"availableOn": "2010-01-01", "source": source}}]
    rules = {"products": {"phone": {"categories": ["sensor"], "availableOn": "2010-01-01", "source": source}}}
    event = {"id": "test", "start": "2016-01-01"}
    edges, seeds, hops = supply_graph(sites, assemblies, event, {"exposed": True}, rules)
    assert seeds == ["exposed"]
    assert hops == {"exposed": 0, "hub": 1, "connected": 2}
    assert len(edges) == 2 and all(e["relation"] == "supply" for e in edges)
    assemblies[0]["productEvidence"]["availableOn"] = "2020-01-01"
    edges, _, hops = supply_graph(sites, assemblies, event, {"exposed": True}, rules)
    assert edges == [] and hops == {"exposed": 0}


def test_financial_attributes_are_selected_by_publication_before_event():
    profiles = [{"supplier": "Example Inc.", "filedOn": "2020-01-01", "appleRevenueShare": 0.2},
                {"supplier": "Example Inc.", "filedOn": "2020-05-01", "appleRevenueShare": 0.8},
                {"supplier": "Example Inc.", "filedOn": None, "appleRevenueShare": 0.9}]
    assert latest_profile(profiles, "Example Incorporated", "2020-03-01", {})["appleRevenueShare"] == 0.2
    facts = {"facts": {"us-gaap": {"Assets": {"units": {"USD": [
        {"end": "2019-12-31", "filed": "2020-02-01", "val": 100, "form": "10-K"},
        {"end": "2020-02-29", "filed": "2020-04-01", "val": 900, "form": "10-Q"},
    ]}}}}}
    assert latest_assets(facts, "2020-03-01")["val"] == 100
    assert latest_assets(facts, "2019-01-01") is None


def test_country_precision_cannot_resolve_a_city_shock_overlap():
    event = {"zone": '{"country":"China","names":["Zhengzhou"]}', "lon": "113.6", "lat": "34.7"}
    row = {"country": "China", "location": "China", "precision": "country", "matchStatus": "matched"}
    assert zone_overlap(row, event, {}) is None
    assert zone_overlap({**row, "country": "Japan"}, event, {}) is False
    assert zone_overlap({**row, "location": "Zhengzhou, China"}, event, {}) is True


def test_route_dependence_is_unknown_without_pre_event_evidence():
    event = {"id": "suez-2021", "start": "2021-03-23"}
    assert chokepoint_evidence("Example", event, {"entries": []}) is None
    entry = {"supplier": "Example", "eventIds": ["suez-2021"], "availableOn": "2021-04-01", "depends": True,
             "sources": [{"title": "Synthetic dated test disclosure", "url": "https://example.org"}]}
    assert chokepoint_evidence("Example", event, {"entries": [entry]}) is None
    entry["availableOn"] = "2020-01-01"
    assert chokepoint_evidence("Example", event, {"entries": [entry]})["depends"] is True


def test_fiscal_year_comes_from_filing_metadata_not_calendar_period_end():
    document = {"facts": {"us-gaap": {"Assets": {"units": {"USD": [
        {"accn": "example", "fy": 2015, "end": "2016-01-02", "form": "10-K"}
    ]}}}}}
    assert filing_years(document)["example"] == {2015}


def test_saved_financial_provenance_precedes_the_event_cutoff():
    path = Path("data/processed/feature_metadata.json")
    if not path.exists():
        pytest.skip("Feature dataset has not been generated")
    metadata = json.loads(path.read_text(encoding="utf-8"))
    events = {row["id"]: row for row in csv.DictReader(Path("data/events.csv").open(encoding="utf-8"))}
    for row in metadata["provenance"]:
        event = events[row["eventId"]]
        cutoff = event.get("knowledgeCutoffDate") or event["start"]
        assert all(source["filedOn"] < cutoff for source in row["attributeSources"].values())
        bounds = row["locationShareBounds"]
        if bounds is not None:
            assert 0 <= bounds[0] <= bounds[1] <= 1
