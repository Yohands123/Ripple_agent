"""Chronos-Bolt quantile forecasts and expanding-window monthly backtests."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import date
from pathlib import Path

import numpy as np

from pipeline.costs import next_month, validate_months

ROOT = Path(__file__).resolve().parents[1]
QUANTILES = np.array([0.1, 0.5, 0.9])
HORIZON, ORIGINS, SEASON = 6, 24, 12


def seasonal_naive(train, horizon=HORIZON):
    train = np.asarray(train, dtype=float)
    if len(train) <= SEASON:
        raise ValueError("Seasonal naive requires more than one year of history")
    center = np.resize(train[-SEASON:], horizon)
    residuals = train[SEASON:] - train[:-SEASON]
    lower, upper = np.quantile(residuals, [0.1, 0.9])
    return np.column_stack([center + min(lower, 0), center, center + max(upper, 0)])


def error_scores(actual, quantiles, baseline, scale):
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("MASE is undefined when training seasonal differences are zero")
    actual = np.asarray(actual)
    error = actual[:, None] - quantiles
    baseline_error = actual[:, None] - baseline
    return {
        "mase": float(np.abs(error[:, 1]).mean() / scale),
        "baselineMase": float(np.abs(baseline_error[:, 1]).mean() / scale),
        "pinballLoss": float(np.maximum(QUANTILES * error, (QUANTILES - 1) * error).mean()),
        "baselinePinballLoss": float(np.maximum(QUANTILES * baseline_error, (QUANTILES - 1) * baseline_error).mean()),
        "coverage80": float(((actual >= quantiles[:, 0]) & (actual <= quantiles[:, 2])).mean()),
        "baselineCoverage80": float(((actual >= baseline[:, 0]) & (actual <= baseline[:, 2])).mean()),
    }


def evaluate(history, predictor, horizon=HORIZON, origins=ORIGINS):
    """Each prediction and its MASE scale use only observations before origin."""
    validate_months(history)
    values = np.array([r["value"] for r in history], dtype=np.float64)
    first = max(60, len(values) - horizon - origins + 1)
    cuts = list(range(first, len(values) - horizon + 1))
    if not cuts:
        raise ValueError("Insufficient monthly history for rolling evaluation")
    predictions = predictor([values[:cut].copy() for cut in cuts] + [values.copy()], horizon)
    if predictions.shape != (len(cuts) + 1, horizon, 3) or not np.isfinite(predictions).all():
        raise ValueError("Unexpected/nonfinite forecast output")
    # Monotonic rearrangement is used consistently for scores and future bands.
    predictions = np.sort(predictions, axis=2)
    rows, scores = [], []
    for index, cut in enumerate(cuts):
        train = values[:cut]
        scale = float(np.abs(train[SEASON:] - train[:-SEASON]).mean())
        actual = values[cut:cut + horizon]
        baseline = seasonal_naive(train, horizon)
        scores.append(error_scores(actual, predictions[index], baseline, scale))
        for step in range(horizon):
            rows.append({"trainThrough": history[cut - 1]["date"], "date": history[cut + step]["date"], "horizon": step + 1,
                         "actual": float(actual[step]), "q10": float(predictions[index, step, 0]), "q50": float(predictions[index, step, 1]), "q90": float(predictions[index, step, 2]),
                         "baselineQ10": float(baseline[step, 0]), "baseline": float(baseline[step, 1]), "baselineQ90": float(baseline[step, 2]), "trainingMaseScale": scale})
    metrics = {key: float(np.mean([s[key] for s in scores])) for key in scores[0]}
    metrics.update({"origins": len(cuts), "horizonMonths": horizon, "scoredPredictions": len(rows),
                    "firstTarget": rows[0]["date"], "lastTarget": rows[-1]["date"],
                    "aggregation": "Equal-weight origin means; MASE denominator is each origin's training-only seasonal MAE"})
    future, baseline_future = [], []
    baseline = seasonal_naive(values, horizon)
    month = date.fromisoformat(history[-1]["date"])
    for step in range(horizon):
        month = next_month(month)
        future.append({"date": month.isoformat(), **{key: float(predictions[-1, step, i]) for i, key in enumerate(["q10", "q50", "q90"])}})
        baseline_future.append({"date": month.isoformat(), "value": float(baseline[step, 1])})
    return future, baseline_future, metrics, rows


def load_predictor(registry):
    # Keep all model downloads and Hugging Face caches in ignored data/raw/.
    os.environ["HF_HOME"] = str(ROOT / "data/raw/huggingface")
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    from ml.runtime import ensure_openmp
    ensure_openmp()
    import torch
    from chronos import BaseChronosPipeline
    torch.set_num_threads(2)
    torch.manual_seed(1729)
    spec = registry["model"]
    snapshot = ROOT / "data/raw/cost_models" / spec["revision"]
    weight_hash = hashlib.sha256((snapshot / "model.safetensors").read_bytes()).hexdigest()
    if weight_hash != spec["weightsSha256"]:
        raise ValueError("Pinned model weight checksum mismatch")
    pipeline = BaseChronosPipeline.from_pretrained(str(snapshot), device_map="cpu", torch_dtype=torch.float32, local_files_only=True)

    def predict(contexts, horizon):
        quantiles, _ = pipeline.predict_quantiles([torch.tensor(c, dtype=torch.float32) for c in contexts], prediction_length=horizon,
                                                 quantile_levels=QUANTILES.tolist())
        return quantiles.detach().cpu().numpy()

    return predict, {**spec,
                     "torchVersion": torch.__version__, "quantiles": QUANTILES.tolist(), "quantileRearrangement": "Sorted independently at each forecast step"}


def main():
    history_path = ROOT / "data/processed/cost_history.json"
    history = json.loads(history_path.read_text(encoding="utf-8"))
    registry = json.loads((ROOT / "data/sources/costs.json").read_text(encoding="utf-8"))
    predictor, model = load_predictor(registry)
    series, backtest = [], []
    for item in history["series"]:
        future, baseline, metrics, rows = evaluate(item["history"], predictor)
        release_month = next_month(date.fromisoformat(model["releasedOn"]))
        later_targets = sum(r["date"] >= release_month.isoformat() for r in item["history"])
        if later_targets:
            _, _, later_metrics, later_rows = evaluate(item["history"], predictor, horizon=1, origins=later_targets)
            metrics["afterPublicReleaseOneMonth"] = {**later_metrics, "note": "Small descriptive check after the reported model release; current data vintage and potential training overlap still limit interpretation"}
            backtest.extend({"seriesId": item["id"], "evaluation": "after-public-release-one-month", **r} for r in later_rows)
        series.append({**item, "forecast": future, "baseline": baseline, "metrics": metrics})
        backtest.extend({"seriesId": item["id"], "evaluation": "rolling-six-month", **r} for r in rows)
        print(item["id"], json.dumps(metrics), flush=True)
    document = {"sampleData": False, "asOf": history["asOf"], "model": model, "series": series,
                "evaluationDefinition": "Expanding-window rolling origins; six-month forecasts; seasonal-naive period 12; no fitting or tuning to held-out targets",
                "intervalDefinition": "Chronos pretrained 10th and 90th quantiles; nominal 80% predictive band, not a guaranteed confidence interval",
                "baselineIntervalDefinition": "Training-only empirical 10/90 percentiles of annual seasonal differences around seasonal naive; bounds include the point forecast",
                "limitations": ["Backtest uses the downloaded vintage, not historical release vintages. Monthly labels identify observation periods, not publication dates.",
                                "Pretrained-model training data may overlap older backtest periods. These scores do not establish fully unseen-series performance.",
                                "Overlapping six-month targets are dependent. No independent-sample confidence intervals are claimed.",
                                "The freight series is a regional Shanghai-Europe route, not a global rate or an Apple contract price. Its archived forecast starts in May 2025."]}
    path = ROOT / "data/processed/forecasts.json"
    path.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    with (ROOT / "data/processed/forecast_backtest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(backtest[0]))
        writer.writeheader()
        writer.writerows(backtest)
    print("Saved forecasts and", len(backtest), "rolling target rows", flush=True)


if __name__ == "__main__":
    main()
