// Routes as GeoJSON LineStrings drawn through d3's geoPath, so they follow the globe
// and split cleanly where they cross the antimeridian (Asia to the Americas goes
// across the Pacific, leaving the map on one side and entering on the other).
//
// Geometry is built in lon/lat: sea and road routes are smoothed through their
// waypoints (a Catmull-Rom spline, which on this equirectangular map is the same
// curve the concept art draws), and air routes bow north the way the concept art's
// arcs do. Longitudes are unwrapped first, so a route never takes the long way round.

import { geoPath } from "d3-geo";
import type { LineString } from "geojson";
import { PX_PER_DEGREE, projection, type Pt } from "./geo";
import { sampleQuad, sampleSmooth } from "./polyline";

const path = geoPath(projection);

/** Sample spacing in degrees for the dense lon/lat line. */
const STEP_DEG = 0.35;

/** Longitudes adjusted by ±360° so consecutive points never jump more than 180°. */
export function unwrap(pts: Pt[]): Pt[] {
  const out: Pt[] = [];
  for (const [lon, lat] of pts) {
    if (out.length === 0) {
      out.push([lon, lat]);
      continue;
    }
    const prev = out[out.length - 1][0];
    let l = lon;
    while (l - prev > 180) l -= 360;
    while (l - prev < -180) l += 360;
    out.push([l, lat]);
  }
  return out;
}

export type LineStyle = "smooth" | "arc" | "straight";

/** Dense lon/lat samples of a route through `pts` (endpoints included). */
export function denseLonLat(pts: Pt[], style: LineStyle): Pt[] {
  const u = unwrap(pts);
  if (u.length < 2) return u;
  if (style === "arc") {
    const a = u[0];
    const b = u[u.length - 1];
    // The concept art's air arc: a quadratic whose control point sits north of the midpoint.
    const c: Pt = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 0.19 * Math.abs(b[0] - a[0])];
    return sampleQuad(a, c, b, STEP_DEG);
  }
  if (style === "smooth" && u.length > 2) return sampleSmooth(u, STEP_DEG);
  // Straight in lon/lat, densified so the drawn line and the sampled one agree.
  const out: Pt[] = [u[0]];
  for (let i = 1; i < u.length; i++) {
    const [x0, y0] = u[i - 1];
    const [x1, y1] = u[i];
    const n = Math.max(1, Math.ceil(Math.hypot(x1 - x0, y1 - y0) / STEP_DEG));
    for (let j = 1; j <= n; j++) out.push([x0 + ((x1 - x0) * j) / n, y0 + ((y1 - y0) * j) / n]);
  }
  return out;
}

/** SVG path data for a lon/lat line, split at the antimeridian by d3. */
export function linePath(lonlat: Pt[]): string {
  if (lonlat.length < 2) return "";
  const line: LineString = { type: "LineString", coordinates: lonlat };
  return path(line) ?? "";
}

const WRAP_JUMP = 180 * PX_PER_DEGREE;

/** The line in map pixels, as one piece per side of the antimeridian. */
export function screenPieces(lonlat: Pt[]): Pt[][] {
  const pieces: Pt[][] = [];
  let cur: Pt[] = [];
  for (const ll of lonlat) {
    const p = projection(ll) as Pt | null;
    if (!p) continue;
    const prev = cur[cur.length - 1];
    if (prev && Math.abs(p[0] - prev[0]) > WRAP_JUMP) {
      if (cur.length > 1) pieces.push(cur);
      cur = [];
    }
    cur.push(p);
  }
  if (cur.length > 1) pieces.push(cur);
  return pieces;
}

export interface LineGeometry {
  lonlat: Pt[];
  d: string;
  pieces: Pt[][];
}

export function lineGeometry(pts: Pt[], style: LineStyle): LineGeometry {
  const lonlat = denseLonLat(pts, style);
  return { lonlat, d: linePath(lonlat), pieces: screenPieces(lonlat) };
}
