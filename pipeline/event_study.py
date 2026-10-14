"""Market-model abnormal returns on explicitly defined exchange trading days."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from pipeline.prices import company_key, safe_symbol
from pipeline.company_registry import company_groups, registry, resolve_listing

ROOT = Path(__file__).resolve().parents[1]
TRAIN_FIRST, TRAIN_LAST, EVENT_LAST = -250, -30, 10


class Unavailable(ValueError):
    """The prescribed estimation or event window cannot be observed."""


def market_event_date(event: dict, exchange: str) -> str:
    if event.get("eventUtc") and exchange in {"NYSE", "NASDAQ"}:
        observed = datetime.fromisoformat(event["eventUtc"].replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York"))
        # Active events with exact timestamps fall on normal US sessions.
        # The benchmark index still supplies weekends and holiday handling.
        day = observed.date() + timedelta(days=observed.time() >= time(16, 0))
        return day.isoformat()
    return event["start"]


def supplier_mapping_index(mapping: dict) -> dict:
    by_key = defaultdict(list)
    for record in mapping["mapped"]:
        by_key[company_key(record["supplier"])].append(record)
        cik = record.get("cik")
        path = ROOT / f"data/raw/sec/CIK{str(cik).zfill(10)}.json" if cik else None
        if path and path.exists():
            issuer = json.loads(path.read_text(encoding="utf-8"))
            names = [issuer["name"]] + [r["name"] for r in issuer.get("formerNames", [])]
            source = {"title": f"SEC issuer legal-name history: {issuer['name']}", "url": f"https://data.sec.gov/submissions/CIK{str(cik).zfill(10)}.json"}
            for name in names:
                by_key[company_key(name)].append({**record, "sources": record["sources"] + [source]})
    return by_key


def listing_for_event(record: dict, supplier: str, event_date: str) -> dict:
    result = dict(record)
    history = json.loads((ROOT / "data/sources/listing_history.json").read_text(encoding="utf-8"))
    era = history.get(record.get("ticker"))
    if era:
        result["sources"] = list(record.get("sources", [])) + era["sources"]
        invalid_legacy = (record.get("ticker") == "AVGO" and supplier.casefold().startswith("broadcom") and event_date < era["broadcomAcquisitionDate"]) or (record.get("ticker") == "COHR" and supplier.casefold().startswith("coherent") and "corporation" not in supplier.casefold() and event_date < era["legacyCoherentAcquisitionDate"]) or (record.get("ticker") == "6479.T" and supplier.casefold().startswith("mitsumi") and event_date < era["mitsumiAcquisitionDate"])
        if invalid_legacy:
            # An acquired company's earlier stock/financial history cannot
            # be replaced by its acquirer's predecessor history.
            result["ticker"] = ""
            result["cik"] = None
            result["mappingUnavailableReason"] = "legacy_issuer_price_series_unverified"
        elif record.get("ticker") == "COHR" and event_date < era["exchangeChangeDate"]:
            result["exchange"] = era["exchangeBefore"]
            result["benchmark"] = era["benchmarkBefore"]
    return result


def market_model(stock: np.ndarray, market: np.ndarray, event_stock: np.ndarray, event_market: np.ndarray) -> dict:
    """OLS with an intercept; CAR variance includes estimation uncertainty.

    Assumes independent, constant-variance market-model residuals. The result
    identifies a statistically negative stock return, not a causal disruption
    effect or an observed loss of factory output.
    """
    arrays = [np.asarray(a, dtype=float) for a in (stock, market, event_stock, event_market)]
    stock, market, event_stock, event_market = arrays
    if any(a.ndim != 1 or not np.isfinite(a).all() for a in arrays):
        raise Unavailable("nonfinite_returns")
    n, length = len(stock), len(event_stock)
    if n <= 2 or len(market) != n or not length or len(event_market) != length:
        raise Unavailable("invalid_window_lengths")
    design = np.column_stack([np.ones(n), market])
    if np.linalg.matrix_rank(design) != 2:
        raise Unavailable("singular_market_model")
    parameters = np.linalg.lstsq(design, stock, rcond=None)[0]
    residuals = stock - design @ parameters
    variance = float(residuals @ residuals / (n - 2))
    if variance <= np.finfo(float).eps:
        raise Unavailable("zero_residual_variance")
    abnormal = event_stock - parameters[0] - parameters[1] * event_market
    car = float(abnormal.sum())
    exposure = np.array([length, event_market.sum()])
    car_variance = float(variance * (length + exposure @ np.linalg.solve(design.T @ design, exposure)))
    t_stat = car / np.sqrt(car_variance)
    return {"alpha": float(parameters[0]), "beta": float(parameters[1]), "residualVariance": variance,
            "car": car, "carStdError": float(np.sqrt(car_variance)), "tStat": float(t_stat), "hit": bool(t_stat < -1.96),
            "nEstimation": n, "nEvent": length}


def trading_windows(stock_close: pd.Series, market_close: pd.Series, event_date: str) -> tuple:
    """Day zero is the first exchange session on/after the local event date.

    The market's dates define the calendar. Reindex before computing equity
    returns, so a missing stock session cannot become a multiday return
    compared with a single day's index return. Missing prices are never filled.
    """
    market_close = market_close.sort_index()
    if market_close.index.has_duplicates or stock_close.index.has_duplicates:
        raise Unavailable("duplicate_price_dates")
    position = market_close.index.searchsorted(pd.Timestamp(event_date))
    if position < -TRAIN_FIRST + 1 or position + EVENT_LAST >= len(market_close):
        raise Unavailable("insufficient_market_calendar")
    aligned_stock = stock_close.reindex(market_close.index)
    returns = pd.DataFrame({"stock": aligned_stock.pct_change(fill_method=None), "market": market_close.pct_change(fill_method=None)})
    training = returns.iloc[position + TRAIN_FIRST:position + TRAIN_LAST + 1]
    event = returns.iloc[position:position + EVENT_LAST + 1]
    if training.isna().any().any():
        raise Unavailable("missing_estimation_observations")
    if event.isna().any().any():
        raise Unavailable("missing_event_observations")
    if len(training) != 221 or len(event) != 11:
        raise Unavailable("incomplete_trading_window")
    dates = {"dayZero": str(event.index[0].date()), "estimationStart": str(training.index[0].date()), "estimationEnd": str(training.index[-1].date()),
             "eventWindowEnd": str(event.index[-1].date())}
    return training["stock"].to_numpy(), training["market"].to_numpy(), event["stock"].to_numpy(), event["market"].to_numpy(), dates


def read_close(symbol: str, manifest: dict[str, dict]) -> pd.Series:
    record = manifest.get(symbol)
    if not record:
        raise Unavailable("price_download_unavailable")
    path = ROOT / record["file"]
    if not path.exists():
        raise Unavailable("raw_price_cache_unavailable")
    if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
        raise ValueError(f"Price hash differs from manifest: {symbol}")
    frame = pd.read_csv(path, index_col="Date", parse_dates=["Date"])
    close = frame["Adj Close"].astype(float)
    if not np.isfinite(close).all() or (close <= 0).any():
        raise ValueError(f"Invalid adjusted close: {symbol}")
    return close


def analyze() -> dict:
    events = list(csv.DictReader((ROOT / "data/events.csv").open(encoding="utf-8")))
    lists = json.loads((ROOT / "data/interim/supplier_list_manifest.json").read_text(encoding="utf-8"))
    editions = {r["snapshotYear"]: r for r in lists["editions"]}
    mapping = json.loads((ROOT / "data/processed/ticker_map.json").read_text(encoding="utf-8"))
    by_key = supplier_mapping_index(mapping)
    prices = json.loads((ROOT / "data/processed/price_manifest.json").read_text(encoding="utf-8"))
    price_records = {r["ticker"]: r for r in prices["prices"]}
    peer_prices = ROOT / "data/processed/peer_price_manifest.json"
    if peer_prices.exists():
        price_records.update({r["ticker"]: r for r in json.loads(peer_prices.read_text(encoding="utf-8"))["prices"]})
    peer_path = ROOT / "data/processed/peer_matches.json"
    peer_data = json.loads(peer_path.read_text(encoding="utf-8")) if peer_path.exists() else {"matches": [], "peers": []}
    peers = {(r["eventId"], r["ticker"]): r for r in peer_data.get("peerEventRecords", [])}
    historical_path = ROOT / "data/processed/industry_history.json"
    classifications = {(r["eventId"], r["ticker"]): r for r in json.loads(historical_path.read_text(encoding="utf-8"))["classifications"]} if historical_path.exists() else {}
    markets = json.loads((ROOT / "data/sources/markets.json").read_text(encoding="utf-8"))
    cache, output, gaps = {}, [], []

    def evaluate(record, event, role, supplier, company_id, source_list, aliases=None):
        record = dict(record)
        historical = classifications.get((event["id"], record.get("ticker")))
        if historical and historical.get("exchange"):
            record.update(exchange=historical["exchange"], benchmark=markets["benchmarks"][historical["exchange"]]["symbol"])
            record["sources"] = record.get("sources", []) + [historical["source"]]
        row = {"eventId": event["id"], "eventYear": int(event["eventYear"]), "snapshotYear": int(event["snapshotYear"]), "companyId": company_id,
               "supplier": supplier, "role": role, "ticker": record.get("ticker", ""), "exchange": record.get("exchange", ""),
               "benchmark": record.get("benchmark", ""), "status": record.get("mappingUnavailableReason", "mapping_unavailable"), "sources": source_list + [{"title": event["sourceTitle"], "url": event["sourceUrl"]}] + record.get("sources", []),
               "sourceSupplierNames": json.dumps(aliases or [supplier]),
               "identityBasis": "User-provided inferred canonicalCompany; exact source-name matches" if role == "supplier" else "Peer ticker identity"}
        row["exchangeEvidenceStatus"] = "verified_pre_event_cover" if historical and historical.get("exchange") else "current_listing_historical_exchange_unverified"
        if record.get("ticker"):
            try:
                for symbol in (record["ticker"], record["benchmark"]):
                    if symbol not in cache:
                        cache[symbol] = read_close(symbol, price_records)
                windows = trading_windows(cache[record["ticker"]], cache[record["benchmark"]], market_event_date(event, record["exchange"]))
                if event.get("eventUtc") and record["exchange"] in {"NYSE", "NASDAQ"}:
                    row["sources"].append({"title": "NYSE regular core session: 9:30 a.m. to 4 p.m. Eastern", "url": "https://www.nyse.com/markets/hours-calendars"})
                row.update(market_model(*windows[:4]), **windows[4], status="ok")
                row["sources"].extend(source for symbol in (record["ticker"], record["benchmark"]) for source in price_records[symbol]["sources"])
            except Unavailable as exc:
                row["status"] = str(exc)
        row["sources"] = json.dumps(list({(s["title"], s["url"]): s for s in row["sources"]}.values()), ensure_ascii=False)
        output.append(row)

    for event in events:
        year = int(event["snapshotYear"])
        if year not in editions:
            gaps.append({"eventId": event["id"], "snapshotYear": year, "reason": "No verified own-year Supplier List; event not analyzed"})
            continue
        with (ROOT / f"data/interim/suppliers_{year}.csv").open(encoding="utf-8") as handle:
            names = sorted({r["supplier"] for r in csv.DictReader(handle)})
        for identifier, aliases in company_groups(names, event["start"]).items():
            name = registry().canonical(aliases[0], event["start"])
            record = resolve_listing(aliases, by_key, event["start"])
            evaluate(record, event, "supplier", name, identifier, editions[year]["sources"], aliases)
        peer_tickers = {r["peerTicker"] for r in peer_data["matches"] if r["eventId"] == event["id"]}
        for ticker in sorted(peer_tickers):
            record = peers[(event["id"], ticker)]
            evaluate(record, event, "peer", record["listedName"], "peer-" + safe_symbol(ticker), editions[year]["sources"])
    fields = ["eventId", "eventYear", "snapshotYear", "companyId", "supplier", "sourceSupplierNames", "identityBasis", "role", "ticker", "exchange", "benchmark", "exchangeEvidenceStatus", "status", "dayZero", "estimationStart", "estimationEnd", "eventWindowEnd",
              "alpha", "beta", "residualVariance", "nEstimation", "nEvent", "car", "carStdError", "tStat", "hit", "sources"]
    with (ROOT / "data/processed/labels.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)
    summary = {"sampleData": False, "estimationTradingDays": [-250, -30], "eventTradingDays": [0, 10], "hitThreshold": -1.96,
               "carVariance": "OLS residual variance times [L + g' (X'X)^-1 g], g = sum of event design rows",
               "dayZeroPolicy": "Exact USGS timestamps aligned to US regular-session close for NYSE/NASDAQ; otherwise first benchmark session on/after local event date. Current exact-timestamp events avoid US early-close sessions.",
               "interpretation": "Statistically negative stock-market abnormal return; not a causal impact estimate or factory-output observation",
               "snapshotPolicy": "Verified own-year lists, published retrospectively; 2011 uses the explicitly approved January 2012 company roster approximation. No FY2019/FY2024 substitution. Membership was not necessarily publicly known at the event date.",
               "exchangePolicy": "Pre-event registered-securities cover where verified; otherwise currently reported listing, flagged as not historically verified",
               "rows": len(output), "statusCounts": dict(Counter(r["status"] for r in output)), "events": [], "gaps": gaps}
    excluded = ROOT / "data/review/event_gaps.json"
    summary["excludedEvents"] = json.loads(excluded.read_text(encoding="utf-8"))["events"] if excluded.exists() else []
    for event in events:
        rows = [r for r in output if r["eventId"] == event["id"]]
        valid = [r for r in rows if r["status"] == "ok"]
        summary["events"].append({"eventId": event["id"], "snapshotYear": int(event["snapshotYear"]), "cohort": json.loads(event["cohort"]) if event.get("cohort") else {}, "rows": len(rows), "validSupplierLabels": sum(r["role"] == "supplier" for r in valid),
                                  "validPeerLabels": sum(r["role"] == "peer" for r in valid), "hits": sum(r["hit"] for r in valid)})
    (ROOT / "data/processed/label_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary["events"], indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    result = analyze()
    return int(bool(result["gaps"]))


if __name__ == "__main__":
    raise SystemExit(main())
