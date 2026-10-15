// Keeping the map readable at every zoom: what is drawn at world, region, and country
// zoom; lanes that share water drawn once; air routes bundled; ships spaced by screen
// distance; and supplier sites gathered into clusters until you zoom into a country.

import { projection, type Pt } from "./geo";
import { continentOf } from "./layout";
import { linePath, screenPieces } from "./georoute";
import { isSupplierKind } from "./routes";
import type { NetworkEdge, NetworkNode } from "./types";

// ---------- Zoom bands ----------

export type Band = "world" | "region" | "country";

/** Zoom (relative to the concept-art view) where each band starts. */
export const REGION_K = 1.6;
export const COUNTRY_K = 3.5;

export const bandOf = (k: number): Band => (k >= COUNTRY_K - 1e-6 ? "country" : k >= REGION_K - 1e-6 ? "region" : "world");

/** A representative zoom for each band, for sizing things in screen pixels. */
export const BAND_K: Record<Band, number> = { world: 1, region: 2.4, country: 5 };

// ---------- Lanes that share water ----------

export interface DrawnLine {
  id: string;
  /** Path data for the parts not already drawn by an earlier line. */
  d: string;
  /** Those parts in map pixels, one polyline per run. */
  pieces: Pt[][];
}

/**
 * Draws each line only where no earlier line already runs (within `tol` map px), so
 * lanes that share water look like one lane and their dashes stay in step.
 * Lines are taken in the order given (put the most important first).
 */
export function trimOverlaps(lines: { id: string; lonlat: Pt[] }[], tol = 3): DrawnLine[] {
  const cell = tol;
  const grid = new Map<string, Pt[]>();
  const keyOf = (x: number, y: number) => `${Math.floor(x / cell)},${Math.floor(y / cell)}`;
  const near = (p: Pt) => {
    const cx = Math.floor(p[0] / cell);
    const cy = Math.floor(p[1] / cell);
    for (let dx = -1; dx <= 1; dx++)
      for (let dy = -1; dy <= 1; dy++)
        for (const q of grid.get(`${cx + dx},${cy + dy}`) ?? []) if (Math.hypot(q[0] - p[0], q[1] - p[1]) <= tol) return true;
    return false;
  };
  const out: DrawnLine[] = [];
  for (const line of lines) {
    const proj = line.lonlat.map((ll) => projection(ll) as Pt);
    const shared = proj.map(near);
    const runs: Pt[][] = [];
    let cur: Pt[] = [];
    line.lonlat.forEach((ll, i) => {
      if (!shared[i]) {
        // Start one sample back so the run joins the line it leaves.
        if (cur.length === 0 && i > 0) cur.push(line.lonlat[i - 1]);
        cur.push(ll);
      } else if (cur.length) {
        cur.push(ll);
        runs.push(cur);
        cur = [];
      }
    });
    if (cur.length) runs.push(cur);
    const kept = runs.filter((r) => r.length > 1);
    out.push({ id: line.id, d: kept.map(linePath).join(""), pieces: kept.flatMap(screenPieces) });
    for (const p of proj) {
      const k = keyOf(p[0], p[1]);
      const list = grid.get(k);
      if (list) list.push(p);
      else grid.set(k, [p]);
    }
  }
  return out;
}

// ---------- Lane names ----------

/**
 * The name a lane is labelled by. Lanes are grouped by their corridor (the part of
 * `laneName` after the dash, e.g. "Asia-Europe via Suez"), so the five ports feeding the
 * same corridor share one label. Without names, the continents at each end are used.
 */
export function laneLabel(edge: NetworkEdge): string | null {
  const named = edge.corridor ?? edge.laneName?.split(/\s[—–-]\s/).pop();
  return named ? named.toUpperCase() : null;
}

/** Name for a chain of unnamed lanes joined end to end (e.g. Shenzhen → Suez → Rotterdam): the continents at its ends. */
export function chainLabel(chain: NetworkEdge[], nodes: Map<string, NetworkNode>): string | null {
  const edge = { ...chain[0], to: chain[chain.length - 1].to };
  const a = nodes.get(edge.from);
  const b = nodes.get(edge.to);
  if (!a || !b) return null;
  const from = continentOf(a.lon, a.lat);
  const to = continentOf(b.lon, b.lat);
  return from === to ? null : `${from} TO ${to} SEA LANE`.toUpperCase();
}

// ---------- Air bundles ----------

export interface AirBundle {
  key: string;
  /** The arc drawn for the bundle: origin to the destination most of its routes use. */
  edge: NetworkEdge;
  edges: NetworkEdge[];
  count: number;
}

/** One arc per origin to destination region, its width set by how many routes it stands for. */
export function airBundles(edges: NetworkEdge[], nodes: Map<string, NetworkNode>): AirBundle[] {
  const groups = new Map<string, NetworkEdge[]>();
  for (const e of edges) {
    if (e.mode !== "air") continue;
    const to = nodes.get(e.to);
    if (!to) continue;
    const key = `${e.from}>${continentOf(to.lon, to.lat)}`;
    groups.set(key, [...(groups.get(key) ?? []), e]);
  }
  const outDegree = new Map<string, number>();
  for (const e of edges) if (e.mode === "air") outDegree.set(e.from, (outDegree.get(e.from) ?? 0) + 1);
  return [...groups.entries()]
    .map(([key, list]) => {
      // Draw to the destination furthest away, so the arc spans the whole bundle.
      const from = nodes.get(list[0].from)!;
      const far = list.reduce((a, b) => {
        const da = nodes.get(a.to)!;
        const db = nodes.get(b.to)!;
        return Math.hypot(db.lon - from.lon, db.lat - from.lat) > Math.hypot(da.lon - from.lon, da.lat - from.lat) ? b : a;
      });
      return { key, edge: far, edges: list, count: list.length };
    })
    .sort((a, b) => b.count - a.count || (outDegree.get(b.edge.from) ?? 0) - (outDegree.get(a.edge.from) ?? 0) || a.key.localeCompare(b.key));
}

/** How many bundles to draw: the top five at world zoom, all of them closer in. */
export const airLimit = (band: Band) => (band === "world" ? 5 : Infinity);

// ---------- Ships ----------

/** At most one ship per lane per this many screen pixels. */
export const SHIP_SCREEN_GAP = 200;
/** About this many ships in view. */
export const SHIP_CAP = 20;

/**
 * Ship counts for each piece of lane: one per 200 screen pixels at the band's zoom,
 * then scaled down so the whole map carries about `SHIP_CAP` ships per screenful.
 */
export function shipCounts(lengths: number[], band: Band): number[] {
  const k = BAND_K[band];
  const raw = lengths.map((len) => Math.floor((len * k) / SHIP_SCREEN_GAP));
  // Zoomed in, only part of the map is on screen, so more ships fit on the whole map.
  const cap = SHIP_CAP * (band === "world" ? 1 : band === "region" ? 2 : 4);
  const total = raw.reduce((a, b) => a + b, 0);
  if (total <= cap) return raw.map((n, i) => (n === 0 && lengths[i] * k > 60 ? 1 : n));
  const f = cap / total;
  return raw.map((n) => Math.floor(n * f));
}

// ---------- Supplier clusters ----------

export interface Cluster {
  id: string;
  x: number;
  y: number;
  members: NetworkNode[];
  /** The tier most members have (null when unknown for most). */
  tier: number | null;
}

/** Cluster radius on screen, px. */
const CLUSTER_PX = 30;

export const isClusterable = (n: NetworkNode) => isSupplierKind(n.kind);

/**
 * Supplier sites gathered into clusters at zoom level L (radius 30 screen px).
 * Singletons stay sites. Zoomed into a country (L ≥ COUNTRY_K) nothing is clustered.
 */
export function clusterSites(nodes: NetworkNode[], points: Map<string, Pt>, L: number): Cluster[] {
  const sites = nodes.filter(isClusterable);
  if (L >= COUNTRY_K - 1e-6) return sites.map((n) => single(n, points));
  const r = CLUSTER_PX / L;
  const seeds: { x: number; y: number; members: NetworkNode[] }[] = [];
  // Densest first, so cluster centres sit where sites crowd.
  const order = [...sites].sort((a, b) => a.id.localeCompare(b.id));
  for (const n of order) {
    const [x, y] = points.get(n.id)!;
    const hit = seeds.find((s) => Math.hypot(s.x - x, s.y - y) <= r);
    if (hit) hit.members.push(n);
    else seeds.push({ x, y, members: [n] });
  }
  return seeds.map((s) => {
    if (s.members.length === 1) return single(s.members[0], points);
    const pts = s.members.map((m) => points.get(m.id)!);
    return {
      id: `cluster-${s.members[0].id}`,
      x: pts.reduce((a, p) => a + p[0], 0) / pts.length,
      y: pts.reduce((a, p) => a + p[1], 0) / pts.length,
      members: s.members,
      tier: commonTier(s.members),
    };
  });
}

function single(n: NetworkNode, points: Map<string, Pt>): Cluster {
  const [x, y] = points.get(n.id)!;
  return { id: n.id, x, y, members: [n], tier: n.tier };
}

/** Most common known tier; null when most members have none. */
export function commonTier(members: NetworkNode[]): number | null {
  const counts = new Map<number | null, number>();
  for (const m of members) counts.set(m.tier, (counts.get(m.tier) ?? 0) + 1);
  let best: number | null = null;
  let n = -1;
  for (const [t, c] of counts) if (c > n || (c === n && t !== null && best === null)) [best, n] = [t, c];
  return best;
}

/** Bubble diameter on screen for a cluster of n sites. */
export const bubbleSize = (n: number) => Math.round(18 + 5 * Math.sqrt(n));

