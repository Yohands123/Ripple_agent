"""Match Supplier List locations to versioned Natural Earth geography."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import requests
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform

ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)
FORWARD = Transformer.from_crs("EPSG:4326", "EPSG:6933", always_xy=True).transform
INVERSE = Transformer.from_crs("EPSG:6933", "EPSG:4326", always_xy=True).transform


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold()
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"\([^)]*\)", "", value)
    value = re.sub(r"\b(?:province|prefecture|autonomous region|region|county)\b", "", value)
    value = re.sub(r"-do\b", "", value)
    return re.sub(r"[^\w]", "", value)


def aliases(properties: dict, fields: tuple[str, ...]) -> set[str]:
    values = set()
    for field in fields:
        value = properties.get(field)
        if isinstance(value, str) and value != "-99":
            for part in re.split(r"[|;]", value):
                if normalize(part):
                    values.add(normalize(part))
    return values


def centroid(geometry: dict) -> tuple[float, float]:
    """Area-weighted centroid in an equal-area projection, back in WGS84."""
    polygon = shape(geometry)
    if polygon.is_empty:
        raise ValueError("Natural Earth geometry is empty")
    point = transform(INVERSE, transform(FORWARD, polygon).centroid)
    if not (-180 <= point.x <= 180 and -90 <= point.y <= 90):
        raise ValueError("Centroid is outside WGS84 bounds")
    return round(point.x, 6), round(point.y, 6)


class Gazetteer:
    def __init__(self, admin1: dict, cities: dict, countries: dict):
        self.provinces = defaultdict(list)
        self.primary_provinces = defaultdict(list)
        self.cities = defaultdict(list)
        self.countries = {}
        self.iso_by_country = {}
        for feature in countries["features"]:
            p = feature["properties"]
            iso = next((p.get(field) for field in ("ISO_A2_EH", "ISO_A2") if p.get(field) and p.get(field) != "-99"), None)
            if not iso or iso == "-99":
                continue
            record = {"name": p["NAME"], "id": str(p["NE_ID"]), "geometry": feature["geometry"], "iso": iso}
            self.countries[iso] = record
            for name in aliases(p, ("NAME", "NAME_EN", "NAME_LONG", "ADMIN", "GEOUNIT", "NAME_CIAWF")):
                self.iso_by_country[name] = iso
        # The Supplier Lists use the short name; Natural Earth also records
        # the United States' full official name.
        self.iso_by_country[normalize("United States")] = "US"
        for feature in admin1["features"]:
            p = feature["properties"]
            record = {"name": p["name"], "id": str(p["ne_id"]), "geometry": feature["geometry"], "iso": p["iso_a2"]}
            for name in aliases(p, ("name", "name_en")):
                self.primary_provinces[(p["iso_a2"], name)].append(record)
            for name in aliases(p, ("name", "name_en", "name_alt", "woe_name", "gn_name", "gns_name")):
                self.provinces[(p["iso_a2"], name)].append(record)
        for feature in cities["features"]:
            p = feature["properties"]
            record = {"name": p["name"], "id": str(p["ne_id"]), "lon": p["longitude"], "lat": p["latitude"],
                      "iso": p["iso_a2"], "province": normalize(p.get("adm1name") or "")}
            for name in aliases(p, ("name", "nameascii", "namealt", "namepar", "ls_name")):
                self.cities[(p["iso_a2"], name)].append(record)
        self.centroid_cache = {}

    @staticmethod
    def unique(records: list[dict]) -> list[dict]:
        return list({record["id"]: record for record in records}.values())

    def region_point(self, record: dict, precision: str) -> dict:
        if record["id"] not in self.centroid_cache:
            self.centroid_cache[record["id"]] = centroid(record["geometry"])
        lon, lat = self.centroid_cache[record["id"]]
        return {"lon": lon, "lat": lat, "precision": precision, "geoName": record["name"], "geoId": record["id"], "matchMethod": "equal-area polygon centroid"}

    def match(self, location: str, country: str) -> tuple[dict | None, str]:
        iso = self.iso_by_country.get(normalize(country))
        if not iso:
            return None, "Country is absent from Natural Earth"
        if normalize(location) == normalize(country):
            return self.region_point(self.countries[iso], "country"), ""
        tokens = [normalize(token) for token in re.split(r"[,;]", location) if normalize(token)]
        province_matches = [(i, self.unique(self.primary_provinces.get((iso, token)) or self.provinces.get((iso, token), []))) for i, token in enumerate(tokens)]
        province_matches = [(i, records) for i, records in province_matches if records]
        # A standalone administrative division stays at province precision,
        # even when a city in it has the same name (for example Fukushima).
        if len(tokens) == 1 and province_matches:
            records = province_matches[0][1]
            if len(records) == 1:
                return self.region_point(records[0], "province"), ""
            return None, "Administrative name has multiple matches"
        provinces = self.unique([r for _, records in province_matches for r in records])
        for token in reversed(tokens):
            city_matches = self.unique(self.cities.get((iso, token), []))
            if provinces:
                city_matches = [city for city in city_matches if any(shape(province["geometry"]).covers(Point(city["lon"], city["lat"])) for province in provinces)]
            if len(city_matches) == 1:
                city = city_matches[0]
                return {"lon": city["lon"], "lat": city["lat"], "precision": "city", "geoName": city["name"], "geoId": city["id"], "matchMethod": "Natural Earth populated-place point"}, ""
        for _, records in reversed(province_matches):
            if len(records) == 1:
                return self.region_point(records[0], "province"), ""
        if normalize(location) == normalize(country) or tokens == [normalize(country)]:
            return self.region_point(self.countries[iso], "country"), ""
        return None, "No unique city or province match; manual review required"


def load_datasets(config: dict, raw_dir: Path, offline: bool = False) -> dict:
    result = {}
    for dataset in config["datasets"]:
        path = raw_dir / dataset["file"]
        if not path.exists():
            if offline:
                raise FileNotFoundError(f"Missing cached geography: {path.name}")
            response = requests.get(config["baseUrl"] + dataset["file"], timeout=(10, 60))
            response.raise_for_status()
            content = response.content
            if hashlib.sha256(content).hexdigest() != dataset["sha256"]:
                raise ValueError(f"Unexpected Natural Earth hash: {path.name}")
            raw_dir.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != dataset["sha256"]:
            raise ValueError(f"Natural Earth cache has changed: {path.name}")
        result[dataset["id"]] = json.loads(content)
    return result


def geocode(interim: Path, review: Path, raw_dir: Path, offline: bool = False) -> dict:
    config = json.loads((ROOT / "data/sources/natural_earth.json").read_text(encoding="utf-8"))
    gazetteer = Gazetteer(**load_datasets(config, raw_dir, offline))
    manifest = json.loads((interim / "supplier_list_manifest.json").read_text(encoding="utf-8"))
    with (interim / "supplier_locations_provenance.csv").open(encoding="utf-8") as handle:
        roles = {(int(r["snapshotYear"]), int(r["rowNumber"])): r["locationRole"] for r in csv.DictReader(handle)}
    geosources = {d["id"]: {"title": d["title"], "url": config["baseUrl"] + d["file"]} for d in config["datasets"]}
    unmatched, summary = [], {"sampleData": False, "naturalEarthVersion": config["version"], "years": []}
    fields = ["snapshotYear", "rowNumber", "supplier", "location", "country", "locationRole", "lon", "lat", "precision", "geoName", "geoId", "matchMethod", "matchStatus", "sources"]
    for edition in manifest["editions"]:
        year = edition["snapshotYear"]
        path = interim / f"suppliers_{year}.csv"
        content = path.read_bytes()
        if edition.get("csvHashNormalization") == "LF":
            content = content.replace(b"\r\n", b"\n")
        if hashlib.sha256(content).hexdigest() != edition["csvSha256"]:
            raise ValueError(f"Supplier CSV no longer matches its source manifest: {path.name}")
        with path.open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        output, counts = [], defaultdict(int)
        for number, row in enumerate(rows, start=1):
            match, reason = (None, "Company roster does not disclose manufacturing locations or countries") if not row["location"] and not row["country"] else gazetteer.match(row["location"], row["country"])
            result = {"snapshotYear": year, "rowNumber": number, **row, "locationRole": roles[(year, number)], "matchStatus": "matched" if match else "unmatched"}
            sources = list(edition["sources"])
            if match:
                result.update(match)
                counts[match["precision"]] += 1
                dataset = {"city": "cities", "province": "admin1", "country": "countries"}[match["precision"]]
                sources.append(geosources[dataset])
            else:
                unmatched.append({"snapshotYear": year, "rowNumber": number, **row, "reason": reason})
                counts["unmatched"] += 1
            result["sources"] = json.dumps(sources, ensure_ascii=False)
            output.append(result)
        with (interim / f"geocoded_{year}.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(output)
        summary["years"].append({"snapshotYear": year, "rows": len(rows), "counts": dict(counts)})
        LOGGER.info("FY%s: %s", year, dict(counts))
    review.mkdir(parents=True, exist_ok=True)
    with (review / "unmatched.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["snapshotYear", "rowNumber", "supplier", "location", "country", "reason"])
        writer.writeheader()
        writer.writerows(unmatched)
    (interim / "geocode_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interim", type=Path, default=ROOT / "data/interim")
    parser.add_argument("--review", type=Path, default=ROOT / "data/review")
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data/raw/natural_earth")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    geocode(args.interim, args.review, args.raw_dir, args.offline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
