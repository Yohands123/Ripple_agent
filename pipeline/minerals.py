"""Parse pinned public mineral disclosures; never infer a specific Apple mine."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_inputs(config, offline=False):
    import requests
    from pipeline.sec_filings import SecClient
    raw = ROOT / "data/raw/minerals"
    raw.mkdir(parents=True, exist_ok=True)
    sec_client = None
    for dataset in config["datasets"].values():
        path = raw / dataset["file"]
        if not path.exists():
            if offline:
                raise FileNotFoundError(path)
            if ".sec.gov/" in dataset["url"]:
                if sec_client is None:
                    sec_client = SecClient(os.environ.get("SEC_USER_AGENT", ""))
                payload = sec_client.get(dataset["url"])
            else:
                response = requests.get(dataset["url"], timeout=(10, 90))
                response.raise_for_status()
                payload = response.content
            path.write_bytes(payload)
        if hashlib.sha256(path.read_bytes()).hexdigest() != dataset["sha256"]:
            raise ValueError("Mineral source snapshot changed; review before repinning: " + dataset["file"])
    return raw


def parse_refiners(pdf_path):
    """Read ruled cells, including wrapped names; never mix adjacent columns."""
    import pdfplumber
    sections = {27: ["cobalt", None], 28: ["gold", "gold"], 29: ["gold", "gold"],
                30: ["gold", "tantalum"], 31: ["tantalum", "tin"], 32: ["tin", "tin"],
                33: ["tungsten", "tungsten"]}
    rows = []
    def cell(page, bounds):
        left, low, right, high = bounds
        # Glyph bounding boxes slightly overhang ruled-cell boundaries.
        # Use character centers so initial letters survive, while a header
        # touching the upper rule cannot contaminate the first data row.
        filtered = page.filter(lambda item: item.get("object_type") == "char" and
                               left <= (item["x0"] + item["x1"]) / 2 < right and
                               low <= (item["top"] + item["bottom"]) / 2 < high)
        return " ".join((filtered.extract_text() or "").split())
    with pdfplumber.open(pdf_path) as document:
        intro = document.pages[27].extract_text()
        if "December 31, 2025" not in intro or "Smelter and refiner list" not in intro:
            raise ValueError("Unexpected Apple annex edition/layout")
        for index, metals in sections.items():
            page = document.pages[index]
            for column, metal in enumerate(metals):
                if metal is None:
                    continue  # Lithium is outside this requested 3TG+cobalt layer.
                left = 48 + 928 * column
                boundaries = sorted({round(line["top"], 4) for line in page.lines
                                     if abs(line["x0"] - left) < 1 and abs(line["x1"] - (left + 448)) < 2})
                for low, high in zip(boundaries, boundaries[1:]):
                    name = cell(page, (left, low, left + 448, high))
                    country = cell(page, (left + 464, low, left + 896, high))
                    if bool(name) != bool(country):
                        raise ValueError(f"Incomplete refinery row on page {index+1}: {name!r} / {country!r}")
                    if name:
                        if "Smelter or refiner name" in name or "Country or region" in country:
                            raise ValueError("Table header contaminated a facility record")
                        rows.append({"metal": metal, "name": name, "country": country, "sourcePage": index + 1})
    keys = {(r["metal"], r["name"], r["country"]) for r in rows}
    if len(keys) != len(rows):
        raise ValueError("Duplicate metal/facility/country records in parsed annex")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    config = read(ROOT / "data/sources/minerals.json")
    raw = fetch_inputs(config, args.offline)
    refiners = parse_refiners(raw / "apple_ungp_2026.pdf")
    counts = dict(Counter(r["metal"] for r in refiners))
    if counts != config["refinerTableCounts"]:
        raise ValueError(f"Unexpected facility count: {counts}")
    path = ROOT / "data/interim/apple_refiners_2025.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(refiners[0]))
        writer.writeheader()
        writer.writerows(refiners)
    print(f"Parsed {len(refiners)} metal/facility/country records: {counts}")
    from pipeline.mineral_catalog import build_nodes, source
    from pipeline.mineral_routes import build_routes, supply_edge
    nodes, gazetteer, _ = build_nodes(config, refiners, args.offline)
    base = read(ROOT / "data/processed/backbone.json")
    edges = build_routes(nodes, base, gazetteer, config)
    for region in [n for n in nodes if n['kind'] == 'mine']:
        for refiner in [n for n in nodes if n['kind'] == 'refinery']:
            metal = refiner['metal']
            if metal not in region['minerals']:
                continue
            restricted = metal in config['originPolicy']['metals'] and region['country'] in config['originPolicy']['countries']
            edges.append(supply_edge(region, refiner, metal, [config['originPolicy']['source']],
                'Global commodity compatibility only: region produces the same metal as this listed refiner. No Apple mine origin, actual feedstock origin or commercial link is established. ' +
                ('Apple publicly excludes DRC/Rwanda-origin 3TG from its supply chain; this is not an allowed current Apple sourcing path.' if restricted else 'Primary versus recycled feedstock is unknown.'),
                appleSourcingStatus='excluded-by-published-origin-policy' if restricted else 'unverified', appleMineOriginAsserted=False))
    output = {'reference': config, 'nodes':nodes, 'edges':edges}
    (ROOT / 'data/processed/minerals.json').write_text(json.dumps(output,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    report = {'refinerRecords':len(refiners), 'byMetal':counts, 'byPrecision':dict(Counter(n['precision'] for n in nodes if n['kind']=='refinery')),
              'miningRegions':sum(n['kind']=='mine' for n in nodes), 'seaRoutes':sum(e['mode']=='sea' for e in edges),
              'landCrossingFailures':0, 'scope':config['scope'], 'sourceChoice':config['sourceChoice']}
    (ROOT / 'data/review/mineral_coverage.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Built mineral reference catalog')


if __name__ == "__main__":
    main()
