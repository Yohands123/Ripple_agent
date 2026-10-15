// Route geometry in map pixels. Every route is a lon/lat line drawn through d3's
// geoPath (lib/georoute.ts), so it follows the globe and splits at the date line.

import { type Pt } from "./geo";
import { lineGeometry, type LineGeometry, type LineStyle } from "./georoute";
import type { Network, NetworkEdge, NetworkNode, NodeKind } from "./types";

const f = (n: number) => n.toFixed(1);

/** Smooth path through points: uniform Catmull-Rom as cubic Béziers (matches the concept art). Used for money lines. */
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

export function nodeIndex(network: Network): Map<string, NetworkNode> {
  return new Map(network.nodes.map((n) => [n.id, n]));
}

// ---------- What an edge is ----------

const SUPPLIER_KINDS = new Set<NodeKind>(["supplier_major", "supplier_minor", "mine", "refinery"]);

/**
 * `route` edges are transport drawn on the map; `supply` edges say who supplies whom
 * (used by the supplier stack and the trace, never drawn as transport). Files without
 * `relation` are read by layer: backbone and supplier-access links are routes. Older
 * files with neither (the fixtures) draw every edge as a route, and an edge from a
 * supplier into an assembly site also counts as supply.
 */
export function isRoute(e: NetworkEdge): boolean {
  // Return routes (repair, recycling, recovered metals) are their own layer, drawn by ReturnLayer.
  if (isReturn(e)) return false;
  if (e.relation === "route") return true;
  if (e.relation === "supply") return false;
  // Before `relation` was route/supply it described the corridor; the layer says what the edge is.
  if (e.layer) return e.layer === "backbone" || e.layer === "supplier_access";
  return true;
}

/** Reverse logistics: sales regions to repair and recycling, and recovered metals back to refineries. */
export const isReturn = (e: NetworkEdge) => e.purpose === "return";

export function isSupply(e: NetworkEdge, nodes: Map<string, NetworkNode>): boolean {
  if (e.relation === "supply") return true;
  if (e.relation === "route" || e.layer) return false;
  const from = nodes.get(e.from);
  const to = nodes.get(e.to);
  return Boolean(from && to && SUPPLIER_KINDS.has(from.kind) && to.kind === "assembly");
}

/**
 * Drawing strength: the backbone at full strength, other inferred routes thinner, supplier
 * links faint. Mineral routes (mining regions to refineries) are dated context, drawn as faint as supplier links.
 */
export type EdgeRank = "backbone" | "inferred" | "supplier" | "context";

export function edgeRank(e: NetworkEdge): EdgeRank {
  if (e.layer === "supplier_access" || e.layer === "supplier") return "supplier";
  if (e.contextLayer === "minerals") return "context";
  if (e.layer && e.layer !== "backbone") return "inferred";
  return "backbone";
}

export const isSupplierKind = (k: NodeKind) => SUPPLIER_KINDS.has(k);

// ---------- Geometry ----------

/** Lon/lat waypoints of an edge, endpoints included. */
export function edgeLonLat(edge: NetworkEdge, nodes: Map<string, NetworkNode>): Pt[] | null {
  const a = nodes.get(edge.from);
  const b = nodes.get(edge.to);
  if (!a || !b) return null;
  return [[a.lon, a.lat], ...(edge.via ?? []), [b.lon, b.lat]];
}

export const styleOf = (edge: NetworkEdge): LineStyle => (edge.mode === "air" ? "arc" : edge.via?.length ? "smooth" : "straight");

const cache = new WeakMap<NetworkEdge, LineGeometry | null>();

/** The edge's line: path data (split at the antimeridian) and its pieces in map pixels. */
export function edgeLine(edge: NetworkEdge, nodes: Map<string, NetworkNode>): LineGeometry | null {
  if (cache.has(edge)) return cache.get(edge)!;
  const ll = edgeLonLat(edge, nodes);
  const g = ll ? lineGeometry(ll, styleOf(edge)) : null;
  cache.set(edge, g);
  return g;
}

/** SVG path for an edge, and the points it was drawn through. */
export function edgeGeometry(edge: NetworkEdge, nodes: Map<string, NetworkNode>): { d: string; pts: Pt[] } | null {
  const g = edgeLine(edge, nodes);
  return g ? { d: g.d, pts: g.pieces.flat() } : null;
}

/** The edge in map pixels, one piece per side of the antimeridian. */
export function edgePieces(edge: NetworkEdge, nodes: Map<string, NetworkNode>): Pt[][] {
  return edgeLine(edge, nodes)?.pieces ?? [];
}

/** All sampled points of an edge (for hit tests and label avoidance). */
export function sampleEdge(edge: NetworkEdge, nodes: Map<string, NetworkNode>): Pt[] {
  return edgePieces(edge, nodes).flat();
}
