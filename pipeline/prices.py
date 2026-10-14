"""Resolve supported exchange listings and cache yfinance daily prices."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)


def company_key(name: str) -> str:
    if not name:
        return ""
    name = re.sub(r"\((?:Foxconn|Foxlink)\)", "", name, flags=re.I)
    name = re.sub(r"\bS\.?\s*A\.?\b", " SA ", name)
    name = re.sub(r"\bAktiengesellschaft\b", " AG ", name, flags=re.I)
    name = unicodedata.normalize("NFKD", name).casefold().replace("&", " and ")
    name = "".join(c for c in name if not unicodedata.combining(c))
    words = re.findall(r"[a-z0-9]+", name)
    legal = {"company", "co", "corporation", "corp", "incorporated", "inc", "limited", "ltd", "plc", "ag", "nv", "sa", "gmbh"}
    return " ".join(word for word in words if word not in legal)


def safe_symbol(symbol: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9.^=-]{1,40}", symbol):
        raise ValueError("Invalid ticker symbol")
    return symbol.replace("^", "INDEX_")


def canonical_exchange(exchange: str, config: dict) -> str:
    return config["exchangeAliases"].get(exchange, exchange)


def select_quote(name: str, quotes: list[dict], config: dict) -> dict | None:
    target = company_key(name)
    matches = [record for record in quotes if record.get("quoteType") == "EQUITY"
               and canonical_exchange(record.get("exchange", ""), config) in config["benchmarks"]
               and target in {company_key(record.get("longname", "")), company_key(record.get("shortname", ""))}]
    # Prefer an ordinary supported local listing to an unsupported OTC quote.
    # The same-name result is required; related public subsidiaries do not qualify.
    return matches[0] if matches else None


def setup_yfinance():
    import yfinance as yf
    cache = ROOT / "data/raw/yfinance"
    cache.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(cache))
    return yf


def supplier_names(interim: Path) -> list[str]:
    manifest = json.loads((interim / "supplier_list_manifest.json").read_text(encoding="utf-8"))
    names = set()
    for edition in manifest["editions"]:
        with (interim / f"suppliers_{edition['snapshotYear']}.csv").open(encoding="utf-8") as handle:
            names.update(row["supplier"] for row in csv.DictReader(handle))
    return sorted(names)


def quote_source(symbol: str) -> dict:
    return {"title": f"Yahoo Finance listing: {symbol}", "url": f"https://finance.yahoo.com/quote/{quote(symbol, safe='')}/"}


def sec_seed_mappings(config: dict) -> dict[str, dict]:
    path = ROOT / "data/raw/listings/SEC.json"
    if not path.exists():
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = [dict(zip(document["fields"], values)) for values in document["data"]]
    by_ticker = {row["ticker"]: row for row in rows}
    by_name = defaultdict(list)
    for row in rows:
        exchange = canonical_exchange(row["exchange"], config)
        if exchange in config["benchmarks"]:
            by_name[company_key(row["name"])].append(row)
    registry = json.loads((ROOT / "data/sources/filings.json").read_text(encoding="utf-8"))
    result = {}
    for name in supplier_names(ROOT / "data/interim"):
        candidates = by_name.get(company_key(name), [])
        issuer = next((item for item in registry["issuers"] if re.search(item["match"], name, re.I)), None)
        if not candidates and issuer:
            ticker = issuer.get("secTicker") or issuer["archive"].rsplit("_", 1)[-1]
            record = by_ticker.get(ticker)
            if record and canonical_exchange(record["exchange"], config) in config["benchmarks"]:
                candidates = [record]
        if len(candidates) == 1:
            row = candidates[0]
            result[name] = {"ticker": row["ticker"], "exchange": canonical_exchange(row["exchange"], config), "listedName": row["name"],
                            "mappingMethod": "SEC registry with reported issuer names", "cik": row["cik"],
                            "sources": [{"title": "SEC company tickers and exchanges", "url": "https://www.sec.gov/files/company_tickers_exchange.json"}]}
    return result


def resolve_suppliers(config: dict, offline: bool = False) -> dict:
    yf = setup_yfinance()
    seeds = sec_seed_mappings(config)
    quote_dir = ROOT / "data/raw/quotes"
    quote_dir.mkdir(parents=True, exist_ok=True)
    mapped, unlisted, unresolved = [], [], []
    for number, name in enumerate(supplier_names(ROOT / "data/interim"), start=1):
        private = next((record for record in config["privateCompanies"] if re.search(record["match"], name, re.I)), None)
        if private:
            unlisted.append({"supplier": name, "status": "unlisted", "reason": "Company explicitly reports private ownership", "sources": [{"title": private["title"], "url": private["url"]}]})
            continue
        mapping = seeds.get(name)
        if not mapping:
            cache = quote_dir / (hashlib.sha256(name.encode("utf-8")).hexdigest()[:20] + ".json")
            try:
                if cache.exists():
                    quotes = json.loads(cache.read_text(encoding="utf-8"))["quotes"]
                elif offline:
                    quotes = []
                else:
                    query = re.sub(r"\([^)]*\)", "", name).strip()
                    quotes = yf.Search(query, max_results=8, news_count=0, enable_fuzzy_query=False, timeout=15).quotes
                    cache.write_text(json.dumps({"supplier": name, "quotes": quotes, "asOf": config["asOf"]}, indent=2) + "\n", encoding="utf-8")
                    time.sleep(0.35)
                candidate = select_quote(name, quotes, config)
                # Legal suffixes can prevent Yahoo's search from finding an
                # issuer. Search again with the normalized name, still requiring
                # an exact issuer-name match before accepting any result.
                short_cache = cache.with_name(cache.stem + "_normalized.json")
                if not candidate:
                    if short_cache.exists():
                        more_quotes = json.loads(short_cache.read_text(encoding="utf-8"))["quotes"]
                    elif offline:
                        more_quotes = []
                    else:
                        query = company_key(name)
                        more_quotes = yf.Search(query, max_results=12, news_count=0, enable_fuzzy_query=False, timeout=15).quotes
                        short_cache.write_text(json.dumps({"supplier": name, "query": query, "quotes": more_quotes, "asOf": config["asOf"]}, indent=2) + "\n", encoding="utf-8")
                        time.sleep(0.35)
                    candidate = select_quote(name, more_quotes, config)
                if candidate:
                    symbol = candidate["symbol"]
                    safe_symbol(symbol)
                    mapping = {"ticker": symbol, "exchange": canonical_exchange(candidate["exchange"], config), "listedName": candidate.get("longname") or candidate.get("shortname"),
                               "mappingMethod": "Yahoo Finance exact normalized issuer name", "cik": None, "sources": [quote_source(symbol)]}
            except Exception as exc:
                LOGGER.warning("%s: search unavailable (%s)", name, type(exc).__name__)
        if mapping:
            exchange = mapping["exchange"]
            mapped.append({"supplier": name, "status": "listed", **mapping, "benchmark": config["benchmarks"][exchange]["symbol"]})
        else:
            unresolved.append({"supplier": name, "status": "unresolved", "reason": "No unique supported listing verified; this does not establish private ownership"})
        if number % 20 == 0:
            LOGGER.info("Resolved %s suppliers: %s mapped, %s unresolved", number, len(mapped), len(unresolved))
    output = {"sampleData": False, "asOf": config["asOf"], "mapped": mapped, "unlisted": unlisted, "unresolved": unresolved,
              "counts": {"mappedSupplierNames": len(mapped), "mappedTickers": len({row["ticker"] for row in mapped}), "unlisted": len(unlisted), "unresolved": len(unresolved)}}
    processed, review = ROOT / "data/processed", ROOT / "data/review"
    (processed / "ticker_map.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for filename, rows in [("unlisted_suppliers.csv", unlisted), ("unresolved_tickers.csv", unresolved)]:
        with (review / filename).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["supplier", "status", "reason", "sources"])
            writer.writeheader()
            writer.writerows({**row, "sources": json.dumps(row.get("sources", []))} for row in rows)
    LOGGER.info("Ticker mapping: %s", output["counts"])
    return output


def clean_prices(frame):
    import numpy as np
    import pandas as pd
    if frame is None or frame.empty:
        raise ValueError("Provider returned no price observations")
    if "Close" not in frame or "Adj Close" not in frame:
        raise ValueError("Unadjusted and adjusted close columns are required")
    result = frame.copy().dropna(subset=["Close", "Adj Close"])
    result.index = pd.to_datetime(result.index).tz_localize(None)
    result = result.sort_index()
    if result.empty or result.index.has_duplicates:
        raise ValueError("Price dates are empty or duplicated")
    values = result[["Close", "Adj Close"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("Close prices must be finite and positive")
    result.index.name = "Date"
    return result


def download_prices(mapping: dict, config: dict, start: str, end: str, offline: bool = False, manifest_path: Path | None = None) -> dict:
    import pandas as pd
    yf = setup_yfinance()
    raw = ROOT / "data/raw/prices"
    raw.mkdir(parents=True, exist_ok=True)
    stocks = {row["ticker"] for row in mapping["mapped"]}
    indices = {row["benchmark"] for row in mapping["mapped"]}
    manifest = {"sampleData": False, "provider": "yfinance", "providerVersion": yf.__version__, "requestedStart": start, "requestedEndExclusive": end,
                "prices": [], "failures": [], "mappingCounts": mapping["counts"]}
    for symbol in sorted(stocks | indices):
        benchmark = next((r for r in config["benchmarks"].values() if r["symbol"] == symbol), {})
        path = raw / (safe_symbol(symbol) + ".csv")
        metadata_path = path.with_suffix(".source.json")
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
            if path.exists() and metadata.get("requestedStart", "9999") <= start and metadata.get("requestedEndExclusive", "") >= end:
                if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["sha256"]:
                    raise ValueError("Cached price file hash differs from its source record")
                frame = clean_prices(pd.read_csv(path, index_col="Date", parse_dates=["Date"]))
            elif benchmark.get("provider") == "Taipei Exchange":
                raise FileNotFoundError("Run python -m pipeline.tpex_index to cache the exchange's public index reports")
            elif offline:
                raise FileNotFoundError("Complete requested download is not cached")
            else:
                frame = None
                for attempt in range(3):
                    candidate = yf.download(symbol, start=start, end=end, interval="1d", auto_adjust=False, threads=False, progress=False,
                                            multi_level_index=False, timeout=20, repair=False)
                    if candidate is not None and not candidate.empty:
                        frame = clean_prices(candidate)
                        break
                    time.sleep(1 + attempt)
                if frame is None:
                    raise ValueError("Provider returned no observations after three attempts")
                frame.to_csv(path, date_format="%Y-%m-%d")
                metadata = {"requestedStart": start, "requestedEndExclusive": end, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
            entry = {"ticker": symbol, "kind": "index" if symbol in indices else "equity", "file": f"data/raw/prices/{path.name}",
                     "rows": len(frame), "firstDate": str(frame.index.min().date()), "lastDate": str(frame.index.max().date()),
                     "sha256": metadata["sha256"], "provider": metadata.get("provider", "yfinance"), "sources": metadata.get("sources") or [quote_source(symbol)]}
            manifest["prices"].append(entry)
            LOGGER.info("%s: %s daily prices (%s to %s)", symbol, len(frame), entry["firstDate"], entry["lastDate"])
        except Exception as exc:
            manifest["failures"].append({"ticker": symbol, "reason": type(exc).__name__ + ": " + str(exc)[:180]})
            LOGGER.error("%s: price download failed (%s)", symbol, type(exc).__name__)
    (manifest_path or ROOT / "data/processed/price_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--map-only", action="store_true")
    parser.add_argument("--reuse-map", action="store_true")
    parser.add_argument("--start", default="2010-01-01")
    parser.add_argument("--end", default="2026-10-14", help="Exclusive end; default excludes the current incomplete trading day")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = json.loads((ROOT / "data/sources/markets.json").read_text(encoding="utf-8"))
    mapping = json.loads((ROOT / "data/processed/ticker_map.json").read_text(encoding="utf-8")) if args.reuse_map else resolve_suppliers(config, args.offline)
    if args.map_only:
        return 0
    manifest = download_prices(mapping, config, args.start, args.end, args.offline)
    return int(bool(manifest["failures"]))


if __name__ == "__main__":
    raise SystemExit(main())
