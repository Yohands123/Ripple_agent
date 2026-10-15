"""Build dated mineral reference nodes from pinned Apple and USGS sources."""
from collections import defaultdict
import hashlib
import re

from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from pipeline.backbone import citations, dms
from pipeline.geocode import Gazetteer, centroid, load_datasets, normalize
from pipeline.minerals import ROOT, read
from pipeline.sea_geometry import geometry
from pipeline.sea_routes import WaterRouter

ALIASES = {"China mainland": "China", "Congo (Kinshasa)": "Democratic Republic of the Congo", "Burma": "Myanmar",
           "Korea, North": "North Korea", "Korea, Republic of": "South Korea"}
PORTS = {"dar-es-salaam": 47010, "durban": 46850, "lobito": 46590, "walvis-bay": 46640, "santos": 12970}


def identifier(*parts):
    return "mineral-" + hashlib.sha256("\0".join(parts).encode()).hexdigest()[:16]


def source(item):
    return {"title": item["title"], "url": item["url"]}


def parse_producer_countries(path):
    import pdfplumber
    with pdfplumber.open(path) as document:
        text = "\n".join(page.extract_text() for page in document.pages)
    match = re.search(r"World Mine (?:and Refinery )?Production and Reserves:", text)
    if not match:
        raise ValueError("USGS mine-production table not found: " + str(path))
    table = text[match.end():].split("World Resources:")[0]
    rows = []
    for line in table.splitlines():
        match = re.match(r"^([A-Za-z][A-Za-z ,()\-]+?)\s+((?:e?\d[\d,]*|\u2014|W)\s+.*)$", line)
        if not match:
            continue
        country, values = match.groups()
        if country in {"Other countries", "World total (rounded)"}:
            continue
        fields = values.split()
        if len(fields) >= 2 and fields[1] not in {"\u2014", "W", "0"}:
            rows.append(ALIASES.get(country, country))
    if not rows:
        raise ValueError("Empty USGS producer-country table: " + str(path))
    return rows


def build_nodes(config, refiner_rows, offline=False):
    geo_config = read(ROOT / "data/sources/natural_earth.json")
    geo = load_datasets(geo_config, ROOT / "data/raw/natural_earth", offline)
    gazetteer = Gazetteer(geo["admin1"], geo["cities"], geo["countries"])
    geography = {item["id"]: {"title": item["title"], "url": geo_config["baseUrl"] + item["file"]} for item in geo_config["datasets"]}
    nodes = []
    def position(place, country):
        country = ALIASES.get(country, country)
        point, reason = gazetteer.match(place, country)
        if point is None:
            raise ValueError(f"Unmatched mineral geography {place}, {country}: {reason}")
        return point, country

    def node(key, name, kind, point, country, evidence, minerals, **extra):
        tier = 1 if kind == "mine" else 2 if kind == "refinery" else None
        result = {"id": key, "name": name, "kind": kind, "layer": "backbone", "contextLayer": "minerals",
                  "lon": point["lon"], "lat": point["lat"], "precision": point["precision"], "country": country,
                  "region": point["geoName"], "tier": tier, "tierStatus": "inferred" if tier else "unknown",
                  "tierBasis": "mineral extraction or processing role" if tier else "part type unavailable",
                  "partType": "mineral extraction" if kind == "mine" else "mineral refining" if kind == "refinery" else None,
                  "ticker": None, "appleRevenueShare": None, "minerals": minerals, "confidence": "low",
                  "confidenceKind": "Qualitative geographic/stage inference, not a calibrated probability",
                  "referenceAsOf": config["referenceAsOf"], "historicalPresenceAsserted": False,
                  "sources": citations(evidence, [geography[{"city": "cities", "province": "admin1", "country": "countries"}[point["precision"]]]]),
                  "positionStatus": "inferred", "positionBasis": point["matchMethod"] + "; approximate reference, not a mine or facility coordinate",
                  "scope": config["scope"], **extra}
        nodes.append(result)
        return result

    annex = source(config["datasets"]["apple_ungp_2026.pdf"])
    cmr = source(config["datasets"]["apple_cmr_2024.html"])
    for row in refiner_rows:
        country = ALIASES.get(row["country"], row["country"])
        point, country = position(country, country)
        city, city_source = None, None
        override = config.get("cityEvidence", {}).get(row["name"])
        if override:
            city, city_source = override["city"], override["source"]
            city_point, _ = gazetteer.match(city + ", " + country, country)
            if city_point:
                point = city_point
        evidence = [annex, cmr] + ([city_source] if city_source else [])
        node(identifier("refinery", row["metal"], row["name"], row["country"]), row["name"] + " (" + row["metal"] + ")",
             "refinery", point, country, evidence, [row["metal"]], metal=row["metal"], city=city,
             reportEntryName=row["name"], reportCountry=row["country"], reportPage=row["sourcePage"],
             listedByApple=True, appleMineOriginAsserted=False, status="known",
             cityPositionNote="Operator-published city; coordinates remain at the displayed precision" if city else "Apple lists the country only; no city or precise facility coordinate is invented")

    countries = defaultdict(dict)
    for metal in ["cobalt", "copper", "gold", "tantalum", "tin", "tungsten"]:
        dataset = config["datasets"][f"mcs2026-{metal}.pdf"]
        for country in parse_producer_countries(ROOT / "data/raw/minerals" / dataset["file"]):
            countries[country][metal] = source(dataset)
    for country, minerals in sorted(countries.items()):
        if country in {"Democratic Republic of the Congo", "Zambia", "Rwanda"}:
            continue  # Named regions below avoid duplicating these countries.
        point, country = position(country, country)
        node(identifier("producing-region", country), country + " producing region", "mine", point, country,
             list(minerals.values()), sorted(minerals), appleMineOriginAsserted=False, status="known",
             regionBasis="Country-level producer region named in USGS 2026 mine-production tables; not a specific mine or an Apple source")
    copperbelt_source = config["sources"]["copperbelt"]
    great_lakes = config["sources"]["greatLakes"]
    for key, name, place, country, minerals, evidence in [
        ("copperbelt-drc", "Copperbelt - Katanga, DRC", "Katanga", "Democratic Republic of the Congo", ["cobalt", "copper"], [copperbelt_source]),
        ("copperbelt-zambia", "Copperbelt - Zambia", "Copperbelt", "Zambia", ["cobalt", "copper"], [copperbelt_source]),
        ("rwanda", "Rwanda 3T mining region", "Rwanda", "Rwanda", ["tin", "tantalum", "tungsten"], [great_lakes]),
    ]:
        point, country = position(place, country)
        evidence += [source(config["datasets"][f"mcs2026-{m}.pdf"]) for m in minerals]
        node("mineral-mine-" + key, name, "mine", point, country, evidence, minerals,
             appleMineOriginAsserted=False, status="known", regionBasis="Broad mineral-producing region; no individual mine or Apple mine purchase is identified")
    eastern = [f for f in geo["admin1"]["features"] if f["properties"].get("iso_a2") == "CD" and f["properties"].get("name") in {"Nord-Kivu", "Sud-Kivu", "Maniema"}]
    if len(eastern) != 3:
        raise ValueError("Eastern DRC region requires the three pinned province geometries")
    lon, lat = centroid(mapping(unary_union([shape(f["geometry"]) for f in eastern])))
    node("mineral-mine-eastern-drc", "Eastern DRC 3T mining region", "mine",
         {"lon": lon, "lat": lat, "precision": "province", "geoName": "Eastern DRC", "matchMethod": "Equal-area centroid of Nord-Kivu, Sud-Kivu and Maniema reference polygons"},
         "Democratic Republic of the Congo", [great_lakes], ["tin", "tantalum", "tungsten"], appleMineOriginAsserted=False, status="known",
         regionBasis="Inferred display extent for a broad historical mining region; not a mineral-deposit boundary")

    port_rows = {r["portNumber"]: r for r in read(ROOT / "data/raw/backbone/ports.json")["ports"]}
    land, _ = geometry()
    for key, number in PORTS.items():
        row = port_rows[number]
        original = [dms(row["longitude"]), dms(row["latitude"])]
        x, y = original
        router = WaterRouter(step=.05, bounds=(round(x-3, 1), round(y-3, 1), round(x+3, 1), round(y+3, 1)), land=land.buffer(.005))
        x, y = router.point(router.snap(tuple(original)))
        point = {"lon": x, "lat": y, "precision": "city", "geoName": row["portName"], "matchMethod": "Inferred coastal approach near the published NGA port reference"}
        node("backbone-mineral-port-" + key, row["portName"] + " port", "port", point, row["countryName"],
             [{"title": f"NGA World Port Index: {row['portName']} ({number})", "url": f"https://msi.nga.mil/api/publications/world-port-index?indexNumber={number}&output=json"}], [],
             worldPortIndex=number, publishedPosition={"lon": original[0], "lat": original[1]}, status="known")
    return nodes, gazetteer, geography
