// Route geometry in map pixels.

import { project, type Pt } from "./geo";
import { sampleQuad, sampleSmooth } from "./polyline";
import type { Network, NetworkEdge, NetworkNode } from "./types";

const f = (n: number) => n.toFixed(1);

/** Smooth path through points: uniform Catmull-Rom as cubic Béziers (matches the concept art). */
export function smoothPath(pts: Pt[]): string {
  if (pts.length === 0) return "";
  let d = `M${f(pts[0][0])} ${f(pts[0][1])}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(pts.length - 1, i + 2)];
    const c1: Pt = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2: Pt = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += ` C${f(c1[0])} ${f(c1[1])} ${f(c2[0])} ${f(c2[1])} ${f(p2[0])} ${f(p2[1])}`;
  }
  return d;
}

/** Air routes are a quadratic arc bowing north (up). */
export function arcControl(a: Pt, b: Pt): Pt {
  return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 0.19 * Math.abs(b[0] - a[0])];
}

export function arcPath(a: Pt, b: Pt): string {
  const c = arcControl(a, b);
  return `M${f(a[0])} ${f(a[1])} Q${f(c[0])} ${f(c[1])} ${f(b[0])} ${f(b[1])}`;
}

export function nodeIndex(network: Network): Map<string, NetworkNode> {
  return new Map(network.nodes.map((n) => [n.id, n]));
}

/** Lon/lat waypoints of an edge, endpoints included. */
export function edgeLonLat(edge: NetworkEdge, nodes: Map<string, NetworkNode>): Pt[] | null {
  const a = nodes.get(edge.from);
  const b = nodes.get(edge.to);
  if (!a || !b) return null;
  return [[a.lon, a.lat], ...(edge.via ?? []), [b.lon, b.lat]];
}

export function edgePoints(edge: NetworkEdge, nodes: Map<string, NetworkNode>): Pt[] | null {
  const ll = edgeLonLat(edge, nodes);
  return ll ? ll.map(([lon, lat]) => project(lon, lat)) : null;
}

/** SVG path for an edge, and the control points it was drawn through. */
export function edgeGeometry(edge: NetworkEdge, nodes: Map<string, NetworkNode>): { d: string; pts: Pt[] } | null {
  const pts = edgePoints(edge, nodes);
  if (!pts) return null;
  if (edge.mode === "air") return { d: arcPath(pts[0], pts[pts.length - 1]), pts: [pts[0], pts[pts.length - 1]] };
  return { d: smoothPath(pts), pts };
}

/** Samples a route as a polyline (for movers, hit tests, and label avoidance). */
export function sampleEdge(edge: NetworkEdge, nodes: Map<string, NetworkNode>, step = 6): Pt[] {
  const pts = edgePoints(edge, nodes);
  if (!pts) return [];
  if (edge.mode === "air") {
    const [a, b] = [pts[0], pts[pts.length - 1]];
    return sampleQuad(a, arcControl(a, b), b, step);
  }
  return sampleSmooth(pts, step);
}
