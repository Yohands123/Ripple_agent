import pytest

from pipeline.tpex_index import parse_month


def example():
    return {"stat": "ok", "tables": [{"fields": ["Date", "Open", "High", "Low", "Close", "Change(%)"],
                                      "totalCount": 1, "data": [["2020/01/02", "149.52", "150.98", "149.52", "150.91", "1.55"]]}]}


def test_published_index_levels_and_dates_are_retained():
    rows = parse_month(example(), 2020, 1)
    assert rows[0]["Date"] == "2020-01-02"
    assert rows[0]["Close"] == rows[0]["Adj Close"] == 150.91
    assert "Volume" not in rows[0]


def test_wrong_month_or_incomplete_provider_report_is_rejected():
    with pytest.raises(ValueError):
        parse_month(example(), 2020, 2)
    document = example()
    document["tables"][0]["totalCount"] = 2
    with pytest.raises(ValueError):
        parse_month(document, 2020, 1)
    with pytest.raises(ValueError):
        parse_month({"stat": "error"}, 2020, 1)
