"""Offline sea-route validation against pinned Natural Earth physical land.

The only geographic allowances are 3 km around port endpoints and a 1 km
cartographic corridor around independently pinned Suez/Panama centerlines.
Exported edge metadata cannot create exemptions. This is not navigation data.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

from shapely import from_wkb, to_wkb, prepare
from shapely.affinity import scale
from shapely.geometry import LineString, Point, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/"
DATASETS = {
    "land": {"file": "ne_10m_land.geojson", "sha256": "1ac90796408bc6ad6911d69448485d3c4dbf2190370080368a09976e1c9f7416"},
    "canals": {"file": "ne_10m_rivers_lake_centerlines.geojson", "sha256": "bb854a900ecbd3b408df46d5e16e3e0f974ba55993f9d8b5c26e855273c0905a"},
}
SOURCES = [{"title": "Natural Earth 5.1.2 physical " + key, "url": BASE + item["file"]} for key, item in DATASETS.items()]


def build():
    raw = {}
    for key, spec in DATASETS.items():
        payload = (ROOT / "data/raw/backbone" / spec["file"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != spec["sha256"]:
            raise ValueError("Natural Earth source hash mismatch: " + key)
        raw[key] = json.loads(payload)
    land = unary_union([shape(f["geometry"]) for f in raw["land"]["features"]])
    canals = {}
    for name in ["Suez", "Panama"]:
        segments = []
        for feature in raw["canals"]["features"]:
            if feature["properties"].get("name") != name + " Canal":
                continue
            geom = shape(feature["geometry"])
            segments.extend([list(g.coords) for g in geom.geoms] if geom.geom_type == "MultiLineString" else [list(geom.coords)])
        if not segments:
            raise ValueError("Missing independently sourced canal: " + name)
        # Connect the tiny rounding gaps between adjacent river/lake records.
        ends = [(i, j, p) for i, s in enumerate(segments) for j, p in [(0, s[0]), (-1, s[-1])]]
        terminals = [(i, j, p) for i, j, p in ends if min(Point(p).distance(Point(q)) for k, _, q in ends if k != i) > .002]
        i, j, _ = min(terminals, key=lambda t: t[2][1])  # southern entrance first
        line = segments.pop(i)
        if j == -1:
            line.reverse()
        while segments:
            _, i, reverse = min((Point(line[-1]).distance(Point(s[-1 if rev else 0])), i, rev) for i, s in enumerate(segments) for rev in [False, True])
            tail = segments.pop(i)
            if reverse:
                tail.reverse()
            if Point(line[-1]).distance(Point(tail[0])) > .002:
                raise ValueError("Disconnected canal records: " + name)
            line.extend(tail if line[-1] != tail[0] else tail[1:])
        canals[name.lower()] = line
    target = ROOT / "data/processed/sea_land.wkb.gz"
    payload = gzip.compress(to_wkb(land), mtime=0)
    target.write_bytes(payload)
    metadata = {"sources": SOURCES, "sourcePins": DATASETS, "landSha256": hashlib.sha256(payload).hexdigest(),
                "landFile": target.name, "canalCenterlines": canals, "portToleranceKm": 3,
                "canalCartographicToleranceKm": 1,
                "basis": "Exact union of Natural Earth 5.1.2 physical land polygons; no simplification. Independently sourced named canal centerlines permit narrow cartographic corridors only."}
    (ROOT / "data/processed/sea_geometry.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Pinned {len(payload)} compressed bytes of physical land and {len(canals)} canal centerlines")


def km_buffer(geometry, km, latitude):
    cosine = math.cos(math.radians(latitude))
    scaled = scale(geometry, xfact=cosine, yfact=1, origin=(0, 0))
    return scale(scaled.buffer(km / 111.32), xfact=1 / cosine, yfact=1, origin=(0, 0))


@lru_cache(maxsize=1)
def geometry():
    metadata = json.loads((ROOT / "data/processed/sea_geometry.json").read_text(encoding="utf-8"))
    payload = (ROOT / "data/processed" / metadata["landFile"]).read_bytes()
    if hashlib.sha256(payload).hexdigest() != metadata["landSha256"]:
        raise ValueError("Pinned physical land mask hash mismatch")
    land = from_wkb(gzip.decompress(payload))
    for points in metadata["canalCenterlines"].values():
        line = LineString(points)
        land = land.difference(km_buffer(line, 1, line.centroid.y))
    prepare(land)
    return land, metadata


def dense(points, step=.05):
    result = [list(points[0])]
    for a, b in zip(points, points[1:]):
        count = max(1, math.ceil(math.dist(a, b) / step))
        result.extend([[round(a[d] + (b[d] - a[d]) * t / count, 6) for d in range(2)] for t in range(1, count + 1)])
    return result


def smooth(points):
    """Catmull-Rom geometry used by web/lib/polyline.ts, sampled more finely."""
    out = [points[0]]
    for i, (p1, p2) in enumerate(zip(points, points[1:])):
        p0, p3 = points[max(0, i - 1)], points[min(len(points) - 1, i + 2)]
        c1 = [p1[d] + (p2[d] - p0[d]) / 6 for d in range(2)]
        c2 = [p2[d] - (p3[d] - p1[d]) / 6 for d in range(2)]
        for j in range(1, 9):
            t, u = j / 8, 1 - j / 8
            out.append([u**3 * p1[d] + 3*u*u*t*c1[d] + 3*u*t*t*c2[d] + t**3*p2[d] for d in range(2)])
    return out


@lru_cache(maxsize=512)
def check_path(points, port_points):
    if any(abs(a[0] - b[0]) > 180 for a, b in zip(points, points[1:])):
        return ("unsplit date-line crossing would draw across the world",)
    if len(set(points)) < 2:
        return ("sea route needs at least two distinct positions",)
    land, _ = geometry()
    allowed = unary_union([km_buffer(Point(p), 3, p[1]) for p in port_points])
    errors = []
    for label, coords in [("polyline", points), ("smoothed ship path", smooth(points))]:
        line = LineString(coords)
        if not land.intersects(line):
            continue
        intersection = land.intersection(line).difference(allowed)
        if not intersection.is_empty:
            location = intersection.representative_point()
            errors.append(f"{label} crosses land near {location.x:.5f}, {location.y:.5f}")
    return tuple(errors)


def sea_route_errors(edge, nodes):
    a, b = nodes[edge["from"]], nodes[edge["to"]]
    raw = [(a["lon"], a["lat"]), *map(tuple, edge.get("via", [])), (b["lon"], b["lat"])]
    points = tuple(p for i, p in enumerate(raw) if not i or p != raw[i - 1])
    ports = tuple((n["lon"], n["lat"]) for n in [a, b] if n["kind"] == "port")
    return check_path(points, ports)


if __name__ == "__main__":
    build()
