import json
from pathlib import Path

import pytest

from pipeline.geocode import Gazetteer, centroid, normalize


def rectangle(x0, y0, x1, y1):
    return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


@pytest.fixture
def gazetteer():
    countries = {"features": [{"properties": {"ISO_A2_EH": "US", "NAME": "United States of America", "NE_ID": 1}, "geometry": rectangle(-125, 25, -65, 50)}]}
    provinces = {"features": [
        {"properties": {"iso_a2": "US", "name": "California", "ne_id": 2}, "geometry": rectangle(-124, 32, -114, 42)},
        {"properties": {"iso_a2": "US", "name": "Illinois", "ne_id": 3}, "geometry": rectangle(-92, 36, -87, 43)},
    ]}
    cities = {"features": [
        {"properties": {"iso_a2": "US", "name": "Springfield", "ne_id": 4, "longitude": -120, "latitude": 38}},
        {"properties": {"iso_a2": "US", "name": "Springfield", "ne_id": 5, "longitude": -89, "latitude": 40}},
    ]}
    return Gazetteer(provinces, cities, countries)


def test_centroid_uses_polygon_geometry():
    lon, lat = centroid(rectangle(0, -2, 4, 2))
    assert lon == pytest.approx(2)
    assert lat == pytest.approx(0, abs=1e-6)


def test_province_name_retains_province_precision(gazetteer):
    result, reason = gazetteer.match("California", "United States")
    assert not reason
    assert result["precision"] == "province"
    assert result["lon"] == pytest.approx(-119)


def test_same_named_cities_are_disambiguated_by_province(gazetteer):
    result, _ = gazetteer.match("123 Factory Road, Springfield, Illinois, United States", "United States")
    assert result["precision"] == "city"
    assert result["lon"] == -89
    result, reason = gazetteer.match("Springfield", "United States")
    assert result is None
    assert "unique" in reason


def test_unknown_location_is_not_hidden_by_country_fallback(gazetteer):
    result, reason = gazetteer.match("Invented Place", "United States")
    assert result is None
    assert reason
    result, _ = gazetteer.match("United States", "United States")
    assert result["precision"] == "country"


def test_normalization_handles_source_spelling_conventions():
    assert normalize("Gyeonggi-Do") == normalize("Gyeonggi")
    assert normalize("Zlín Region") == normalize("Zlin")
    assert normalize("Malacca (Melaka)") == normalize("Malacca")


def test_real_outputs_have_coordinates_and_explicit_precision():
    import csv

    paths = list(Path("data/interim").glob("geocoded_*.csv"))
    if not paths:
        pytest.skip("Run M2 ingestion to verify its processed outputs")
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row["matchStatus"] == "matched":
                    assert -180 <= float(row["lon"]) <= 180
                    assert -90 <= float(row["lat"]) <= 90
                    assert row["precision"] in {"city", "province", "country"}
                    assert len(json.loads(row["sources"])) >= 2
                else:
                    assert row["lon"] == row["lat"] == row["precision"] == ""
