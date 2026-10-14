"""Cache public EDGAR annual filings using SEC_USER_AGENT and paced requests."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


class SecClient:
    def __init__(self, user_agent: str):
        if not user_agent.strip():
            raise ValueError("SEC_USER_AGENT is required; no placeholder identity is permitted")
        self.user_agent = user_agent
        self.last_request = 0.0

    def get(self, url: str, limit_bytes: int | None = None) -> bytes:
        # Sequential requests at at most five per second, below the SEC limit.
        delay = 0.2 - (time.monotonic() - self.last_request)
        if delay > 0:
            time.sleep(delay)
        self.last_request = time.monotonic()
        request = Request(url, headers={"User-Agent": self.user_agent, "Accept-Encoding": "identity"})
        with urlopen(request, timeout=20) as response:
            return response.read() if limit_bytes is None else response.read(limit_bytes)

    def cached_json(self, url: str, path: Path) -> dict:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        data = self.get(url)
        document = json.loads(data)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return document


def filing_rows(columns: dict) -> list[dict]:
    if not columns or not columns.get("accessionNumber"):
        return []
    return [{key: values[i] for key, values in columns.items() if isinstance(values, list) and len(values) > i}
            for i in range(len(columns["accessionNumber"]))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exchange-registry", action="store_true", help="Cache the public ticker/exchange registry only")
    args = parser.parse_args()
    client = SecClient(os.environ.get("SEC_USER_AGENT", ""))
    if args.exchange_registry:
        document = client.cached_json("https://www.sec.gov/files/company_tickers_exchange.json", ROOT / "data/raw/listings/SEC.json")
        print(f"Cached SEC ticker/exchange registry: {len(document['data'])} records")
        return 0
    registry = json.loads((ROOT / "data/sources/filings.json").read_text(encoding="utf-8"))
    raw = ROOT / "data/raw/filings"
    sec_raw = ROOT / "data/raw/sec"
    raw.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / "data/interim/supplier_list_manifest.json").read_text(encoding="utf-8"))
    years_by_issuer = {}
    for edition in manifest["editions"]:
        year = edition["snapshotYear"]
        with (ROOT / f"data/interim/suppliers_{year}.csv").open(encoding="utf-8") as handle:
            names = {row["supplier"] for row in csv.DictReader(handle)}
        for issuer in registry["issuers"]:
            if any(re.search(issuer["match"], name, re.I) for name in names):
                years_by_issuer.setdefault(issuer["id"], []).append(year)
    tickers = client.cached_json("https://www.sec.gov/files/company_tickers.json", sec_raw / "company_tickers.json")
    by_ticker = {row["ticker"]: row for row in tickers.values()}
    failures, count = [], 0
    for issuer in registry["issuers"]:
        years = years_by_issuer.get(issuer["id"], [])
        needed = [year for year in years if not (raw / f"{issuer['id']}_{year}.source.json").exists()]
        if not needed:
            continue
        ticker = issuer.get("secTicker") or issuer["archive"].rsplit("_", 1)[-1]
        company = by_ticker.get(ticker)
        if company is None:
            failures.append({"issuerId": issuer["id"], "reason": "Issuer is absent from current SEC ticker registry"})
            continue
        cik = str(company["cik_str"]).zfill(10)
        try:
            submission = client.cached_json(f"https://data.sec.gov/submissions/CIK{cik}.json", sec_raw / f"CIK{cik}.json")
            entries = filing_rows(submission["filings"]["recent"])
            for archive in submission["filings"].get("files", []):
                if archive["filingTo"] >= f"{min(needed)}-01-01" and archive["filingFrom"] <= f"{max(needed)+2}-12-31":
                    history = client.cached_json(f"https://data.sec.gov/submissions/{archive['name']}", sec_raw / archive["name"])
                    entries.extend(filing_rows(history))
            for year in needed:
                candidates = [entry for entry in entries if entry.get("form") in {"10-K", "20-F"} and entry.get("reportDate", "").startswith(str(year))]
                if not candidates:
                    failures.append({"issuerId": issuer["id"], "reportYear": year, "reason": "No original annual filing found for requested reporting year"})
                    continue
                # Original filing, earliest publication; do not quietly select
                # a later amendment as contemporaneous historical information.
                entry = min(candidates, key=lambda item: item["filingDate"])
                accession = entry["accessionNumber"].replace("-", "")
                url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{entry['primaryDocument']}"
                data = client.get(url)
                extension = ".pdf" if data.startswith(b"%PDF-") else ".html"
                if extension == ".html" and b"<" not in data[:500]:
                    raise ValueError("Annual filing did not return PDF or HTML")
                path = raw / f"{issuer['id']}_{year}{extension}"
                path.write_bytes(data)
                focus = re.search(r'name=["\']dei:DocumentFiscalYearFocus["\'][^>]*>\s*(20\d{2})\s*<', data.decode("utf-8", errors="replace"), re.I) if extension == ".html" else None
                path.with_suffix(".source.json").write_text(json.dumps({"url": url, "sha256": hashlib.sha256(data).hexdigest(), "filedOn": entry["filingDate"],
                                                                       "reportDate": entry["reportDate"], "fiscalYearFocus": int(focus[1]) if focus else None,
                                                                       "form": entry["form"], "companyName": submission["name"]}) + "\n", encoding="utf-8")
                count += 1
                print(f"{issuer['id']} FY{year}: cached {entry['form']}, published {entry['filingDate']}", flush=True)
        except (HTTPError, URLError, TimeoutError, ConnectionError, ValueError) as exc:
            failures.append({"issuerId": issuer["id"], "reason": type(exc).__name__})
            print(f"{issuer['id']}: unavailable ({type(exc).__name__})", flush=True)
    (sec_raw / "download_gaps.json").write_text(json.dumps(failures, indent=2) + "\n", encoding="utf-8")
    print(f"SEC filings downloaded: {count}; recorded gaps: {len(failures)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
