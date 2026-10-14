"""Download Apple-authored PDFs and extract fiscal-year supplier snapshots.

Run from the project root with ``.venv/bin/python -m pipeline.supplier_lists``.
Raw PDFs stay under data/raw. CSVs contain one supplier/location/country row;
a sidecar preserves page numbers and the FY2020 headquarters-only section.
No historical year is filled from a different edition.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
import unicodedata
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import pdfplumber
import requests

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
COUNTRIES = {
    "Australia", "Austria", "Belgium", "Brazil", "Cambodia", "Canada", "China", "China mainland", "Costa Rica",
    "Czech Republic", "Czechia", "Denmark", "Finland", "France", "Germany",
    "Hong Kong", "Hungary", "India", "Indonesia", "Ireland", "Israel", "Italy",
    "Japan", "Korea", "Luxembourg", "Malaysia", "Malta", "Mauritius", "Mexico", "Morocco", "Netherlands",
    "New Zealand", "Norway", "Philippines", "Poland", "Portugal", "Romania",
    "Puerto Rico", "Russia", "Singapore", "Slovakia", "South Korea", "Spain", "Sweden",
    "Switzerland", "Taiwan", "Thailand", "Turkey", "United Kingdom",
    "United States", "Vietnam", "Viet Nam",
}
COUNTRY_ALIASES = {"China mainland": "China", "Korea": "South Korea", "Viet Nam": "Vietnam", "Czechia": "Czech Republic"}


class ParseError(ValueError):
    """A document or row cannot be represented without guessing."""


def clean(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def fiscal_year(text: str) -> int:
    matches = set(re.findall(r"fiscal\s+year\s+(20\d{2})", text, re.I))
    if len(matches) != 1:
        raise ParseError("Cover must identify exactly one fiscal year")
    return int(matches.pop())


def normalize_country(value: str) -> str:
    value = clean(value)
    if value not in COUNTRIES:
        raise ParseError(f"Unrecognized source country: {value!r}")
    return COUNTRY_ALIASES.get(value, value)


def address_row(supplier: str, address: str) -> dict[str, str]:
    address = clean(address)
    for country in sorted(COUNTRIES, key=len, reverse=True):
        if address == country or address.endswith(", " + country):
            return {"supplier": clean(supplier), "location": address, "country": normalize_country(country)}
    raise ParseError(f"Address has no recognized country suffix: {address!r}")


def region_rows(supplier: str, location: str, country: str) -> list[dict[str, str]]:
    """Expand explicitly delimited regions, preserving parenthesized names."""
    supplier = clean(re.sub(r"\s*\(continued\)\s*", "", supplier, flags=re.I))
    if not supplier:
        raise ParseError("Location is missing its supplier")
    normalized_country = normalize_country(country)
    location = clean(location) or clean(country)
    # Region lists use commas/semicolons; street addresses use address_row.
    locations = re.split(r"[;,](?![^()]*\))", location)
    return [{"supplier": supplier, "location": clean(part), "country": normalized_country}
            for part in locations if clean(part)]


def word_text(words: list[dict]) -> str:
    return clean(" ".join(w["text"] for w in sorted(words, key=lambda w: (round(w["top"] / 2), w["x0"]))))


def lines(words: list[dict], tolerance: float = 2) -> list[list[dict]]:
    result: list[list[dict]] = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if not result or abs(word["top"] - result[-1][0]["top"]) > tolerance:
            result.append([word])
        else:
            result[-1].append(word)
    return [sorted(line, key=lambda w: w["x0"]) for line in result]


def headers(words: list[dict], edges: list[dict] | None = None) -> list[dict]:
    result = []
    for line in lines(words):
        texts = [w["text"].casefold() for w in line]
        if texts[:2] == ["global", "name"]:
            # The 2019 publication's headquarters table changes its column
            # widths and labels the left column "Global Name".
            nearby = [e for e in (edges or []) if 0 < e["top"] - line[0]["bottom"] < 20]
            starts = [e["x0"] for e in nearby if e["x0"] > line[0]["x0"] + 20]
            if not starts:
                raise ParseError("Headquarters table has no column boundary")
            result.append({"top": line[0]["top"], "bottom": line[0]["bottom"],
                           "nameX": line[0]["x0"], "locationX": min(starts),
                           "address": True, "role": "headquarters"})
            continue
        for i in range(len(line) - 1):
            if texts[i:i+2] != ["supplier", "name"]:
                continue
            following = line[i+2:]
            location = next((w for w in following if w["text"].casefold() in {"primary", "manufacturing", "location"}), None)
            if location:
                result.append({"top": line[i]["top"], "bottom": max(w["bottom"] for w in line),
                               "nameX": line[i]["x0"], "locationX": location["x0"],
                               "address": location["text"].casefold() == "manufacturing",
                               "role": "headquarters" if location["text"].casefold() == "location" else "manufacturing"})
    return result


def parse_page(page, previous: str | None = None) -> tuple[list[dict], str | None]:
    words = page.dedupe_chars().extract_words(x_tolerance=2, y_tolerance=2)
    sections = headers(words, page.horizontal_edges)
    result = []
    for index, header in enumerate(sections):
        name_x, location_x = header["nameX"], header["locationX"]
        end = sections[index+1]["top"] if index+1 < len(sections) else page.height - 30
        notes = [line[0]["top"] for line in lines(words)
                 if header["bottom"] < line[0]["top"] < end
                 and word_text(line).startswith(("Because the suppliers below", "The suppliers below"))]
        end = min(notes, default=end)
        edges = [e for e in page.horizontal_edges if header["bottom"] - 1 <= e["top"] < end]
        # Rules crossing the supplier column delimit whole supplier cells. In
        # FY2020 supplier names are vertically centered over many country rows.
        cuts = sorted({round(e["top"], 1) for e in edges
                       if e["x0"] <= name_x + 2 and e["x1"] >= location_x - 10})
        if len(cuts) < 2:
            raise ParseError("Supplier table has no usable row boundaries")
        body = [w for w in words if cuts[0] <= w["top"] < end and w["x0"] >= name_x - 2]
        # Country columns have a repeated left alignment even in unruled PDFs.
        country_starts = []
        if not header["address"]:
            for line in lines(body):
                for j, word in enumerate(line):
                    if word["x0"] > location_x + 50 and word_text(line[j:]) in COUNTRIES:
                        country_starts.append(round(word["x0"] / 2) * 2)
            if not country_starts:
                raise ParseError("Cannot identify table country column")
            country_x = min(country_starts) - 4
            trailing = [line for line in lines([w for w in body if w["x0"] >= country_x and w["top"] >= cuts[-1]])
                        if word_text(line) in COUNTRIES]
            if trailing:
                # FY2021 omits the bottom border on many pages. The final
                # supplier still belongs to the table, including continuations.
                cuts.append(min(end, max(w["bottom"] for line in trailing for w in line) + 12))
        body = [w for w in body if w["top"] < cuts[-1]]
        for top, bottom in zip(cuts, cuts[1:]):
            group = [w for w in body if top <= w["top"] < bottom]
            name = word_text([w for w in group if w["x0"] < location_x - 2])
            name = clean(re.sub(r"\s*\(continued\)\s*", "", name, flags=re.I))
            if name:
                previous = name
            if not previous:
                raise ParseError("Continuation appears before a supplier name")
            if header["address"]:
                location = word_text([w for w in group if w["x0"] >= location_x - 2])
                row = address_row(previous, location)
                result.append({**row, "locationRole": header["role"]})
                continue
            country_lines = lines([w for w in group if w["x0"] >= country_x])
            if not country_lines:
                raise ParseError(f"Missing country for {previous}")
            for j, country_line in enumerate(country_lines):
                country = word_text(country_line)
                y = country_line[0]["top"]
                lower = top if j == 0 else (country_lines[j-1][0]["top"] + y) / 2
                upper = bottom if j == len(country_lines)-1 else (country_lines[j+1][0]["top"] + y) / 2
                # Prefer printed country-row rules for wrapped locations.
                before = [e["top"] for e in edges if e["x1"] >= country_x and e["x0"] <= location_x and lower <= e["top"] <= y]
                after = [e["top"] for e in edges if e["x1"] >= country_x and e["x0"] <= location_x and y < e["top"] <= upper]
                lower = max(before, default=lower)
                upper = min(after, default=upper)
                location = word_text([w for w in group if location_x - 2 <= w["x0"] < country_x and lower <= w["top"] < upper])
                for row in region_rows(previous, location, country):
                    result.append({**row, "locationRole": header["role"]})
    return result, previous


def parse_pdf(path: Path, expected_year: int) -> list[dict]:
    rows, previous = [], None
    with pdfplumber.open(path) as document:
        year = fiscal_year(document.pages[0].extract_text() or "")
        if year != expected_year:
            raise ParseError(f"Expected FY{expected_year}, document covers FY{year}")
        for number, page in enumerate(document.pages[1:], start=2):
            try:
                page_rows, previous = parse_page(page, previous)
            except ParseError as exc:
                raise ParseError(f"{path.name}, page {number}: {exc}") from exc
            rows.extend({**row, "sourcePage": number} for row in page_rows)
    if not rows:
        raise ParseError("No supplier locations extracted")
    # Exact repeated source rows are redundant, but distinct addresses remain.
    seen = set()
    unique = []
    for row in rows:
        key = tuple(row[field] for field in ("supplier", "location", "country", "locationRole"))
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def fetch_pdf(url: str, session: requests.Session) -> bytes:
    response = session.get(url, timeout=(10, 30))
    response.raise_for_status()
    if response.content.startswith(b"%PDF-"):
        return response.content
    # Mirrors can expose an Apple-authored PDF as a public attachment. Resolve
    # its current URL without persisting expiring query credentials.
    for href in re.findall(r"href=[\"']([^\"']+)[\"']", response.text):
        href = urljoin(response.url, unescape(href))
        if ".pdf" in href.lower() and "supplier" in href.lower() and urlsplit(href).scheme == "https":
            attachment = session.get(href, timeout=(10, 30))
            attachment.raise_for_status()
            if attachment.content.startswith(b"%PDF-"):
                return attachment.content
    raise ParseError("Source returned HTML instead of a supplier-list PDF")


def download(edition: dict, raw_dir: Path, session: requests.Session) -> Path:
    path = raw_dir / f"suppliers_{edition['snapshotYear']}.pdf"
    if path.exists():
        if not path.read_bytes().startswith(b"%PDF-"):
            raise ParseError(f"Invalid cached PDF: {path.name}")
        return path
    errors = []
    for url in edition["downloads"]:
        try:
            content = fetch_pdf(url, session)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(content)
            # Check the cover before caching a mutable URL under a year.
            with pdfplumber.open(temporary) as document:
                year = fiscal_year(document.pages[0].extract_text() or "")
            if year != edition["snapshotYear"]:
                temporary.unlink()
                raise ParseError(f"Downloaded FY{year}, expected FY{edition['snapshotYear']}")
            temporary.replace(path)
            return path
        except (requests.RequestException, ValueError, OSError) as exc:
            # Never log attachment query strings (including signed URLs).
            errors.append(f"{urlsplit(url).netloc}: {type(exc).__name__}")
    raise ParseError("All downloads failed: " + "; ".join(errors))


def ingest(source_file: Path, raw_dir: Path, output_dir: Path, offline: bool = False) -> dict:
    config = json.loads(source_file.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"sampleData": False, "checkedOn": config["checkedOn"], "yearPolicy": config["yearPolicy"], "editions": [], "gaps": config["gaps"]}
    provenance = []
    with requests.Session() as session:
        session.headers["User-Agent"] = "Ripple-public-data/1.0"
        for edition in config["editions"]:
            year = edition["snapshotYear"]
            try:
                path = raw_dir / f"suppliers_{year}.pdf" if offline else download(edition, raw_dir, session)
                if not path.exists():
                    raise ParseError("Verified PDF is unavailable in the raw cache")
                rows = parse_pdf(path, year)
            except (ParseError, OSError) as exc:
                LOGGER.error("FY%s: %s", year, exc)
                manifest["gaps"].append({"snapshotYear": year, "reason": str(exc)})
                continue
            output = output_dir / f"suppliers_{year}.csv"
            with output.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["supplier", "location", "country"], extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
            record = {"snapshotYear": year, "publicationYear": edition["publicationYear"], "sources": [{"title": edition["title"], "url": edition["url"]}],
                      "pdfSha256": hashlib.sha256(path.read_bytes()).hexdigest(), "csvSha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                      "rows": len(rows), "suppliers": len({row["supplier"] for row in rows}),
                      "headquartersRows": sum(row["locationRole"] == "headquarters" for row in rows)}
            manifest["editions"].append(record)
            for row_number, row in enumerate(rows, start=1):
                provenance.append({"snapshotYear": year, "rowNumber": row_number, "sourcePage": row["sourcePage"], "locationRole": row["locationRole"]})
            LOGGER.info("FY%s: %s rows, %s suppliers (%s headquarters rows)", year, record["rows"], record["suppliers"], record["headquartersRows"])
    (output_dir / "supplier_list_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with (output_dir / "supplier_locations_provenance.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["snapshotYear", "rowNumber", "sourcePage", "locationRole"])
        writer.writeheader()
        writer.writerows(provenance)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=ROOT / "data/sources/supplier_lists.json")
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data/raw/supplier_lists")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/interim")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    manifest = ingest(args.sources, args.raw_dir, args.output_dir, args.offline)
    LOGGER.info("Verified editions: %s; gaps: %s", [e["snapshotYear"] for e in manifest["editions"]], [g["snapshotYear"] for g in manifest["gaps"]])
    # Gaps are explicit, but parsing/download failures of requested editions
    # must not silently look like a successful ingestion.
    requested = json.loads(args.sources.read_text(encoding="utf-8"))["editions"]
    return int(len(manifest["editions"]) != len(requested))


if __name__ == "__main__":
    raise SystemExit(main())
