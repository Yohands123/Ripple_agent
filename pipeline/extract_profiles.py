"""Extract auditable supplier attributes from public annual reports.

Only explicitly named Apple revenue percentages with an unambiguous year are
accepted. Anonymous customer concentration is never attributed to Apple.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import random
import re
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pypdfium2 as pdfium
import requests

ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)
YEAR_LIST = r"20\d{2}(?:\s*,\s*20\d{2})*(?:\s*,?\s*and\s*20\d{2})?"
PERCENT = r"\d{1,3}(?:\.\d+)?\s*(?:%|percent)"
PERCENT_LIST = rf"{PERCENT}(?:\s*,\s*{PERCENT})*(?:\s*,?\s*and\s*{PERCENT})?"


def normalize_text(text: str) -> str:
    return " ".join(text.replace("\u00ad", "").split())


def apple_revenue_share(text: str, year: int) -> tuple[float | None, dict | None]:
    text = normalize_text(text)
    patterns = [
        (rf"(?:fiscal(?: years?)?|years?)\s+(?P<years>{YEAR_LIST}).{{0,250}}?\bApple(?:\s+Inc\.?)?.{{0,550}}?(?:accounted for|represented|constituted)\s+(?:approximately\s+)?(?P<values>{PERCENT_LIST}).{{0,100}}?(?:revenue|sales).{{0,65}}?respectively", False),
        (rf"\bApple(?:\s+Inc\.?)?.{{0,250}}?(?:accounted for|represented|constituted)\s+(?:approximately\s+)?(?P<values>{PERCENT_LIST}).{{0,120}}?(?:revenue|sales).{{0,100}}?(?:fiscal(?: years?)?|years?)\s+(?P<years>{YEAR_LIST}).{{0,25}}?respectively", False),
        (rf"(?:net revenue|net sales|total sales).{{0,250}}?Fiscal Year Ended.{{0,60}}?(?P<years>20\d{{2}}(?:\s+20\d{{2}}){{1,4}})\s+Apple(?:,?\s+Inc\.?)?\s+(?P<values>(?:\d{{1,3}}(?:\.\d+)?\s*%\s*){{2,5}})", False),
        (rf"\bApple(?:,?\s+Inc\.?)?.{{0,180}}?(?:accounted for|represented|constituted)\s+(?:approximately\s+)?(?P<values>{PERCENT}).{{0,65}}?(?:revenue|sales)\s+for each of(?: our)? fiscal years\s+(?P<years>{YEAR_LIST})", True),
        (rf"\bApple(?:,?\s+Inc\.?)?.{{0,180}}?(?:accounted for|represented|constituted)\s+(?:approximately\s+)?(?P<values>{PERCENT}).{{0,65}}?(?:revenue|sales)\s+(?:for|in)\s+(?:our\s+)?fiscal year\s+(?P<years>20\d{{2}})", False),
    ]
    candidates = []
    for pattern, repeated in patterns:
        # Lookahead allows an invalid earlier fiscal-year mention to overlap
        # the actual disclosure, rather than consuming and hiding it.
        for match in re.finditer(rf"(?=(?P<disclosure>{pattern}))", text, re.I):
            years = [int(value) for value in re.findall(r"20\d{2}", match["years"])]
            values = [float(value) / 100 for value in re.findall(r"(\d{1,3}(?:\.\d+)?)\s*(?:%|percent)", match["values"], re.I)]
            segment = match["disclosure"]
            # Receivables, anonymous customers, bounds, and combined-customer
            # shares are different measures and cannot fill this scalar field.
            before_values = segment[:segment.index(match["values"])]
            if re.search(r"receivable|more than|less than|at least|at most|Apple(?: Inc\.?)?\s+and\s+[A-Z]", before_values, re.I):
                continue
            if repeated and len(values) == 1:
                values = values * len(years)
            if len(years) != len(values) or len(set(years)) != len(years) or year not in years:
                continue
            value = values[years.index(year)]
            if 0 <= value <= 1:
                candidates.append((value, {"reportedYear": year, "percentage": value * 100, "method": "named Apple revenue disclosure; ordered years and percentages"}))
    distinct = {round(value, 8) for value, _ in candidates}
    if len(distinct) == 1:
        return candidates[0]
    return None, None


def report_pages(path: Path) -> list[str]:
    cache = path.with_suffix(".txt")
    if cache.exists():
        return cache.read_text(encoding="utf-8").split("\n\f\n")
    if path.suffix == ".html":
        class TextParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.output, self.skipped = [], 0
            def handle_starttag(self, tag, attrs):
                if tag in {"script", "style"}:
                    self.skipped += 1
            def handle_endtag(self, tag):
                if tag in {"script", "style"}:
                    self.skipped = max(0, self.skipped - 1)
            def handle_data(self, data):
                if not self.skipped:
                    self.output.append(data)
        parser = TextParser()
        parser.feed(path.read_text(encoding="utf-8", errors="replace"))
        text = normalize_text(" ".join(parser.output))
        cache.write_text(text, encoding="utf-8")
        return [text]
    pages = []
    # PDFium must run sequentially. Only network downloads use threads.
    with pdfium.PdfDocument(path) as document:
        for index in range(len(document)):
            page = document[index]
            textpage = page.get_textpage()
            pages.append(textpage.get_text_range())
            textpage.close()
            page.close()
    cache.write_text("\n\f\n".join(pages), encoding="utf-8")
    return pages


def fetch_report(issuer: dict, year: int, archives: list[str], raw_dir: Path, offline: bool = False) -> tuple[Path | None, str | None]:
    path = raw_dir / f"{issuer['id']}_{year}.pdf"
    html = path.with_suffix(".html")
    if not path.exists() and html.exists():
        path = html
    meta = path.with_suffix(".source.json")
    if path.exists() and meta.exists():
        metadata = json.loads(meta.read_text(encoding="utf-8"))
        if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["sha256"]:
            raise ValueError(f"Filing cache has changed: {path.name}")
        return path, metadata["url"]
    if offline:
        return None, None
    raw_dir.mkdir(parents=True, exist_ok=True)
    archive_keys = [issuer["archive"]]
    if issuer.get("alternateArchive"):
        archive_keys.append(issuer["alternateArchive"])
    for base in archives:
        for key in archive_keys:
            url = f"{base}{key}_{year}.pdf"
            try:
                response = requests.get(url, headers={"User-Agent": "Ripple-public-data/1.0"}, timeout=(10, 25))
                response.raise_for_status()
                if not response.content.startswith(b"%PDF-"):
                    continue
                path.write_bytes(response.content)
                meta.write_text(json.dumps({"url": url, "sha256": hashlib.sha256(response.content).hexdigest()}) + "\n", encoding="utf-8")
                return path, url
            except requests.RequestException:
                continue
    return None, None


def product_category(pages: list[str], issuer: dict) -> tuple[str | None, int | None]:
    # Limit extraction to business descriptions, avoiding a rule that merely
    # finds product words in an unrelated competitor or risk-factor passage.
    for page_number, raw in enumerate(pages, start=1):
        text = normalize_text(raw)
        if not re.search(r"business|overview|products|company profile|current businesses", text, re.I):
            continue
        if re.search(issuer["evidence"], text, re.I):
            return issuer["partType"], page_number
    return None, None


def extract(interim: Path, processed: Path, review: Path, raw_dir: Path, offline: bool = False) -> dict:
    registry = json.loads((ROOT / "data/sources/filings.json").read_text(encoding="utf-8"))
    manifest = json.loads((interim / "supplier_list_manifest.json").read_text(encoding="utf-8"))
    pairs, jobs = [], {}
    for edition in manifest["editions"]:
        year = edition["snapshotYear"]
        with (interim / f"suppliers_{year}.csv").open(encoding="utf-8") as handle:
            names = sorted({r["supplier"] for r in csv.DictReader(handle)})
        for name in names:
            issuer = next((i for i in registry["issuers"] if re.search(i["match"], name, re.I)), None)
            pairs.append((year, name, issuer, edition["sources"]))
            if issuer:
                jobs[(issuer["id"], year)] = issuer
    keys = sorted(jobs)
    def fetch(key):
        return key, fetch_report(jobs[key], key[1], registry["archives"], raw_dir, offline)
    with ThreadPoolExecutor(max_workers=4) as pool:
        downloads = dict(pool.map(fetch, keys))
    results, failures = {}, []
    for key in keys:
        issuer, year = jobs[key], key[1]
        path, url = downloads[key]
        if path is None:
            failures.append({"issuerId": key[0], "reportYear": year, "reason": "Public report download unavailable"})
            continue
        pages = report_pages(path)
        cover = normalize_text(" ".join(pages[:6]))
        if not re.search(re.escape(issuer["identity"]), cover, re.I) or not re.search(rf"\b{year}\b", cover):
            failures.append({"issuerId": key[0], "reportYear": year, "reason": "Document issuer/year could not be verified"})
            continue
        category, page_number = product_category(pages, issuer)
        metadata = json.loads(path.with_suffix(".source.json").read_text(encoding="utf-8"))
        if path.suffix == ".html":
            focus = re.search(r'name=["\']dei:DocumentFiscalYearFocus["\'][^>]*>\s*(20\d{2})\s*<', path.read_text(encoding="utf-8", errors="replace"), re.I)
            if focus:
                metadata["fiscalYearFocus"] = int(focus[1])
            page_number = None
        share, evidence = apple_revenue_share(" ".join(pages), year)
        source_year = metadata.get("fiscalYearFocus") or year
        source = {"title": f"{issuer['identity']} annual report FY{source_year}", "url": url}
        results[key] = {"partType": category, "partTypeSource": source if category else None, "partTypeSourcePage": page_number,
                        "appleRevenueShare": share, "appleRevenueShareSource": source if share is not None else None, "revenueEvidence": evidence,
                        "filingSha256": hashlib.sha256(path.read_bytes()).hexdigest(), "filedOn": metadata.get("filedOn"), "reportDate": metadata.get("reportDate"),
                        "reportFiscalYear": source_year, "sourceFormat": path.suffix.lstrip(".")}
        LOGGER.info("%s FY%s: category=%s, Apple share=%s", issuer["id"], year, category, share)
    profiles, links = [], []
    for year, name, issuer, membership_sources in pairs:
        values = results.get((issuer["id"], year), {}) if issuer else {}
        record = {"snapshotYear": year, "supplier": name, "issuerId": issuer["id"] if issuer else None,
                  "partType": values.get("partType"), "partTypeSource": values.get("partTypeSource"), "partTypeSourcePage": values.get("partTypeSourcePage"),
                  "partTypeScope": registry["partTypeScope"], "applePartAssignmentStatus": "inferred" if values.get("partType") else "unavailable",
                  "appleRevenueShare": values.get("appleRevenueShare"), "appleRevenueShareSource": values.get("appleRevenueShareSource"),
                  "revenueEvidence": values.get("revenueEvidence"), "membershipSources": membership_sources,
                  "filedOn": values.get("filedOn"), "reportDate": values.get("reportDate"), "reportFiscalYear": values.get("reportFiscalYear"), "sourceFormat": values.get("sourceFormat"),
                  "filingSha256": values.get("filingSha256"),
                  "extractionMethod": "rule-based", "filingStatus": "verified" if values else "unavailable"}
        profiles.append(record)
        for field in ["partType", "appleRevenueShare"]:
            source = record[field + "Source"]
            if source is not None:
                links.append({"snapshotYear": year, "supplier": name, "field": field, "value": record[field], "sourceTitle": source["title"], "sourceUrl": source["url"],
                              "sourcePage": record.get("partTypeSourcePage") if field == "partType" else "", "verificationStatus": "pending"})
    # Avoid over-representing legal-name aliases with the same source/value.
    unique_links = list({(r["sourceUrl"], r["field"], r["value"]): r for r in links}.values())
    selected = random.Random(20261014).sample(unique_links, min(30, len(unique_links)))
    processed.mkdir(parents=True, exist_ok=True)
    review.mkdir(parents=True, exist_ok=True)
    output = {"sampleData": False, "method": "rule-based", "profiles": profiles,
              "coverage": {"supplierYearRows": len(profiles), "verifiedReports": len(results), "partTypes": sum(p["partType"] is not None for p in profiles),
                           "appleRevenueShares": sum(p["appleRevenueShare"] is not None for p in profiles), "missingReports": len(failures)},
              "limitations": ["Missing reports or undisclosed values remain null.", "Company categories do not establish Apple-specific parts.", "Reports match the snapshot fiscal year; publication dates must be checked before using attributes for historical predictions."]}
    (processed / "supplier_profiles.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (review / "hand_check.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["snapshotYear", "supplier", "field", "value", "sourceTitle", "sourceUrl", "sourcePage", "verificationStatus"])
        writer.writeheader()
        writer.writerows(selected)
    (review / "filing_download_gaps.json").write_text(json.dumps(failures, indent=2) + "\n", encoding="utf-8")
    if len(selected) < 30:
        raise ValueError(f"Only {len(selected)} extracted links available; outputs saved, but M3 requires a 30-row review sheet")
    LOGGER.info("Coverage: %s; review rows: 30", output["coverage"])
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    extract(ROOT / "data/interim", ROOT / "data/processed", ROOT / "data/review", ROOT / "data/raw/filings", args.offline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
