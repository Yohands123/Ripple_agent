import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pipeline.prices import clean_prices, company_key, safe_symbol, select_quote


@pytest.fixture
def markets():
    return json.loads(Path("data/sources/markets.json").read_text(encoding="utf-8"))


def test_legal_names_match_without_turning_subsidiaries_into_parents():
    assert company_key("Murata Manufacturing Company Limited") == company_key("Murata Manufacturing Co., Ltd.")
    assert company_key("Hon Hai Precision Industry Company Limited (Foxconn)") == company_key("Hon Hai Precision Industry Co., Ltd.")
    assert company_key("Tianma Micro-Electronics (Hong Kong) Limited") != company_key("Tianma Micro-Electronics Co., Ltd.")
    assert company_key("Example Holdings Incorporated") != company_key("Example Incorporated")


def test_quote_requires_equity_exact_name_and_supported_exchange(markets):
    quotes = [
        {"symbol": "FAKE", "longname": "Murata Equipment Co., Ltd.", "quoteType": "EQUITY", "exchange": "JPX"},
        {"symbol": "MRAAY", "longname": "Murata Manufacturing Co., Ltd.", "quoteType": "EQUITY", "exchange": "PNK"},
        {"symbol": "6981.T", "longname": "Murata Manufacturing Co., Ltd.", "quoteType": "EQUITY", "exchange": "JPX"},
    ]
    assert select_quote("Murata Manufacturing Company Limited", quotes, markets)["symbol"] == "6981.T"
    assert select_quote("Unrelated Company", quotes, markets) is None


def test_ticker_cannot_escape_the_raw_cache():
    assert safe_symbol("^IXIC") == "INDEX_IXIC"
    assert safe_symbol("2317.TW") == "2317.TW"
    with pytest.raises(ValueError):
        safe_symbol("../../outside")


def test_price_validation_rejects_bad_or_missing_observations():
    dates = pd.to_datetime(["2020-01-03", "2020-01-02"])
    frame = pd.DataFrame({"Close": [102, 100], "Adj Close": [51, 50]}, index=dates)
    cleaned = clean_prices(frame)
    assert str(cleaned.index[0].date()) == "2020-01-02"
    for bad in [pd.DataFrame(), frame.assign(Close=[0, 1]), frame.assign(**{"Adj Close": [np.inf, 50]})]:
        with pytest.raises(ValueError):
            clean_prices(bad)
    with pytest.raises(ValueError):
        clean_prices(pd.concat([frame, frame]))


def test_published_manifest_covers_every_mapped_listing_and_benchmark():
    mapping = json.loads(Path("data/processed/ticker_map.json").read_text(encoding="utf-8"))
    manifest = json.loads(Path("data/processed/price_manifest.json").read_text(encoding="utf-8"))
    expected = {r[key] for r in mapping["mapped"] for key in ("ticker", "benchmark")}
    assert not manifest["failures"]
    assert {r["ticker"] for r in manifest["prices"]} == expected
    assert manifest["mappingCounts"] == mapping["counts"]
    assert all(r["rows"] > 0 and r["firstDate"] <= r["lastDate"] and r["sources"] for r in manifest["prices"])
    assert mapping["counts"]["unlisted"] == len(mapping["unlisted"])
    assert not ({r["supplier"] for r in mapping["unlisted"]} & {r["supplier"] for r in mapping["unresolved"]})
