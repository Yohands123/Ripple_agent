import json

from pipeline.company_registry import CLASS_BASIS, CompanyRegistry, deduplicate_locations, resolve_listing
from pipeline.tiers import inferred_tier


def row(name, canonical, tier="3", part="connectors", confidence="high"):
    return {"company": name, "canonicalCompany": canonical, "tier": tier, "partType": part, "confidence": confidence}


def test_exact_classification_preserves_filing_category_and_fills_only_missing_values():
    classes = CompanyRegistry([row("Example Inc.", "Example", "2", "glass")])
    known = classes.classify("Example Inc.", "optical sensors", inferred_tier("optical sensors"))
    assert known["partType"] == "optical sensors" and known["tier"] == 3
    assert known["partTypeStatus"] == "sourced" and known["tierBasis"] == CLASS_BASIS
    inferred = classes.classify("Example Inc.", None, inferred_tier(None))
    assert inferred["partType"] == "glass" and inferred["tier"] == 2
    assert inferred["confidence"] == "high" and inferred["partTypeStatus"] == "inferred"
    assert classes.classify("example inc.", None, inferred_tier(None))["tier"] is None
    assert classes.classify("Example Inc. ", None, inferred_tier(None))["partType"] is None


def test_empty_csv_tier_remains_null_and_names_share_an_identity():
    classes = CompanyRegistry([row("First Spelling", "Example", "", "", "unknown"), row("Second Spelling", "Example")])
    assert classes.identifier("First Spelling") == classes.identifier("Second Spelling")
    assert classes.classify("First Spelling", None, inferred_tier(None))["tier"] is None


def test_alias_resolution_keeps_historical_issuer_guard_and_does_not_choose_ambiguous_tickers(monkeypatch):
    import pipeline.company_registry as module
    from pipeline.prices import company_key
    classes = CompanyRegistry([row("Broadcom Corporation", "Broadcom"), row("Broadcomm Limited", "Broadcom")])
    monkeypatch.setattr(module, "registry", lambda: classes)
    avgo = {"ticker": "AVGO", "cik": 1730168, "sources": []}
    mapping = {company_key("Broadcomm Limited"): [avgo]}
    legacy = resolve_listing(["Broadcom Corporation"], mapping, "2011-03-11")
    assert legacy["ticker"] == "" and legacy["cik"] is None
    assert resolve_listing(["Broadcomm Limited"], mapping, "2022-03-28")["ticker"] == "AVGO"
    mapping[company_key("Broadcom")] = [{"ticker": "OTHER", "cik": 1, "sources": []}]
    assert resolve_listing(["Broadcomm Limited"], mapping, "2022-03-28")["mappingUnavailableReason"] == "canonical_listing_ambiguous"


def test_duplicate_disclosure_rows_merge_citations_and_preserve_source_names(monkeypatch):
    import pipeline.company_registry as module
    classes = CompanyRegistry([row("First", "Example"), row("Second", "Example")])
    monkeypatch.setattr(module, "registry", lambda: classes)
    base = {"location": "Shenzhen", "country": "China", "locationRole": "manufacturing"}
    records = [{**base, "supplier": n, "sources": json.dumps([{"title": n, "url": "https://example.org/" + n}])} for n in ["First", "Second"]]
    merged = deduplicate_locations(records)
    assert len(merged) == 1 and merged[0]["supplierAliases"] == ["First", "Second"]
    assert len(json.loads(merged[0]["sources"])) == 2


def test_a_later_merger_does_not_merge_historical_companies_or_borrow_parent_stock(monkeypatch):
    import pipeline.company_registry as module
    from pipeline.event_study import listing_for_event
    rule = {"canonicalCompany": "MinebeaMitsumi", "sourceNamePrefix": "Mitsumi", "before": "2017-01-27", "historicalCanonicalCompany": "Mitsumi Electric"}
    classes = CompanyRegistry([row("Minebea Co., Ltd.", "MinebeaMitsumi"), row("Mitsumi Electric Co., Ltd.", "MinebeaMitsumi")], [rule])
    monkeypatch.setattr(module, "registry", lambda: classes)
    assert classes.identifier("Minebea Co., Ltd.", "2016-04-16") != classes.identifier("Mitsumi Electric Co., Ltd.", "2016-04-16")
    assert classes.identifier("Minebea Co., Ltd.", "2022-03-28") == classes.identifier("Mitsumi Electric Co., Ltd.", "2022-03-28")
    assert "Minebea Co., Ltd." not in classes.aliases("Mitsumi Electric Co., Ltd.", "2011-03-11")
    assert listing_for_event({"ticker": "6479.T", "cik": None, "sources": []}, "Mitsumi Electric Co., Ltd.", "2016-04-16")["ticker"] == ""
