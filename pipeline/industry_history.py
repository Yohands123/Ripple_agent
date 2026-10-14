"""Read contemporaneous SIC and exchange evidence from pre-event SEC filings."""

from __future__ import annotations

import csv
import html
import json
import os
import re
from pathlib import Path

from pipeline.sec_filings import SecClient, filing_rows

ROOT = Path(__file__).resolve().parents[1]


def parse_evidence(prefix: bytes, expected_cik: int) -> dict:
    text = prefix.decode("utf-8", errors="replace")
    header = text.split("</SEC-HEADER>", 1)[0]
    cik = re.search(r"CENTRAL\s+INDEX\s+KEY:\s*(\d+)", header, re.I)
    sic = re.search(r"STANDARD\s+INDUSTRIAL\s+CLASSIFICATION:\s*([^\r\n\[]+)\[(\d{4})\]", header, re.I)
    if not cik or int(cik[1]) != expected_cik or not sic:
        raise ValueError("Contemporaneous filer CIK or SIC is unavailable")
    # Use the registered-securities cover table, not mentions of exchanges in
    # the report's business discussion or stock-performance comparison chart.
    plain = html.unescape(re.sub(r"<[^>]+>", " ", text))
    plain = " ".join(plain.split())
    start = re.search(r"securities\s+registered(?:\s+or\s+to\s+be\s+registered)?\s+pursuant\s+to\s+section\s+12\s*\(\s*b\s*\)", plain, re.I)
    exchange, excerpt = None, None
    if start:
        cover = plain[start.start():start.start() + 6000]
        end = re.search(r"securities\s+registered(?:\s+or\s+to\s+be\s+registered)?\s+pursuant\s+to\s+section\s+12\s*\(\s*g\s*\)|indicate\s+by\s+check\s*mark|check\s+one", cover, re.I)
        if end:
            cover = cover[:end.start()]
        found = set()
        if re.search(r"Nasdaq", cover, re.I):
            found.add("NASDAQ")
        if re.search(r"New\s+York\s+Stock\s+Exchange|\bNYSE\b", cover, re.I):
            found.add("NYSE")
        if len(found) == 1:
            exchange = found.pop()
            excerpt = cover[:1400]
    return {"sic": sic[2], "industry": sic[1].strip(), "exchange": exchange, "exchangeEvidence": excerpt}


def main() -> int:
    client = SecClient(os.environ.get("SEC_USER_AGENT", ""))
    registry = client.cached_json("https://www.sec.gov/files/company_tickers_exchange.json", ROOT / "data/raw/listings/SEC.json")
    by_ticker = {row[2]: row for row in registry["data"]}
    mapping = json.loads((ROOT / "data/processed/ticker_map.json").read_text(encoding="utf-8"))
    candidates = json.loads((ROOT / "data/sources/peer_candidates.json").read_text(encoding="utf-8"))["tickers"]
    tickers = set(candidates) | {r["ticker"] for r in mapping["mapped"] if r.get("cik")}
    events = list(csv.DictReader((ROOT / "data/events.csv").open(encoding="utf-8")))
    raw = ROOT / "data/raw/industry_headers"
    raw.mkdir(parents=True, exist_ok=True)
    output, gaps = [], []
    for ticker in sorted(tickers):
        issuer = by_ticker.get(ticker)
        if not issuer:
            continue
        cik = str(issuer[0]).zfill(10)
        try:
            submission = client.cached_json(f"https://data.sec.gov/submissions/CIK{cik}.json", ROOT / f"data/raw/sec/CIK{cik}.json")
            entries = filing_rows(submission["filings"]["recent"])
            for archive in submission["filings"].get("files", []):
                if archive["filingTo"] >= "2014-01-01" and archive["filingFrom"] <= max(e["start"] for e in events):
                    document = client.cached_json("https://data.sec.gov/submissions/" + archive["name"], ROOT / "data/raw/sec" / archive["name"])
                    entries.extend(filing_rows(document))
            for event in events:
                cutoff = event.get("knowledgeCutoffDate") or event["start"]
                annual = [r for r in entries if r.get("form") in {"10-K", "20-F"} and r.get("filingDate", "9999") < cutoff]
                if not annual:
                    gaps.append({"ticker": ticker, "eventId": event["id"], "reason": "No pre-event annual filing found"})
                    continue
                entry = max(annual, key=lambda r: r["filingDate"])
                accession = entry["accessionNumber"]
                url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{accession}.txt"
                path = raw / f"{cik}_{accession}.header.txt"
                try:
                    if not path.exists():
                        # Cache only the public filing prefix: complete filings
                        # can contain very large image/exhibit attachments.
                        prefix = client.get(url, limit_bytes=256 * 1024)
                        parse_evidence(prefix, int(cik))
                        path.write_bytes(prefix)
                    evidence = parse_evidence(path.read_bytes(), int(cik))
                    output.append({"eventId": event["id"], "ticker": ticker, "cik": int(cik), "filedOn": entry["filingDate"], **evidence,
                                   "source": {"title": f"SEC pre-event annual filing: {submission['name']} ({entry['filingDate']})", "url": url}})
                except Exception as exc:
                    gaps.append({"ticker": ticker, "eventId": event["id"], "reason": type(exc).__name__})
            print(f"{ticker}: pre-event classifications inspected", flush=True)
        except Exception as exc:
            gaps.append({"ticker": ticker, "reason": type(exc).__name__})
    result = {"sampleData": False, "method": "SIC from archived filing header; exchange from registered-securities cover; most recent annual filing published before event",
              "classifications": output, "gaps": gaps}
    (ROOT / "data/processed/industry_history.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Pre-event classifications: {len(output)}, including {sum(r['exchange'] is not None for r in output)} verified exchanges; gaps: {len(gaps)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
