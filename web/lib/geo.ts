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

export const projection = geoEquirectangular()
  .scale((PX_PER_DEGREE * 180) / Math.PI)
  .translate([-VIEW_WEST * PX_PER_DEGREE, VIEW_NORTH * PX_PER_DEGREE])
  .clipExtent([
    [-40, -40],
    [size.mapW + 40, size.mapH + 40],
  ]);

export const pathFor = geoPath(projection);

export type Pt = [number, number];

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
