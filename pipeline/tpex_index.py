"""Cache the TPEx's own daily market index from its public monthly reports."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import ssl
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCE = {"title": "Taipei Exchange: Historical Data of TPEx Index", "url": "https://www.tpex.org.tw/en-us/indices/stock-index/industrial/inxh.html"}


def parse_month(document: dict, year: int, month: int) -> list[dict]:
    if document.get("stat") != "ok" or len(document.get("tables", [])) != 1:
        raise ValueError("TPEx monthly index report is unavailable or ambiguous")
    table = document["tables"][0]
    if table["fields"] != ["Date", "Open", "High", "Low", "Close", "Change(%)"]:
        raise ValueError("TPEx index columns changed")
    rows = []
    for values in table["data"]:
        observed = date.fromisoformat(values[0].replace("/", "-"))
        if (observed.year, observed.month) != (year, month):
            raise ValueError("Observation is outside requested month")
        row = {"Date": observed.isoformat()}
        for field, value in zip(table["fields"][1:5], values[1:5]):
            price = float(value.replace(",", ""))
            if not math.isfinite(price) or price <= 0:
                raise ValueError("Invalid published index level")
            row[field] = price
        # This is a published price-index level, not an equity needing a split
        # adjustment. Both columns contain exactly the observed index close.
        row["Adj Close"] = row["Close"]
        rows.append(row)
    if len(rows) != table["totalCount"] or not rows:
        raise ValueError("TPEx monthly row count is incomplete")
    return rows


def download(start: str, end: str, offline: bool = False) -> int:
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if first >= last:
        raise ValueError("Start must precede exclusive end")
    context = ssl.create_default_context()
    # The exchange's trusted legacy CA lacks a Subject Key Identifier. Keep
    # certificate-chain verification and hostname verification enabled; relax
    # only the newer OpenSSL strict extension requirement for this host.
    context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    raw = ROOT / "data/raw/tpex"
    raw.mkdir(parents=True, exist_ok=True)
    year, month = max(first, date(2012, 4, 1)).timetuple()[:2]
    rows, failures, requests = [], [], []
    while date(year, month, 1) < last:
        url = "https://www.tpex.org.tw/www/en-us/indexInfo/inx?" + urlencode({"date": f"{year}/{month:02d}/01", "response": "json"})
        path = raw / f"{year}-{month:02d}.json"
        try:
            if path.exists():
                document = json.loads(path.read_text(encoding="utf-8"))
            elif offline:
                raise FileNotFoundError("Monthly TPEx report is not cached")
            else:
                document = None
                for attempt in range(3):
                    try:
                        request = Request(url, headers={"User-Agent": "Ripple public-data research", "Accept": "application/json"})
                        with urlopen(request, context=context, timeout=20) as response:
                            body = response.read()
                        document = json.loads(body)
                        parse_month(document, year, month)
                        path.write_bytes(body)
                        time.sleep(0.2)
                        break
                    except Exception:
                        if attempt == 2:
                            raise
                        time.sleep(1 + attempt)
            rows.extend(parse_month(document, year, month))
            requests.append(url)
        except Exception as exc:
            failures.append({"month": f"{year}-{month:02d}", "reason": type(exc).__name__})
        month += 1
        if month == 13:
            year, month = year + 1, 1
            print(f"TPEx through {year - 1}: {len(rows)} observations, {len(failures)} failed months", flush=True)
    (raw / "failures.json").write_text(json.dumps(failures, indent=2) + "\n", encoding="utf-8")
    if failures:
        return 1
    rows = sorted((row for row in rows if start <= row["Date"] < end), key=lambda row: row["Date"])
    if not rows or len({row["Date"] for row in rows}) != len(rows):
        raise ValueError("Missing or duplicate TPEx index observations")
    output = ROOT / "data/raw/prices/TPEXINDEX.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Date", "Open", "High", "Low", "Close", "Adj Close"])
        writer.writeheader()
        writer.writerows(rows)
    metadata = {"requestedStart": start, "requestedEndExclusive": end, "availableFrom": "2012-04-01", "provider": "Taipei Exchange",
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "closeType": "published price-index level", "sources": [SOURCE], "monthlyRequests": requests}
    output.with_suffix(".source.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"TPEx index cached: {len(rows)} observations; {rows[0]['Date']} to {rows[-1]['Date']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2010-01-01")
    parser.add_argument("--end", default="2026-10-14")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    return download(args.start, args.end, args.offline)


if __name__ == "__main__":
    raise SystemExit(main())
