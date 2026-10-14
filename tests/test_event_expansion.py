import json
from pathlib import Path

import pytest

from pipeline.events import expanded_events
from pipeline.export import unlocated_company
from pipeline.validate import Validator


def test_unapproved_event_expansion_does_not_activate_proxies_or_additions():
    base = [{"id": "earthquake", "eventYear": 2024, "snapshotYear": 2024}]
    more = [{"id": "older", "eventYear": 2011, "snapshotYear": 2011}]
    assert expanded_events(base, more, {"approved": False, "snapshotProxies": {"earthquake": 2023}}) == base
    chosen = expanded_events(base, more, {"approved": True, "snapshotProxies": {"earthquake": 2023}})
    assert chosen[0]["eventYear"] == 2024 and chosen[0]["snapshotYear"] == 2023
    assert base[0]["snapshotYear"] == 2024
    with pytest.raises(ValueError, match="Duplicate"):
        expanded_events(base, base, {"approved": True})


def test_company_export_preserves_stock_outcome_without_fabricated_coordinates():
    source = {"title": "Public report", "url": "https://example.org/report"}
    prediction = {"companyId": "c", "supplier": "Example", "pHit": .2, "ciLow": .1, "ciHigh": .3,
                  "lowConfidence": True, "shap": [], "shapBaseValue": -1.0, "shapMeanRawScore": -1.0, "sources": [source]}
    attributes = {"ticker": "", "sources": json.dumps([source])}
    label = {"hit": "True", "car": "-0.1", "sources": json.dumps([source])}
    record = unlocated_company(prediction, attributes, label)
    assert not {"lon", "lat", "nodeId"} & record.keys()
    assert record["actual"] == {"hit": True, "car": -.1}
    assert record["outcomeObservable"] is True and record["sources"] == [source]
    scenario = {"cohort": {"locationCoverage": "company-only", "companyOnlyExportApproved": True, "assumption": True}, "companyPredictions": [record]}
    validator = Validator(Path('.'))
    validator.company_predictions(scenario, set(), "test")
    assert validator.errors == []
    validator.company_predictions(scenario, {"invented-site"}, "test")
    assert any("no invented sites" in e for e in validator.errors)
    record["lon"] = 120
    validator.company_predictions(scenario, set(), "test")
    assert any("cannot assert site coordinates" in e for e in validator.errors)


def test_legacy_broadcom_cannot_borrow_avago_prices_or_financial_identity():
    from pipeline.event_study import listing_for_event
    record = {"ticker": "AVGO", "cik": 1730168, "exchange": "NASDAQ", "benchmark": "^IXIC", "sources": []}
    before = listing_for_event(record, "Broadcom Corporation", "2011-03-11")
    assert before["ticker"] == "" and before["cik"] is None
    assert before["mappingUnavailableReason"] == "legacy_issuer_price_series_unverified"
    assert listing_for_event(record, "Broadcom Limited", "2016-04-16")["ticker"] == "AVGO"


def test_single_class_events_are_excluded_from_every_metric_without_losing_predictions():
    import pandas as pd
    from ml.train import calibration, evaluation_population, score
    assert score([0, 0], [.1, .2])["auc"] is None
    predictions = pd.DataFrame({"eventId": ["zero", "zero", "one", "one", "mixed", "mixed"],
                                "hit": [0, 0, 1, 1, 0, 1], "pHit": [.1, .2, .8, .9, .2, .8]})
    with pytest.raises(ValueError, match="recorded evaluation decision"):
        evaluation_population(predictions, {})
    eligible, excluded = evaluation_population(predictions, {"approved": True, "singleClassEvents": "exclude-from-metrics"})
    assert set(eligible["eventId"]) == {"mixed"}
    assert {r["eventId"] for r in excluded} == {"zero", "one"}
    assert len(predictions) == 6 and len(eligible) == 2
    assert score(eligible["hit"], eligible["pHit"])["auc"] == 1
    assert sum(r["n"] for r in calibration(eligible)) == 2
    with pytest.raises(ValueError, match="No events"):
        evaluation_population(predictions.iloc[:4], {"approved": True, "singleClassEvents": "exclude-from-metrics"})


def test_validator_rejects_undefined_auc_and_single_class_numeric_placeholders():
    metrics = {"model": "lightgbm", "events": 1, "rows": 2,
               "loeo": [{"eventId": "single-class", "auc": None, "baselineAuc": None, "distanceAuc": None,
                         "brier": .025, "rows": 2, "hits": 0, "aucUnavailableReason": "No positive targets"}],
               "overall": {"auc": [.4, .6], "brier": [.01, .05], "baselineAuc": [.4, .6]}, "calibration": []}
    v = Validator(Path('.'))
    v.metrics(metrics)
    assert any("invalid numeric" in e for e in v.errors)
    metrics["loeo"][0].update(auc=.5, baselineAuc=.5, distanceAuc=.5)
    v = Validator(Path('.'))
    v.metrics(metrics)
    assert any("both supplier outcome classes" in e for e in v.errors)
