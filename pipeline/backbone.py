"""Build a sourced reference layer and overlay inferred routes during export.

Only build_catalog needs raw geography. attach_backbone reads the small,
committed catalog; it never updates historical cohorts, model inputs, labels,
predictions, or illustrative optimizer outputs.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import re
from pathlib import Path

from pipeline.sea_routes import distance_km
from pipeline.tiers import inferred_tier

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "backbone-"
ROUTE_SCOPE = "Inferred schematic connection from public geography and transport corridors; no Apple shipment, volume, schedule, capacity or allocation is disclosed."


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def citations(*groups):
    return list({(s["title"], s["url"]): {"title": s["title"], "url": s["url"]} for group in groups for s in group}.values())


def dms(value):
    pieces = re.findall(r"\d+(?:\.\d+)?", value)
    if len(pieces) != 3 or value[-1] not in "NSEW":
        raise ValueError(f"Invalid WPI coordinate: {value!r}")
    degrees, minutes, seconds = map(float, pieces)
    return (degrees + minutes / 60 + seconds / 3600) * (-1 if value[-1] in "SW" else 1)


def load_raw(config, root, offline):
    import requests
    result = {}
    for key, dataset in config["datasets"].items():
        path = root / "data/raw/backbone" / dataset["file"]
        if not path.exists():
            if offline:
                raise FileNotFoundError(path)
            response = requests.get(dataset["url"], timeout=(10, 90))
            response.raise_for_status()
            payload = response.content
            if hashlib.sha256(payload).hexdigest() != dataset["sha256"]:
                raise ValueError(f"{key}: upstream snapshot changed; review and pin it before use")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        if hashlib.sha256(path.read_bytes()).hexdigest() != dataset["sha256"]:
            raise ValueError(f"{key}: cached dataset hash changed")
        result[key] = path
    return result


def build_catalog(root=ROOT, offline=False):
    from pipeline.geocode import load_datasets, centroid, normalize
    from pipeline.sea_routes import WaterRouter

    config = read(root / "data/sources/backbone.json")
    if config["approval"].get("approved") is not True:
        raise ValueError("Backbone export requires the approved format extension")
    raw = load_raw(config, root, offline)
    geo_config = read(root / "data/sources/natural_earth.json")
    geo = load_datasets(geo_config, root / "data/raw/natural_earth", offline)
    geo_sources = {r["id"]: {"title": r["title"], "url": geo_config["baseUrl"] + r["file"]} for r in geo_config["datasets"]}
    sources = config["sources"]
    nodes, edges = [], []

    def add_node(key, name, kind, point, region, evidence, precision="exact", **extra):
        part = "assembly" if kind == "assembly" else None
        node = {"id": PREFIX + key, "name": name, "kind": kind, "layer": "backbone",
                "referenceAsOf": config["checkedOn"], "historicalPresenceAsserted": False,
                "lon": point[0], "lat": point[1], "precision": precision, "region": region,
                "partType": part, **inferred_tier(part), "ticker": None, "appleRevenueShare": None,
                "sources": citations(evidence), "status": "inferred" if kind in {"assembly", "sales_region"} else "known",
                "scope": config["scope"], **extra}
        nodes.append(node)
        return node

    def geo_point(name, iso, province=False):
        collection = "admin1" if province else "cities"
        matches = [f for f in geo[collection]["features"] if f["properties"].get("iso_a2") == iso
                   and normalize(f["properties"].get("name") or "") == normalize(name)]
        if len(matches) != 1:
            raise ValueError(f"No unique reference point: {name}, {iso}")
        f = matches[0]
        if province:
            point = list(centroid(f["geometry"]))
        else:
            point = [f["properties"]["longitude"], f["properties"]["latitude"]]
        return point, geo_sources[collection]

    airport_rows = list(csv.DictReader(raw["airports"].open(encoding="utf-8")))
    for code in config["airports"]:
        matches = [r for r in airport_rows if r["iata_code"] == code and r["type"] != "closed"]
        if len(matches) != 1:
            raise ValueError(f"Ambiguous IATA code: {code}")
        row = matches[0]
        evidence = [config["datasets"]["airports"], sources["cargo"]]
        if code.lower() in sources:
            evidence.append(sources[code.lower()])
        add_node("airport-" + code.lower(), row["name"] + f" ({code})", "airport",
                 [float(row["longitude_deg"]), float(row["latitude_deg"])], row["iso_country"], evidence,
                 iata=code, positionBasis="Published airport reference point, not a cargo-terminal coordinate",
                 gatewaySelectionBasis="Curated regional gateway; no supplier usage or flight schedule is asserted")

    port_rows = {r["portNumber"]: r for r in read(raw["ports"])["ports"]}
    for port in config["ports"]:
        row = port_rows[port["number"]]
        evidence = [{"title": f"NGA World Port Index: {row['portName']} ({row['portNumber']})",
                     "url": f"https://msi.nga.mil/api/publications/world-port-index?indexNumber={row['portNumber']}&output=json"}]
        if port["key"] in sources:
            evidence.append(sources[port["key"]])
        add_node("port-" + port["key"], row["portName"] + " port", "port",
                 [dms(row["longitude"]), dms(row["latitude"])], row["countryName"], evidence,
                 worldPortIndex=row["portNumber"], positionBasis="Published WPI port reference, rounded to an arcminute in the source")
    add_node("port-chennai", "Chennai port", "port", [80 + 18 / 60, 13 + 6 / 60], "India", [sources["chennai"]],
             positionBasis="Chennai Port Authority published position, rounded to an arcminute")
    point, evidence = geo_point("Colón", "PA")
    add_node("port-cristobal", "Cristobal / Colón Atlantic canal gateway", "port", point, "Panama",
             [evidence, sources["panama"], {"title": "Panama Maritime Authority: Cristobal container terminal", "url": "https://www.amp.gob.pa/servicios/puertos-e-industrias-maritimas-auxiliares/infraestructura/terminal-de-contenedores/"}],
             precision="city", positionBasis="Natural Earth Colón city point, not an exact terminal coordinate")

    for choke in config["chokepoints"]:
        kind = "canal" if choke["key"] in {"suez", "panama"} else "chokepoint"
        record = {"title": f"Marine Regions: {choke['name']}, MRGID {choke['mrgid']}",
                  "url": f"https://www.marineregions.org/gazetteer.php?id={choke['mrgid']}&p=details"}
        add_node(choke["key"], choke["name"], kind, [choke["lon"], choke["lat"]], choke["region"], [record, sources["straits"]],
                 positionBasis="Exact published gazetteer reference point for a geographic area; not an exact facility, channel boundary, or incident",
                 positionScope="geographic area reference", sourcePrecisionMeters=choke.get("precisionMeters"), mrgid=choke["mrgid"])

    for assembly in config["assemblies"]:
        province = "province" in assembly
        point, evidence = geo_point(assembly.get("province", assembly.get("city")), assembly["iso"], province)
        add_node("assembly-" + assembly["key"], assembly["name"], "assembly", point, assembly.get("province", assembly.get("city")),
                 [evidence] + [sources[k] for k in assembly["sources"]], precision="province" if province else "city",
                 positionBasis=assembly.get("placementNote", "Regional Natural Earth reference point; not an exact factory pin"),
                 partTypeScope="Inferred aggregate assembly role from public manufacturing evidence; not product-specific plant throughput")
    for region in config["salesRegions"]:
        point, evidence = geo_point(region["city"], region["iso"])
        add_node("sales-" + region["key"], "Apple sales region: " + region["name"], "sales_region", point, region["definition"],
                 [evidence, sources["sales"]], precision="city", salesRegion=region["name"],
                 positionBasis=f"{region['city']} is a geographic display anchor, not a regional Apple headquarters, warehouse or store",
                 regionDefinition=region["definition"])
    add_node("apple-park", "Apple Park", "hq", [-122.00902, 37.3349], "Cupertino, California", [sources["hq"], sources["hqPoint"]],
             establishedOn="2017-04", positionBasis="Published Apple Maps place reference; headquarters context only")

    by_id = {n["id"]: n for n in nodes}

    def add_edge(key, start, finish, mode, source_keys=(), **extra):
        a, b = by_id[PREFIX + start], by_id[PREFIX + finish]
        edge = {"id": PREFIX + "route-" + key, "from": a["id"], "to": b["id"], "mode": mode,
                "carriesTier": 4, "status": "inferred", "layer": "backbone", "referenceAsOf": config["checkedOn"],
                "sources": citations(a["sources"], b["sources"], [sources[k] for k in source_keys]),
                "basis": ROUTE_SCOPE, "routingVerified": False, **extra}
        edges.append(edge)
        return edge

    for assembly in config["assemblies"]:
        for gateway in assembly["gateways"]:
            add_edge(assembly["key"] + "-" + gateway, "assembly-" + assembly["key"], gateway, "road",
                     relation="regional_assembly_access", geometryBasis="Straight reference-point connector; actual road alignment, border crossings and modal transfers unknown")
    regional_anchor = {"americas": "airport-lax", "europe": "airport-fra", "greater-china": "airport-pvg", "japan": "airport-nrt", "rest-apac": "airport-sin"}
    for region in config["salesRegions"]:
        gateway = regional_anchor[region["key"]]
        add_edge(region["key"] + "-sales-access", gateway, "sales-" + region["key"], "road", ["sales"],
                 relation="sales_region_reference_access", geometryBasis="Illustrative local market access to the representative region marker; no distribution facility is asserted")
    for port, region in [("los-angeles", "americas"), ("rotterdam", "europe"), ("shanghai", "greater-china"), ("tokyo", "japan"), ("singapore", "rest-apac")]:
        add_edge(port + "-sales-access", "port-" + port, "sales-" + region, "road", ["sales", "rotterdam"],
                 relation="sales_region_reference_access", geometryBasis="Inferred port-to-market reference connector; not a disclosed distribution route")
    add_edge("new-york-airport-access", "port-new-york", "airport-jfk", "road", relation="regional_gateway_access")
    add_edge("apple-park-access", "airport-sfo", "apple-park", "road", ["hq"], carriesTier=None, relation="headquarters_access")

    origin_airports = ["cgo", "szx", "maa", "blr", "han", "pvg", "hkg", "sin"]
    destination_airports = ["fra", "lax", "nrt", "sin", "pvg"]
    for origin in origin_airports:
        for destination in destination_airports:
            if origin == destination:
                continue
            add_edge(f"air-{origin}-{destination}", "airport-" + origin, "airport-" + destination, "air", ["cargo", "airCorridors"],
                     relation="inferred_cargo_corridor", geometryBasis="Geodesic display arc between airport references; may require intermediate flights")
    for origin, destination in [("pvg", "ams"), ("pvg", "jfk"), ("jfk", "lax"), ("fra", "svo"), ("wuh", "fra"), ("kmj", "nrt"), ("sdj", "nrt"), ("bkk", "fra"), ("dmk", "fra"), ("hph", "fra"), ("tpe", "nrt")]:
        add_edge(f"air-{origin}-{destination}", "airport-" + origin, "airport-" + destination, "air", ["cargo"], relation="inferred_cargo_corridor")
    router = WaterRouter(geo["countries"])
    def pos(key):
        n = by_id[PREFIX + key]
        return [n["lon"], n["lat"]]

    def local(bounds):
        return WaterRouter(step=0.05, bounds=bounds, land=router.land)

    malacca_router = local((94, 0, 106, 8.5))
    bab_router = local((41, 11, 46, 16))
    suez_router = local((31, 24, 36, 32))
    panama_router = local((-81, 7, -78, 11))
    print("Refining Malacca, Bab-el-Mandeb and the Suez approaches", flush=True)
    malacca_path = malacca_router.route([105, 1], pos("malacca")) + malacca_router.route(pos("malacca"), [96, 6])
    bab_path = bab_router.route([45, 12], pos("bab-el-mandeb")) + bab_router.route(pos("bab-el-mandeb"), [42, 15])
    passage_paths = {
        "malacca": malacca_path,
        "bab-el-mandeb": bab_path,
        "suez": suez_router.route([35, 25], pos("port-suez-south")) + [pos("port-suez-south"), pos("suez"), pos("port-said"), [32.5, 32]],
        "panama": panama_router.route([-79.5, 8], pos("port-balboa")) + [pos("port-balboa"), pos("panama"), pos("port-cristobal")] + panama_router.route(pos("port-cristobal"), [-80, 10]),
    }
    coastal_routers = {}

    def water_leg(a, b):
        # Singapore's narrow channels must use the refined local mesh.
        inside = lambda p: 94 <= p[0] <= 106 and 0 <= p[1] <= 8.5
        if inside(a) and inside(b):
            return malacca_router.route(a, b)
        if inside(b) and b[0] >= 102 and a[0] > 106:
            return router.route(a, [105, 1]) + malacca_router.route([105, 1], b)
        return router.route(a, b)

    def coastal_path(port_key, water_point):
        point = pos(port_key)
        if 94 <= point[0] <= 106 and 0 <= point[1] <= 8.5:
            return malacca_router.route(point, water_point)
        if port_key not in coastal_routers:
            x, y = point
            coastal_routers[port_key] = local((round(x - 3, 1), round(y - 3, 1), round(x + 3, 1), round(y + 3, 1)))
        return coastal_routers[port_key].route(point, water_point)
    # Offshore control points impose the sourced global corridor, rather than
    # shortest paths around a different continent. Their placement is inferred.
    controls = {
        "south-china-sea": [112, 12], "singapore-approach": [103.5, 1],
        "indian-ocean": [75, 0], "arabian-sea": [60, 12],
        "cape-east": [30, -36], "cape-west": [15, -36], "atlantic": [-15, -5],
        "gibraltar": [-6, 36], "english-channel": [-3, 50],
        "north-pacific": [-150, 30], "south-of-japan": [145, 30],
        "east-pacific": [-100, 8], "caribbean": [-77, 15],
    }

    def sea(key, a, b, gates, corridor, source_keys=("sea", "straits"), alternative=None):
        points, via_nodes, passages = [], [], []
        cursor = pos(a)
        for gate in [*gates, b]:
            if gate in passage_paths:
                canal = passage_paths[gate]
                if gate not in {"suez", "panama"} and distance_km(cursor, canal[-1]) < distance_km(cursor, canal[0]):
                    canal = list(reversed(canal))
                points.extend(water_leg(cursor, canal[0]))
                # Canal line is a schematic through published references;
                # it is deliberately exempt from the coarse open-water mask.
                points.extend(canal)
                cursor = canal[-1]
                passages.append({"nodeId": PREFIX + gate, "points": canal, "scope": "Schematic canal passage, not a surveyed channel centerline" if gate in {"suez", "panama"} else "Inferred strait passage refined on a 0.05-degree water grid"})
                via_nodes.append(PREFIX + gate)
            else:
                target = controls[gate] if gate in controls else pos(gate)
                points.extend(water_leg(cursor, target))
                cursor = target
                if PREFIX + gate in by_id and by_id[PREFIX + gate]["kind"] in {"chokepoint", "canal"}:
                    via_nodes.append(PREFIX + gate)
        points = coastal_path(a, points[0]) + points + list(reversed(coastal_path(b, points[-1])))
        points = [p for i, p in enumerate(points) if not i or p != points[i - 1]]
        edge = add_edge(key, a, b, "sea", source_keys, via=points, viaNodeIds=via_nodes,
                        corridor=corridor, geometryBasis="Inferred Natural Earth water-grid path: 0.5-degree offshore mesh, 0.05-degree port/strait refinement, and explicit schematic canal passages; published port reference to nearest water connector is not a surveyed channel",
                        geometrySources=[geo_sources["countries"]], narrowPassages=passages)
        edge["sources"] = citations(edge["sources"], [geo_sources["countries"]], *[by_id[n]["sources"] for n in via_nodes])
        if alternative:
            edge["alternativeTo"] = PREFIX + "route-" + alternative
        print(f"Built sea corridor {key}: {len(points)} waypoints", flush=True)

    for origin in ["yantian", "shanghai", "haiphong", "chennai", "singapore"]:
        east = ["taiwan-strait"] if origin == "shanghai" else []
        if origin in {"yantian", "shanghai", "haiphong"}:
            east += ["south-china-sea", "malacca"]
        elif origin == "singapore":
            east = ["malacca"]
        suez_key = f"sea-{origin}-rotterdam-suez"
        sea(suez_key, "port-" + origin, "port-rotterdam", east + ["arabian-sea", "bab-el-mandeb", "suez", "gibraltar", "english-channel"], "Asia-Europe via Suez", ("sea", "straits", "cape"))
        sea(f"sea-{origin}-rotterdam-cape", "port-" + origin, "port-rotterdam", east + ["indian-ocean", "cape-east", "cape-west", "atlantic", "english-channel"], "Asia-Europe via Cape of Good Hope", ("sea", "cape"), suez_key)
    for origin in ["yantian", "shanghai", "haiphong"]:
        gates = ["south-china-sea", "south-of-japan"] if origin in {"yantian", "haiphong"} else ["south-of-japan"]
        sea(f"sea-{origin}-los-angeles-pacific", "port-" + origin, "port-los-angeles", gates + ["north-pacific"], "Asia-Americas Pacific")
        sea(f"sea-{origin}-new-york-panama", "port-" + origin, "port-new-york", gates + ["north-pacific", "east-pacific", "panama", "caribbean"], "Asia-Americas via Panama", ("sea", "straits", "panama"))
    for a, b, gates in [("shanghai", "yantian", ["taiwan-strait"]), ("shanghai", "tokyo", []), ("kaohsiung", "shanghai", ["taiwan-strait"]), ("haiphong", "yantian", []), ("chennai", "singapore", ["malacca", "singapore-approach"]), ("yantian", "singapore", ["south-china-sea", "singapore-approach"]), ("shekou", "singapore", ["south-china-sea", "singapore-approach"]), ("shanghai", "busan", [])]:
        sea(f"sea-{a}-{b}", "port-" + a, "port-" + b, gates, "Inferred regional feeder corridor")

    return {"referenceAsOf": config["checkedOn"], "scope": config["scope"], "approval": config["approval"],
            "datasets": config["datasets"], "geography": geo_config, "nodes": nodes, "edges": edges,
            "routeDefinition": ROUTE_SCOPE,
            "nearestGatewayDefinition": "Minimum haversine distance among the curated backbone port and airport nodes, using each supplier's disclosed city/province/country reference; not the nearest of every gateway worldwide or a verified driving route"}


def nearest_gateway(site, gateways):
    return min(gateways, key=lambda n: (distance_km((site["lon"], site["lat"]), (n["lon"], n["lat"])), n["id"]))


def attach_backbone(network, scenario, event, catalog):
    """Attach display context after model projections and optimizer plans exist."""
    sites = network["nodes"]
    for site in sites:
        site["layer"] = "supplier"
    nodes, edges = copy.deepcopy(catalog["nodes"]), copy.deepcopy(catalog["edges"])
    gateways = [n for n in nodes if n["kind"] in {"port", "airport"}]
    for site in sites:
        gateway = nearest_gateway(site, gateways)
        edges.append({"id": "access-" + site["id"], "from": site["id"], "to": gateway["id"],
                      "mode": "road", "carriesTier": site["tier"], "status": "inferred", "layer": "supplier_access",
                      "sources": citations(site["sources"], gateway["sources"]), "basis": catalog["nearestGatewayDefinition"],
                      "distanceKm": round(distance_km((site["lon"], site["lat"]), (gateway["lon"], gateway["lat"])), 3),
                      "distanceDefinition": "Calculated great-circle reference distance, not road length",
                      "geometryBasis": "Straight geographic access connector; continuous roads, water crossings, borders and actual shipment modes remain unverified",
                      "routingVerified": False})

    event_id = event["id"]
    anchors = {
        "kumamoto-2016": ("airport-kmj", "airport-nrt"),
        "covid-china-2020": ("airport-wuh", "airport-pvg"),
        "japan-2011": ("airport-sdj", "airport-nrt"),
        "thailand-2011": ("airport-bkk", "airport-dmk"),
        "russia-2022": ("airport-svo", None),
    }
    if event_id in anchors:
        point = scenario["shock"]["location"]
        anchor_id = PREFIX + "event-" + event_id
        anchor = {"id": anchor_id, "name": event["title"] + " geographic anchor", "kind": "event_anchor", "layer": "backbone",
                  "lon": point["lon"], "lat": point["lat"], "precision": point["precision"], "region": event["location"],
                  "ticker": None, "partType": None, "appleRevenueShare": None, **inferred_tier(None),
                  "sources": point["sources"], "positionBasis": point["basis"], "eventId": event_id,
                  "scope": "Sourced event geography; not an undisclosed supplier site, cargo demand, or a measured transport closure"}
        nodes.append(anchor)
        affected, alternate = anchors[event_id]
        by_id = {n["id"]: n for n in nodes}
        for gateway_key in filter(None, [affected, alternate]):
            gateway = by_id[PREFIX + gateway_key]
            edges.append({"id": PREFIX + "route-event-access-" + event_id + "-" + gateway_key,
                          "from": anchor_id, "to": gateway["id"], "mode": "road", "carriesTier": None,
                          "status": "inferred", "layer": "backbone", "relation": "regional_event_access",
                          "basis": "Inferred regional geographic access; an epicenter/jurisdiction centroid is an event marker, not a shipment origin or a verified road. No complete gateway closure is asserted.",
                          "sources": citations(anchor["sources"], gateway["sources"]), "routingVerified": False})
        hit_nodes = [anchor_id]
    else:
        hit_nodes = {"suez-2021": [PREFIX + "suez"], "red-sea-2023": [PREFIX + "bab-el-mandeb"],
                     "shanghai-2022": [PREFIX + "port-shanghai", PREFIX + "airport-pvg"],
                     "zhengzhou-2022": [PREFIX + "assembly-zhengzhou"]}[event_id]

    blocked, detour, expedited = [], [], []
    edge_by_id = {e["id"]: e for e in edges}
    if event_id in {"suez-2021", "red-sea-2023"}:
        for edge in edges:
            if any(n in edge.get("viaNodeIds", []) for n in hit_nodes):
                blocked.append(edge["id"])
        detour = [e["id"] for e in edges if e.get("alternativeTo") in blocked]
        expedited = [e["id"] for e in edges if e["mode"] == "air" and e["to"] == PREFIX + "airport-fra" and e["from"] in {PREFIX + "airport-" + c for c in ["cgo", "szx", "maa", "blr", "han", "pvg", "sin", "hkg"]}]
    elif event_id in {"shanghai-2022", "zhengzhou-2022"}:
        blocked = [e["id"] for e in edges if e["from"] in hit_nodes or e["to"] in hit_nodes]
        if event_id == "shanghai-2022":
            detour = [PREFIX + "route-sea-yantian-rotterdam-suez", PREFIX + "route-sea-yantian-los-angeles-pacific"]
            expedited = [PREFIX + "route-air-szx-fra", PREFIX + "route-air-hkg-lax"]
        else:
            detour = [PREFIX + "route-shenzhen-airport-szx", PREFIX + "route-chennai-airport-maa", PREFIX + "route-bengaluru-airport-blr", PREFIX + "route-northern-vietnam-airport-han"]
            expedited = [PREFIX + "route-air-szx-fra", PREFIX + "route-air-maa-lax", PREFIX + "route-air-han-lax"]
    else:
        affected, alternate = anchors[event_id]
        blocked = [PREFIX + "route-event-access-" + event_id + "-" + affected]
        if event_id == "russia-2022":
            blocked.append(PREFIX + "route-air-fra-svo")
            # Export restrictions cannot be bypassed by inventing a detour.
        else:
            detour = [PREFIX + "route-event-access-" + event_id + "-" + alternate]
            destination = "fra" if event_id in {"covid-china-2020", "thailand-2011"} else "lax"
            alternate_code = alternate.removeprefix("airport-")
            key = PREFIX + f"route-air-{alternate_code}-{destination}"
            if key not in edge_by_id:
                by_id = {n["id"]: n for n in nodes}
                a, b = by_id[PREFIX + alternate], by_id[PREFIX + "airport-" + destination]
                edge_by_id[key] = {"id": key, "from": a["id"], "to": b["id"], "mode": "air", "carriesTier": 4,
                                   "status": "inferred", "layer": "backbone", "basis": ROUTE_SCOPE,
                                   "sources": citations(a["sources"], b["sources"]), "routingVerified": False}
                edges.append(edge_by_id[key])
            expedited = [key]
    network["nodes"] = sites + nodes
    network["edges"] = edges
    network["coverage"].update(backboneNodes=len(nodes), supplierAccessLinks=len(sites), backboneRoutes=sum(e["layer"] == "backbone" for e in edges))
    network["scope"] = "Own-year disclosed supplier cohort plus a separately dated contemporary geographic backbone; all shipment and access routes are inferred."
    network["backbone"] = {k: catalog[k] for k in ["referenceAsOf", "scope", "approval", "routeDefinition", "nearestGatewayDefinition"]}
    scenario["shock"]["nodeIds"] = hit_nodes
    scenario["affectedRoutes"] = {"blocked": sorted(blocked), "detour": sorted(detour), "expedited": sorted(expedited)}
    scenario["affectedRoutesStatus"] = "inferred"
    scenario["affectedRoutesBasis"] = "Scenario exposure overlay inferred from sourced disruption geography and reference corridors. 'Blocked' marks potential disrupted access, not proof that each gateway shut or an Apple shipment stopped. Detour and expedited routes are hypothetical alternatives; no capacity, availability, legality or realized rerouting is measured."
    scenario["affectedRoutesSources"] = scenario["sources"]
    scenario["affectedRoutesScope"] = "Display-only; not inputs to the CAR model or to the independent approved indexed optimizer"
    if event_id == "russia-2022":
        scenario["affectedRoutesBasis"] += " No detour or expedition is assigned to evade jurisdictional export restrictions."


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    catalog = build_catalog(offline=args.offline)
    target = ROOT / "data/processed/backbone.json"
    target.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    print(f"Built {len(catalog['nodes'])} reference nodes and {len(catalog['edges'])} inferred corridors")
