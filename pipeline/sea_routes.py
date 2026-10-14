"""Inferred water-only schematic paths from pinned Natural Earth geometry.

This is a map geometry builder, not a navigation service or a traffic model.
Explicit canal passages and coastal endpoint connectors are separate from
the open-water grid. Cached processed paths make exports independent of raw
downloads and of this calculation.
"""

from __future__ import annotations

import heapq
import math
from functools import lru_cache

import numpy as np
from shapely import contains_xy, prepare
from shapely.geometry import LineString, Point, shape
from shapely.ops import unary_union


def distance_km(a, b):
    """Great-circle distance, with longitude wrapping at the dateline."""
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    value = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1, value)))


class WaterRouter:
    def __init__(self, countries=None, step=0.5, bounds=(-180, -80, 180, 80), land=None):
        self.step = step
        self.bounds = bounds
        west, south, east, north = bounds
        self.wrap = east - west == 360
        self.width = round((east - west) / step) + (0 if self.wrap else 1)
        self.height = round((north - south) / step) + 1
        self.land = land if land is not None else unary_union([shape(f["geometry"]) for f in countries["features"]])
        prepare(self.land)
        self.lons = np.arange(self.width) * step + west
        self.lats = np.arange(self.height) * step + south
        lon, lat = np.meshgrid(self.lons, self.lats)
        self.wet = ~contains_xy(self.land, lon, lat)

    def point(self, cell):
        x, y = cell
        return [round(float(self.lons[x]), 6), round(float(self.lats[y]), 6)]

    @lru_cache(maxsize=200000)
    def clear(self, a, b):
        p, q = self.point(a), self.point(b)
        if abs(p[0] - q[0]) > 180:
            # Test each half of the short dateline crossing independently.
            west, east = sorted([p, q])
            mid_lat = (west[1] + east[1]) / 2
            return not self.land.intersects(LineString([west, [-180, mid_lat]])) and not self.land.intersects(LineString([[180, mid_lat], east]))
        return not self.land.intersects(LineString([p, q]))

    @lru_cache(maxsize=512)
    def snap(self, point):
        """Nearest wet grid point; connectors retain their coarse-map scope."""
        x = round((point[0] - self.bounds[0]) / self.step)
        x = x % self.width if self.wrap else min(self.width - 1, max(0, x))
        y = min(self.height - 1, max(0, round((point[1] - self.bounds[1]) / self.step)))
        for radius in range(0, 30):
            candidates = {((x + dx) % self.width if self.wrap else x + dx, y + dy) for dx in range(-radius, radius + 1) for dy in range(-radius, radius + 1)
                          if max(abs(dx), abs(dy)) == radius and 0 <= y + dy < self.height and (self.wrap or 0 <= x + dx < self.width)}
            # Offshore margin avoids isolated harbor/lake grid cells. The
            # endpoint-to-grid connector remains explicitly schematic.
            wet = [c for c in candidates if self.wet[c[1], c[0]] and self.land.distance(Point(self.point(c))) >= self.step]
            if wet:
                return min(wet, key=lambda c: (distance_km(point, self.point(c)), c))
        raise ValueError(f"No nearby water grid point for {point}")

    @lru_cache(maxsize=256)
    def path_cells(self, start, finish):
        costs, previous = {start: 0.0}, {}
        queue = [(distance_km(self.point(start), self.point(finish)), 0.0, start)]
        while queue:
            _, cost, current = heapq.heappop(queue)
            if cost > costs[current] + 1e-8:
                continue
            if current == finish:
                result = [current]
                while result[-1] in previous:
                    result.append(previous[result[-1]])
                return tuple(reversed(result))
            x, y = current
            for dx, dy in [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]:
                neighbor = ((x + dx) % self.width if self.wrap else x + dx, y + dy)
                if not 0 <= neighbor[1] < self.height or not 0 <= neighbor[0] < self.width or not self.wet[neighbor[1], neighbor[0]] or not self.clear(current, neighbor):
                    continue
                candidate = cost + distance_km(self.point(current), self.point(neighbor))
                if candidate < costs.get(neighbor, math.inf):
                    costs[neighbor], previous[neighbor] = candidate, current
                    estimate = candidate + distance_km(self.point(neighbor), self.point(finish))
                    heapq.heappush(queue, (estimate, candidate, neighbor))
        raise ValueError(f"No water path between {start} and {finish}")

    def route(self, a, b):
        cells = self.path_cells(self.snap(tuple(a)), self.snap(tuple(b)))
        # Keep every grid bend. Removing only collinear runs cannot cross land.
        keep = [cells[0]]
        direction = None
        for previous, current in zip(cells, cells[1:]):
            dx = current[0] - previous[0]
            if self.wrap:
                dx = (dx + self.width // 2) % self.width - self.width // 2
            value = (dx, current[1] - previous[1])
            if direction is not None and value != direction:
                keep.append(previous)
            direction = value
        if keep[-1] != cells[-1]:
            keep.append(cells[-1])
        return [self.point(c) for c in keep]
