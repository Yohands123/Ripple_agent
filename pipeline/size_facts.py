"""Cache public SEC company facts for timestamp-filtered company-size features."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pipeline.sec_filings import SecClient

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    client = SecClient(os.environ.get("SEC_USER_AGENT", ""))
    mapping = json.loads((ROOT / "data/processed/ticker_map.json").read_text(encoding="utf-8"))
    ciks = sorted({r["cik"] for r in mapping["mapped"] if r.get("cik")})
    gaps = []
    for cik in ciks:
        try:
            document = client.cached_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json", ROOT / f"data/raw/company_facts/CIK{cik:010d}.json")
            if int(document["cik"]) != cik:
                raise ValueError("Company-facts issuer differs from requested CIK")
            print(f"CIK{cik:010d}: company facts cached", flush=True)
        except Exception as exc:
            gaps.append({"cik": cik, "reason": type(exc).__name__})
    (ROOT / "data/raw/company_facts/download_gaps.json").write_text(json.dumps(gaps, indent=2) + "\n", encoding="utf-8")
    return int(bool(gaps))


if __name__ == "__main__":
    raise SystemExit(main())
