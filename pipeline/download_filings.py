"""Cache public filing PDFs with the standard library (also runs on Windows).

The Windows and WSL environments share the project's raw cache. This command
needs no global Python packages and can download using the Windows network
when WSL outbound connections are unavailable.
"""

from __future__ import annotations

import csv
import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def download_one(issuer: dict, year: int, bases: list[str], raw: Path, direct_url: str | None = None) -> tuple[str, int, bool]:
    path = raw / f"{issuer['id']}_{year}.pdf"
    meta = path.with_suffix(".source.json")
    if path.exists() and meta.exists():
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() == json.loads(meta.read_text(encoding="utf-8"))["sha256"]:
            return issuer["id"], year, True
        raise ValueError(f"Cached report changed: {path.name}")
    keys = [issuer["archive"]]
    if issuer.get("alternateArchive"):
        keys.append(issuer["alternateArchive"])
    urls = ([direct_url] if direct_url else []) + [f"{base}{key}_{year}.pdf" for base in bases for key in keys]
    for url in urls:
        try:
            with urlopen(Request(url, headers={"User-Agent": "Ripple-public-data/1.0"}), timeout=15) as response:
                content = response.read()
            if not content.startswith(b"%PDF-"):
                continue
            path.write_bytes(content)
            meta.write_text(json.dumps({"url": url, "sha256": hashlib.sha256(content).hexdigest()}) + "\n", encoding="utf-8")
            return issuer["id"], year, True
        except (HTTPError, URLError, TimeoutError, ConnectionError):
            continue
    return issuer["id"], year, False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direct-only", action="store_true", help="Skip archives and fetch only issuer URLs")
    args = parser.parse_args()
    registry = json.loads((ROOT / "data/sources/filings.json").read_text(encoding="utf-8"))
    direct_file = ROOT / "data/sources/filing_urls.json"
    direct = json.loads(direct_file.read_text(encoding="utf-8")) if direct_file.exists() else {}
    raw = ROOT / "data/raw/filings"
    raw.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / "data/interim/supplier_list_manifest.json").read_text(encoding="utf-8"))
    jobs = {}
    for edition in manifest["editions"]:
        year = edition["snapshotYear"]
        with (ROOT / f"data/interim/suppliers_{year}.csv").open(encoding="utf-8") as handle:
            names = {r["supplier"] for r in csv.DictReader(handle)}
        for issuer in registry["issuers"]:
            if any(re.search(issuer["match"], name, re.I) for name in names):
                jobs[(issuer["id"], year)] = issuer
    successes = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(download_one, issuer, year, [] if args.direct_only else registry["archives"], raw, direct.get(issuer["id"], {}).get(str(year))) for (_, year), issuer in sorted(jobs.items())]
        for future in as_completed(futures):
            issuer, year, ok = future.result()
            successes += int(ok)
            print(f"{issuer} FY{year}: {'cached' if ok else 'unavailable'}", flush=True)
    print(f"Downloaded {successes}/{len(jobs)} public reports; missing reports remain explicit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
