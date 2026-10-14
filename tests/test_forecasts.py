from datetime import date

import numpy as np
import pytest

from ml.forecast import error_scores, evaluate, seasonal_naive
from pipeline.costs import next_month, parse_freight, parse_metals, validate_months


def test_rolling_predictions_and_mase_use_only_origin_training_history():
    month, history = date(2000, 1, 1), []
    for value in range(1, 91):
        history.append({"date": month.isoformat(), "value": float(value)})
        month = next_month(month)
    seen = []

    def perfect_linear_predictor(contexts, horizon):
        seen.extend(contexts)
        return np.array([[[c[-1] + h - 1, c[-1] + h, c[-1] + h + 1] for h in range(1, horizon + 1)] for c in contexts])

    future, baseline, metrics, rows = evaluate(history, perfect_linear_predictor, horizon=3, origins=2)
    assert [len(c) for c in seen] == [86, 87, 90]
    assert [c[-1] for c in seen] == [86, 87, 90]
    assert metrics["mase"] == 0
    assert metrics["baselineMase"] == 1
    assert metrics["pinballLoss"] == pytest.approx(1 / 15)
    assert metrics["coverage80"] == 1
    assert len(rows) == 6
    assert all(r["trainThrough"] < r["date"] and r["trainingMaseScale"] == 12 for r in rows)
    assert future[0]["q50"] == 91
    assert baseline[0]["value"] == 79
    assert future[0]["date"] == "2007-07-01"


def test_seasonal_naive_repeats_last_year_and_no_undefined_mase_is_faked():
    values = np.arange(1, 25, dtype=float)
    forecast = seasonal_naive(values, 15)
    assert forecast[:, 1].tolist() == list(range(13, 25)) + [13, 14, 15]
    assert np.all(forecast[:, 0] <= forecast[:, 1])
    with pytest.raises(ValueError, match="undefined"):
        error_scores(np.ones(2), np.ones((2, 3)), np.ones((2, 3)), 0)


def test_monthly_parser_does_not_fill_a_gap():
    with pytest.raises(ValueError, match="Missing"):
        validate_months([{"date": "2020-01-01", "value": 10}, {"date": "2020-03-01", "value": 20}])


def test_freight_aggregation_discards_incomplete_boundary_month(tmp_path):
    path = tmp_path / "freight.csv"
    path.write_text("Date,SCFI_EU\n2025/1/3,10\n2025/1/10,20\n2025/1/17,30\n2025/1/24,40\n2025/1/31,50\n2025/2/7,999\n")
    assert parse_freight(path, "2025-02-01") == [{"date": "2025-01-01", "value": 30, "weeklyObservations": 5}]


def test_workbook_uses_named_columns_and_refuses_implicit_unit_conversion(tmp_path):
    from openpyxl import Workbook
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Monthly Prices"
    sheet.append([None, "Tin", "Copper", "Aluminum"])
    sheet.append([None, "($/mt)", "($/mt)", "($/mt)"])
    sheet.append(["2020M01", 100, 20, 5])
    sheet.append(["2020M02", 101, 21, 6])
    path = tmp_path / "metals.xlsx"
    workbook.save(path)
    parsed = parse_metals(path, "2020-01-01")
    assert parsed["aluminium"] == [{"date": "2020-01-01", "value": 5}]
    assert parsed["copper"] == [{"date": "2020-01-01", "value": 20}]
    sheet.cell(2, 2, "($/kg)")
    workbook.save(path)
    with pytest.raises(ValueError, match="units"):
        parse_metals(path, "2020-02-01")
