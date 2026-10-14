import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pipeline.event_study import Unavailable, market_model, trading_windows


def test_synthetic_car_and_estimation_uncertainty_match_closed_form():
    market = np.linspace(-0.02, 0.02, 221)
    # A symmetric quadratic residual is orthogonal to the OLS intercept/slope.
    residual = market**2 - np.mean(market**2)
    residual *= 10
    stock = 0.001 + 1.3 * market + residual
    event_market = np.full(11, 0.005)
    event_stock = 0.001 + 1.3 * event_market - 0.02
    result = market_model(stock, market, event_stock, event_market)
    s2 = np.sum(residual**2) / 219
    expected_variance = s2 * (11 + 121 / 221 + (11 * 0.005)**2 / np.sum(market**2))
    assert result["alpha"] == pytest.approx(0.001)
    assert result["beta"] == pytest.approx(1.3)
    assert result["car"] == pytest.approx(-0.22)
    assert result["carStdError"] == pytest.approx(np.sqrt(expected_variance))
    assert result["tStat"] == pytest.approx(-0.22 / np.sqrt(expected_variance))
    assert result["hit"] is True


def test_trading_offsets_are_inclusive_and_weekend_uses_next_session():
    dates = pd.bdate_range("2020-01-01", periods=400)
    market = pd.Series(100 + np.arange(400), index=dates)
    stock = pd.Series(50 + np.arange(400), index=dates)
    weekend = "2021-01-02"
    windows = trading_windows(stock, market, weekend)
    position = dates.searchsorted(pd.Timestamp(weekend))
    assert windows[4]["dayZero"] == "2021-01-04"
    assert windows[4]["estimationStart"] == str(dates[position-250].date())
    assert windows[4]["estimationEnd"] == str(dates[position-30].date())
    assert windows[4]["eventWindowEnd"] == str(dates[position+10].date())
    assert len(windows[0]) == 221 and len(windows[2]) == 11


def test_missing_stock_session_does_not_become_a_multiday_daily_return():
    dates = pd.bdate_range("2020-01-01", periods=400)
    closes = pd.Series(100 + np.arange(400), index=dates)
    stock = closes.drop(dates[300])
    with pytest.raises(Unavailable, match="missing_event"):
        trading_windows(stock, closes, str(dates[300].date()))
    with pytest.raises(Unavailable, match="missing_estimation"):
        trading_windows(closes.drop(dates[100]), closes, str(dates[300].date()))


def test_degenerate_models_and_short_calendars_are_unavailable():
    with pytest.raises(Unavailable, match="singular"):
        market_model(np.arange(10), np.zeros(10), np.ones(11), np.ones(11))
    with pytest.raises(Unavailable, match="zero_residual"):
        market_model(np.arange(10), np.arange(10), np.ones(11), np.ones(11))
    dates = pd.bdate_range("2020-01-01", periods=50)
    closes = pd.Series(100 + np.arange(50), index=dates)
    with pytest.raises(Unavailable, match="insufficient_market"):
        trading_windows(closes, closes, "2020-02-01")


def test_saved_labels_have_unique_identities_valid_windows_and_no_fake_outcomes():
    path = Path("data/processed/labels.csv")
    if not path.exists():
        pytest.skip("Event dataset has not been generated")
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert len({(r["eventId"], r["companyId"]) for r in rows}) == len(rows)
    for row in rows:
        assert json.loads(row["sources"])
        if row["status"] == "ok":
            assert int(row["nEstimation"]) == 221 and int(row["nEvent"]) == 11
            assert row["estimationEnd"] < row["dayZero"] <= row["eventWindowEnd"]
            assert (row["hit"] == "True") == (float(row["tStat"]) < -1.96)
            assert float(row["carStdError"]) > 0
        else:
            assert not row["hit"] and not row["car"] and not row["tStat"]


def test_saved_peer_matches_use_pre_event_classifications_and_exclude_suppliers():
    path = Path("data/processed/peer_matches.json")
    if not path.exists():
        pytest.skip("Peer dataset has not been generated")
    peers = json.loads(path.read_text(encoding="utf-8"))
    events = {r["id"]: r for r in csv.DictReader(Path("data/events.csv").open(encoding="utf-8"))}
    for match in peers["matches"]:
        event = events[match["eventId"]]
        assert match["supplierTicker"] != match["peerTicker"]
        assert match["supplierClassificationFiledOn"] < event["start"]
        assert match["peerClassificationFiledOn"] < event["start"]
        assert len(match["sic"]) == 4 and match["sources"]
