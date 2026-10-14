"""Verify SEC-classified exchange/industry comparison companies for events."""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def download_metadata() -> int:
    from pipeline.sec_filings import SecClient
    client = SecClient(os.environ.get("SEC_USER_AGENT", ""))
    tickers = client.cached_json("https://www.sec.gov/files/company_tickers_exchange.json", ROOT / "data/raw/listings/SEC.json")
    by_ticker = {row[2]: row for row in tickers["data"]}
    candidates = json.loads((ROOT / "data/sources/peer_candidates.json").read_text(encoding="utf-8"))["tickers"]
    gaps = []
    for ticker in candidates:
        row = by_ticker.get(ticker)
        if not row:
            gaps.append({"ticker": ticker, "reason": "Absent from current SEC issuer registry"})
            continue
        cik = str(row[0]).zfill(10)
        try:
            client.cached_json(f"https://data.sec.gov/submissions/CIK{cik}.json", ROOT / f"data/raw/sec/CIK{cik}.json")
            print(f"{ticker}: SEC industry metadata cached", flush=True)
        except Exception as exc:
            gaps.append({"ticker": ticker, "reason": type(exc).__name__})
    (ROOT / "data/raw/sec/peer_metadata_gaps.json").write_text(json.dumps(gaps, indent=2) + "\n", encoding="utf-8")
    return int(bool(gaps))


def build_matches() -> dict:
    from pipeline.event_study import listing_for_event, supplier_mapping_index
    from pipeline.prices import canonical_exchange, company_key
    config = json.loads((ROOT / "data/sources/markets.json").read_text(encoding="utf-8"))
    rows = json.loads((ROOT / "data/raw/listings/SEC.json").read_text(encoding="utf-8"))["data"]
    by_ticker = {row[2]: row for row in rows}
    candidates = json.loads((ROOT / "data/sources/peer_candidates.json").read_text(encoding="utf-8"))["tickers"]
    peers, gaps = [], []
    for ticker in candidates:
        row = by_ticker.get(ticker)
        path = ROOT / f"data/raw/sec/CIK{str(row[0]).zfill(10)}.json" if row else None
        if not path or not path.exists():
            gaps.append({"ticker": ticker, "reason": "Verified SEC industry metadata unavailable"})
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        exchange = canonical_exchange(row[3], config)
        if not document.get("sic") or exchange not in config["benchmarks"]:
            continue
        peers.append({"ticker": ticker, "exchange": exchange, "benchmark": config["benchmarks"][exchange]["symbol"], "listedName": document["name"],
                      "sic": document["sic"], "industry": document["sicDescription"], "cik": row[0],
                      "verifiedIssuerNames": [document["name"]] + [r["name"] for r in document.get("formerNames", [])],
                      "sources": [{"title": f"SEC issuer exchange and SIC: {document['name']}", "url": f"https://data.sec.gov/submissions/CIK{str(row[0]).zfill(10)}.json"}]})
    mapping = json.loads((ROOT / "data/processed/ticker_map.json").read_text(encoding="utf-8"))
    history_path = ROOT / "data/processed/industry_history.json"
    history = {(r["eventId"], r["ticker"]): r for r in json.loads(history_path.read_text(encoding="utf-8"))["classifications"]} if history_path.exists() else {}
    by_name = supplier_mapping_index(mapping)
    events = list(csv.DictReader((ROOT / "data/events.csv").open(encoding="utf-8")))
    matches, unmatched, event_peers = [], [], {}
    for event in events:
        path = ROOT / f"data/interim/suppliers_{event['snapshotYear']}.csv"
        if not path.exists():
            continue
        names = {company_key(r["supplier"]): r["supplier"] for r in csv.DictReader(path.open(encoding="utf-8"))}
        known_tickers = {r["ticker"] for key in names for r in by_name[key]}
        for key, name in names.items():
            unique = {r["ticker"]: r for r in by_name[key]}
            if len(unique) != 1:
                continue
            record = listing_for_event(next(iter(unique.values())), name, event["start"])
            historical = history.get((event["id"], record.get("ticker")))
            if not historical or not historical.get("exchange"):
                unmatched.append({"eventId": event["id"], "supplier": name, "reason": "Verified pre-event SIC or exchange unavailable"})
                continue
            industry, exchange = historical["sic"], historical["exchange"]
            eligible = []
            for peer in peers:
                classification = history.get((event["id"], peer["ticker"]))
                if peer["ticker"] in known_tickers or any(company_key(n) in names for n in peer["verifiedIssuerNames"]) or not classification:
                    continue
                if classification["exchange"] == exchange and classification["sic"] == industry:
                    eligible.append({**peer, "eventId": event["id"], "exchange": exchange, "benchmark": config["benchmarks"][exchange]["symbol"],
                                     "sic": industry, "industry": classification["industry"], "filedOn": classification["filedOn"],
                                     "sources": peer["sources"] + [classification["source"]]})
            eligible.sort(key=lambda p: p["ticker"])
            for peer in eligible[:3]:
                event_peers[(event["id"], peer["ticker"])] = peer
                matches.append({"eventId": event["id"], "supplier": name, "supplierTicker": record["ticker"], "peerTicker": peer["ticker"], "exchange": peer["exchange"],
                                "sic": industry, "supplierClassificationFiledOn": historical["filedOn"], "peerClassificationFiledOn": peer["filedOn"],
                                "sources": [historical["source"], peer["sources"][-1]],
                                "selection": "First three alphabetic candidates with identical pre-event exchange and four-digit SIC; selection uses no event returns"})
            if not eligible:
                unmatched.append({"eventId": event["id"], "supplier": name, "reason": "No eligible same-exchange and same-SIC candidate"})
    used = {m["peerTicker"] for m in matches}
    result = {"sampleData": False, "classificationAsOf": "Most recent annual filing published before each event",
              "unlinkedDefinition": "Not named or ticker-linked in the event-year top Supplier List; no observed link in this dataset, not proof of no Apple relationship",
              "limitation": "Candidates come from the current SEC listing universe, introducing survivorship limits. Not-listed controls may still have undisclosed or lower-tier Apple links. Foreign issuers without verified pre-event SEC classification remain unmatched.",
              "peers": [p for p in peers if p["ticker"] in used], "peerEventRecords": list(event_peers.values()), "matches": matches, "unmatched": unmatched, "metadataGaps": gaps}
    (ROOT / "data/processed/peer_matches.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Matched controls: {len(matches)} pairs, {len(used)} distinct peers; {len(unmatched)} unmatched suppliers")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-metadata", action="store_true")
    parser.add_argument("--prices", action="store_true")
    args = parser.parse_args()
    if args.download_metadata:
        return download_metadata()
    result = build_matches()
    if args.prices:
        from pipeline.prices import download_prices
        config = json.loads((ROOT / "data/sources/markets.json").read_text(encoding="utf-8"))
        manifest = download_prices({"mapped": result["peers"], "counts": {"peerTickers": len(result["peers"])}}, config, "2010-01-01", "2026-10-14",
                                   manifest_path=ROOT / "data/processed/peer_price_manifest.json")
        return int(bool(manifest["failures"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
