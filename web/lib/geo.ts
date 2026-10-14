// Map projection and Natural Earth geometry.
//
// The concept art frames the map as an equirectangular crop at 8.6 px per degree
// with its top-left corner at 25°W, 57°N (1440 × 810 px covers 25°W–142.4°E,
// 57°N–37.2°S). Fixture nodes land on the reference positions with this frame.

import { geoContains, geoEquirectangular, geoPath, type GeoPermissibleObjects } from "d3-geo";
import { feature, merge } from "topojson-client";
import type { Feature, FeatureCollection, Geometry, MultiPolygon } from "geojson";
import type { GeometryCollection, Topology } from "topojson-specification";
import { size } from "./tokens";

export const PX_PER_DEGREE = 8.6;
export const VIEW_WEST = -25;
export const VIEW_NORTH = 57;

// The whole world is drawn in the same pixel space, so panning reaches every continent.
export const projection = geoEquirectangular()
  .scale((PX_PER_DEGREE * 180) / Math.PI)
  .translate([-VIEW_WEST * PX_PER_DEGREE, VIEW_NORTH * PX_PER_DEGREE]);

export const pathFor = geoPath(projection);

export type Pt = [number, number];

/** Pannable extent in map pixels: 180°W to 180°E, 84°N to 58°S (Antarctica left out). */
export const WORLD_BOUNDS = {
  x0: (-180 - VIEW_WEST) * PX_PER_DEGREE,
  x1: (180 - VIEW_WEST) * PX_PER_DEGREE,
  y0: (VIEW_NORTH - 84) * PX_PER_DEGREE,
  y1: (VIEW_NORTH + 58) * PX_PER_DEGREE,
};

/** Map pixel x of the antimeridian on each side. */
export const DATELINE_WEST = WORLD_BOUNDS.x0;
export const DATELINE_EAST = WORLD_BOUNDS.x1;

/** The concept-art view: what the map shows before any pan or zoom. */
export const DEFAULT_FRAME = { x: 0, y: 0, w: size.mapW, h: size.mapH };

export function project(lon: number, lat: number): Pt {
  return [(lon - VIEW_WEST) * PX_PER_DEGREE, (VIEW_NORTH - lat) * PX_PER_DEGREE];
}

export interface Country {
  id: string;
  name: string;
  feature: Feature<Geometry>;
}

export interface WorldGeometry {
  land: string;
  countries: Country[];
}

let worldPromise: Promise<WorldGeometry> | null = null;

/** Loads Natural Earth 1:50m land and countries (via world-atlas) once. */
export function loadWorld(): Promise<WorldGeometry> {
  if (!worldPromise) {
    worldPromise = import("world-atlas/countries-50m.json").then((mod) => {
      const topo = (mod.default ?? mod) as unknown as Topology<{ countries: GeometryCollection<{ name: string }> }>;
      const countriesObj = topo.objects.countries;
      const landGeom: MultiPolygon = merge(topo, countriesObj.geometries as never);
      const fc = feature(topo, countriesObj) as FeatureCollection<Geometry, { name: string }>;
      const countries = fc.features.map((f, i) => ({
        id: String(f.id ?? i),
        name: f.properties?.name ?? "",
        feature: f as Feature<Geometry>,
      }));
      return { land: pathFor(landGeom as GeoPermissibleObjects) ?? "", countries };
    });
  }
  return worldPromise;
}

/** The country containing a point, if any. */
export function countryAt(world: WorldGeometry, lon: number, lat: number): Country | undefined {
  return world.countries.find((c) => geoContains(c.feature, [lon, lat]));
}

export function countryPath(c: Country): string {
  return pathFor(c.feature) ?? "";
}
