"""Extract company attributes from the most recent annual filing before events."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def filing_years(document: dict) -> dict[str, set[int]]:
    result = {}
    for taxonomy in document.get("facts", {}).values():
        for concept in taxonomy.values():
            for observations in concept.get("units", {}).values():
                for observation in observations:
                    if observation.get("form") in {"10-K", "20-F"} and observation.get("accn") and observation.get("fy"):
                        result.setdefault(observation["accn"], set()).add(int(observation["fy"]))
    return result


def download() -> int:
    from pipeline.sec_filings import SecClient
    client = SecClient(os.environ.get("SEC_USER_AGENT", ""))
    classifications = json.loads((ROOT / "data/processed/industry_history.json").read_text(encoding="utf-8"))["classifications"]
    tickers = {r["ticker"] for r in json.loads((ROOT / "data/processed/ticker_map.json").read_text(encoding="utf-8"))["mapped"] if r.get("cik")}
    raw = ROOT / "data/raw/historical_profiles"
    raw.mkdir(parents=True, exist_ok=True)
    existing = {}
    for path in (ROOT / "data/raw/filings").glob("*.source.json"):
        metadata = json.loads(path.read_text(encoding="utf-8"))
        candidate = path.with_name(path.name.replace(".source.json", ".html"))
        if candidate.exists():
            existing[metadata["url"]] = candidate
    gaps, completed = [], set()
    for record in classifications:
        if record["ticker"] not in tickers:
            continue
        accession = record["source"]["url"].rsplit("/", 1)[-1].removesuffix(".txt")
        key = f"{record['cik']:010d}_{accession}"
        if key in completed:
            continue
        completed.add(key)
        prefix = (ROOT / f"data/raw/industry_headers/{key}.header.txt").read_text(encoding="utf-8", errors="replace")
        filename = re.search(r"<FILENAME>([^\r\n]+)", prefix)
        period = re.search(r"CONFORMED\s+PERIOD\s+OF\s+REPORT:\s*(\d{8})", prefix)
        if not filename or not period:
            gaps.append({"ticker": record["ticker"], "filedOn": record["filedOn"], "reason": "Primary document or reporting period unavailable"})
            continue
        url = record["source"]["url"].rsplit("/", 1)[0] + "/" + filename[1].strip()
        output = raw / f"{key}.html"
        metadata_path = output.with_suffix(".source.json")
        try:
            if not metadata_path.exists():
                body = existing[url].read_bytes() if url in existing else client.get(url)
                if b"<" not in body[:500]:
                    raise ValueError("Annual primary document is not HTML/XML")
                output.write_bytes(body)
                focus = re.search(r'name=["\']dei:DocumentFiscalYearFocus["\'][^>]*>\s*(20\d{2})\s*<', body.decode("utf-8", errors="replace"), re.I)
                metadata = {"url": url, "filedOn": record["filedOn"], "reportDate": f"{period[1][:4]}-{period[1][4:6]}-{period[1][6:]}",
                            "fiscalYearFocus": int(focus[1]) if focus else None, "sha256": hashlib.sha256(body).hexdigest(), "cik": record["cik"], "ticker": record["ticker"]}
                metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
            print(f"{record['ticker']} filing {record['filedOn']}: annual report cached", flush=True)
        except Exception as exc:
            gaps.append({"ticker": record["ticker"], "filedOn": record["filedOn"], "reason": type(exc).__name__})
    (raw / "download_gaps.json").write_text(json.dumps(gaps, indent=2) + "\n", encoding="utf-8")
    return int(bool(gaps))


def extract() -> int:
    from pipeline.extract_profiles import apple_revenue_share, product_category, report_pages
    from pipeline.prices import company_key
    registry = json.loads((ROOT / "data/sources/filings.json").read_text(encoding="utf-8"))
    mapping = json.loads((ROOT / "data/processed/ticker_map.json").read_text(encoding="utf-8"))
    by_ticker = {}
    for record in mapping["mapped"]:
        by_ticker.setdefault(record["ticker"], []).append(record["supplier"])
    output, review, year_cache = [], [], {}
    for metadata_path in sorted((ROOT / "data/raw/historical_profiles").glob("*.source.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        path = metadata_path.with_name(metadata_path.name.replace(".source.json", ".html"))
        if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["sha256"]:
            raise ValueError("Historical report hash mismatch")
        names = by_ticker.get(metadata["ticker"], [])
        issuer = next((i for i in registry["issuers"] if any(re.search(i["match"], n, re.I) for n in names)), None)
        if not issuer:
            continue
        pages = report_pages(path)
        category, _ = product_category(pages, issuer)
        cik = metadata["cik"]
        if cik not in year_cache:
            facts = ROOT / f"data/raw/company_facts/CIK{cik:010d}.json"
            year_cache[cik] = filing_years(json.loads(facts.read_text(encoding="utf-8"))) if facts.exists() else {}
        accession = path.stem.split("_", 1)[1]
        years = year_cache[cik].get(accession, set())
        if metadata["fiscalYearFocus"]:
            years = years | {metadata["fiscalYearFocus"]}
        year = next(iter(years)) if len(years) == 1 else None
        share, evidence = apple_revenue_share(" ".join(pages), year) if year else (None, None)
        label = f"FY{year}" if year else f"period ending {metadata['reportDate']}"
        header = (ROOT / f"data/raw/industry_headers/{path.stem}.header.txt").read_text(encoding="utf-8", errors="replace")
        filer = re.search(r"COMPANY\s+CONFORMED\s+NAME:\s*([^\r\n]+)", header)
        identity = filer[1].strip() if filer else issuer["identity"]
        source = {"title": f"{identity} annual report, {label}, filed {metadata['filedOn']}", "url": metadata["url"]}
        for name in dict.fromkeys(names):
            record = {"supplier": name, "issuerId": issuer["id"], "partType": category, "partTypeSource": source if category else None,
                      "appleRevenueShare": share, "appleRevenueShareSource": source if share is not None else None, "revenueEvidence": evidence,
                      "filedOn": metadata["filedOn"], "reportDate": metadata["reportDate"], "reportFiscalYear": year, "extractionMethod": "rule-based"}
            output.append(record)
        for field, value in [("partType", category), ("appleRevenueShare", share)]:
            if value is not None:
                review.append({"ticker": metadata["ticker"], "field": field, "value": value, "filedOn": metadata["filedOn"], "sourceTitle": source["title"], "sourceUrl": source["url"], "verificationStatus": "pending"})
    (ROOT / "data/processed/historical_profiles.json").write_text(json.dumps({"sampleData": False, "method": "rule-based; annual reports selected before events", "profiles": output}, indent=2) + "\n", encoding="utf-8")
    with (ROOT / "data/review/pre_event_attributes.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ticker", "field", "value", "filedOn", "sourceTitle", "sourceUrl", "verificationStatus"])
        writer.writeheader()
        writer.writerows(review)
    print(f"Historical attributes: {len(output)} issuer-name/report records; {len(review)} sourced attribute links")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    raise SystemExit(download() if args.download else extract())
