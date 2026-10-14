// Everything drawn on the map for one state (free flow or a dropped disruption),
// derived only from the network, the scenario file, and the layout.

import { DATELINE_EAST, DATELINE_WEST, type Pt } from "./geo";
import { continentOf, largePillBox, placeBox, smallPillBox, spiral, type MapLayout } from "./layout";
import { Polyline, sampleSmooth } from "./polyline";
import { edgeGeometry, nodeIndex, sampleEdge, smoothPath } from "./routes";
import { color, size, tierColor, type CoinKind } from "./tokens";
import type { Network, NetworkEdge, NetworkNode, Scenario } from "./types";

export type RouteState = "normal" | "blocked" | "detour" | "expedited";

export interface RouteDraw {
  id: string;
  edge: NetworkEdge;
  d: string;
  state: RouteState;
  color: string;
}

export interface MoneyLine {
  id: string;
  kind: "in" | "out";
  d: string;
  path: Polyline;
}

export interface Mover {
  id: string;
  kind: "ship" | "coin";
  coin?: CoinKind;
  size?: number;
  path: Polyline;
  /** Starting distance along the path, px. */
  offset: number;
  /** Travel speed in px per second; 0 means it never moves. */
  speed: number;
  /** Travel only within [from, to] along the path; defaults to the whole path. */
  span?: [number, number];
  opacity?: number;
  rotate?: number;
  /** Falling coin: fades and turns (by `rotate` degrees in total) as it travels. */
  fall?: boolean;
  /** CSS class for the orchestrated entrance (e.g. "enter-coins"). */
  enter?: string;
}

export interface MapPill {
  key: string;
  text: string;
  big: boolean;
  bg: string;
  fg: string;
  x: number;
  y: number;
}

export interface Caption {
  key: string;
  text: string;
  x: number;
  y: number;
  w: number;
  color: string;
}

export interface ShockZone {
  key: string;
  x: number;
  y: number;
  d: number;
}

export interface Marker {
  key: string;
  kind: "predicted" | "actual-hit" | "actual-miss";
  x: number;
  y: number;
  /** Ring radius, px. */
  r: number;
  low: boolean;
}

export interface Scene {
  markers?: Marker[];
  zones?: ShockZone[];
  /** Replacement text for regional group pills, keyed by continent. */
  groupText?: Record<string, string>;
  routes: RouteDraw[];
  money: MoneyLine[];
  movers: Mover[];
  pills: MapPill[];
  captions: Caption[];
  /** Edges the layout should treat as drawn (for label avoidance). */
  visibleEdges: NetworkEdge[];
}

export const SHIP_SPACING = 240;
export const SHIP_SPEED = 14;
export const COIN_SPEED = 22;
export const MONEY_COINS = 3;

/** Edges drawn in free flow: everything except routes that only exist as a scenario's detour. */
export function freeFlowEdges(network: Network, scenario: Scenario | null): NetworkEdge[] {
  const detourOnly = new Set(scenario?.affectedRoutes.detour ?? []);
  return network.edges.filter((e) => !detourOnly.has(e.id));
}

/** Where revenue leaves each regional sales group: its nearest shipping node, or the group's first node. */
function salesHubs(network: Network, layout: MapLayout): Pt[] {
  return layout.groups.map((g) => {
    const members = network.nodes.filter((n) => g.nodeIds.includes(n.id));
    const ports = network.nodes.filter((n) => n.kind === "port" || n.kind === "airport");
    let best: NetworkNode | null = null;
    let bestD = Infinity;
    for (const p of ports) {
      for (const m of members) {
        const d = Math.hypot(p.lon - m.lon, p.lat - m.lat);
        if (d < bestD && d < 12) {
          bestD = d;
          best = p;
        }
      }
    }
    return layout.points.get((best ?? members[0]).id)!;
  });
}

function revenueLine(from: Pt, to: Pt): Pt[] {
  const lerp = (t: number): Pt => [from[0] + (to[0] - from[0]) * t, from[1] + (to[1] - from[1]) * t];
  const a = lerp(0.27);
  const b = lerp(0.64);
  return [from, [a[0], a[1] + 13], [b[0], b[1] + 12.5], to];
}

/**
 * Revenue heading to an Apple Park outside the concept view keeps the concept-art
 * shape up to the pinned card, then carries on to Apple Park's real location.
 */
function revenueToHq(hub: Pt, hq: NonNullable<MapLayout["hq"]>): Pt[] {
  if (!hq.offMap) return revenueLine(hub, hq.anchor);
  const pin = hq.pin.anchor;
  const [tx, ty] = hq.anchor;
  const onward: Pt[] = [
    [pin[0] + (tx - pin[0]) * 0.3, pin[1] + (ty - pin[1]) * 0.15],
    [pin[0] + (tx - pin[0]) * 0.7, pin[1] + (ty - pin[1]) * 0.6],
    [tx, ty],
  ];
  return [...revenueLine(hub, pin), ...onward];
}

/** Spend crosses the Pacific: it enters the concept view at the right edge and curls into the target. */
function spendEast(to: Pt): Pt[] {
  const [x, y] = to;
  return [
    [DATELINE_EAST, y - 62],
    [size.mapW + 22, y - 60],
    [x + 155, y - 43],
    [x + 95, y - 37],
    [x + 35, y - 41],
    [x, y],
  ];
}

/** The same payment leaving Apple Park westward, up to the antimeridian. */
function spendWest(from: Pt, to: Pt): Pt[] {
  const yEdge = to[1] - 62;
  return [from, [from[0] - 160, from[1] + (yEdge - from[1]) * 0.6 + 18], [DATELINE_WEST, yEdge]];
}

export interface MoneyGeometry {
  revenue: { pts: Pt[]; hub: Pt }[];
  /** Spend is one or two segments (split where it crosses the antimeridian), in travel order. */
  spend: { segments: Pt[][]; target: Pt } | null;
}

/** Money lines: revenue from each sales region to Apple Park, spend from Apple Park to the assembly nearest the Pacific. */
export function moneyGeometry(network: Network, layout: MapLayout): MoneyGeometry {
  if (!layout.hq) return { revenue: [], spend: null };
  const hq = layout.hq;
  const revenue = salesHubs(network, layout).map((hub) => ({ hub, pts: revenueToHq(hub, hq) }));
  const assemblies = network.nodes.filter((n) => n.kind === "assembly");
  let spend: MoneyGeometry["spend"] = null;
  if (assemblies.length) {
    const east = assemblies.reduce((a, b) => (b.lon > a.lon ? b : a));
    const target = layout.points.get(east.id)!;
    const acrossPacific = hq.offMap && hq.anchor[0] < target[0];
    spend = { target, segments: acrossPacific ? [spendWest(hq.anchor, target), spendEast(target)] : [[hq.anchor, target]] };
  }
  return { revenue, spend };
}

/**
 * Coins along money lines, spaced so the concept view shows the same three coins
 * per line; the rest travel on beyond it (behind the pinned card or off the edge).
 */
export function moneyCoins(
  mg: MoneyGeometry,
  layout: MapLayout,
): { lines: MoneyLine[]; movers: Mover[] } {
  const lines: MoneyLine[] = [];
  const movers: Mover[] = [];
  mg.revenue.forEach((rev, i) => {
    const path = new Polyline(sampleSmooth(rev.pts));
    lines.push({ id: `revenue-${i}`, kind: "in", d: smoothPath(rev.pts), path });
    const visible = layout.hq?.offMap ? cardEdgeDistance(path, layout.hq.pin.x + size.hqCardW + size.coin / 2) : path.length;
    const gap = visible / MONEY_COINS;
    for (let k = 0; k < MONEY_COINS; k++) {
      movers.push({ id: `gold-${i}-${k}`, kind: "coin", coin: "gold", size: size.coin, path, offset: (k + 0.5) * gap, speed: COIN_SPEED, span: [0, visible] });
    }
    // Beyond the concept view the line is long, so its coins are spaced wider.
    const onward = path.length - visible;
    const far = Math.round(onward / (gap * 3));
    for (let k = 0; k < far; k++) {
      movers.push({ id: `gold-${i}-far-${k}`, kind: "coin", coin: "gold", size: size.coin, path, offset: visible + ((k + 0.5) * onward) / far, speed: COIN_SPEED, span: [visible, path.length] });
    }
  });
  if (mg.spend) {
    mg.spend.segments.forEach((seg, j) => {
      const path = new Polyline(sampleSmooth(seg));
      lines.push({ id: `spend-${j}`, kind: "out", d: smoothPath(seg), path });
      const last = j === mg.spend!.segments.length - 1;
      // The last segment's visible stretch starts at the concept view's right edge.
      const visible = last && layout.hq?.offMap ? path.length - path.project([size.mapW, seg[1][1]]) : path.length;
      const gap = Math.max(40, visible / MONEY_COINS);
      const count = Math.max(1, Math.round(path.length / gap));
      for (let k = 0; k < count; k++) {
        movers.push({ id: `blue-${j}-${k}`, kind: "coin", coin: "blue", size: size.coin, path, offset: path.length - (k + 0.5) * gap, speed: COIN_SPEED });
      }
    });
  }
  return { lines, movers };
}

/** Sea routes that carry finished devices, joined end to end (e.g. Shenzhen → Suez → Rotterdam). */
function seaLaneChains(routes: RouteDraw[]): RouteDraw[][] {
  const sea = routes.filter((r) => r.edge.mode === "sea" && r.edge.carriesTier === 4 && r.state !== "detour");
  const byFrom = new Map(sea.map((r) => [r.edge.from, r]));
  const hasPred = new Set(sea.map((r) => r.edge.to));
  const chains: RouteDraw[][] = [];
  for (const start of sea.filter((r) => !hasPred.has(r.edge.from))) {
    const chain = [start];
    let cur = start;
    while (byFrom.has(cur.edge.to) && chain.length < 20) {
      cur = byFrom.get(cur.edge.to)!;
      chain.push(cur);
    }
    chains.push(chain);
  }
  return chains;
}

/** Distance along a westward path where it first reaches x <= `edgeX`. */
export function cardEdgeDistance(path: Polyline, edgeX: number): number {
  const i = path.pts.findIndex((p) => p[0] <= edgeX);
  return i > 0 ? path.cum[i] : path.length;
}

export function buildFreeFlowScene(network: Network, layout: MapLayout, scenario: Scenario | null): Scene {
  const nodes = nodeIndex(network);
  const visibleEdges = freeFlowEdges(network, scenario);
  const routes: RouteDraw[] = [];
  for (const edge of visibleEdges) {
    const g = edgeGeometry(edge, nodes);
    if (!g) continue;
    routes.push({ id: edge.id, edge, d: g.d, state: "normal", color: tierColor[edge.carriesTier] ?? color.pillLight });
  }
  // Air arcs under sea lanes, as in the concept art.
  routes.sort((a, b) => Number(b.edge.mode === "air") - Number(a.edge.mode === "air"));

  const movers: Mover[] = [];
  const pills: MapPill[] = [];
  const captions: Caption[] = [];

  // Ships on finished-device sea lanes, evenly spaced, sailing from → to.
  for (const r of routes) {
    if (r.edge.mode !== "sea" || r.edge.carriesTier !== 4) continue;
    const path = new Polyline(sampleEdge(r.edge, nodes));
    const count = Math.max(1, Math.round(path.length / SHIP_SPACING));
    for (let i = 0; i < count; i++) {
      movers.push({ id: `ship-${r.id}-${i}`, kind: "ship", path, offset: ((i + 0.5) / count) * path.length, speed: SHIP_SPEED });
    }
  }

  // Money lines and their coins.
  const mg = moneyGeometry(network, layout);
  const { lines: money, movers: coins } = moneyCoins(mg, layout);
  movers.push(...coins);

  // Route pills.
  pills.push(...routePills(network, layout, routes, mg, null));
  if (mg.spend && layout.hq?.offMap) {
    const y = mg.spend.target[1];
    captions.push({ key: "spend-caption", text: "Payments from Apple Park, across the Pacific", x: size.mapW - 20 - 170, y: y + 60, w: 170, color: "#9CC6EE" });
  }

  return { routes, money, movers, pills, captions, visibleEdges };
}

/** Pills naming the sea lane, air freight, and the revenue line.
 * `airDetail` is null in free flow, else the air option's detail (e.g. "higher cost") during a disruption.
 */
export function routePills(network: Network, layout: MapLayout, routes: RouteDraw[], mg: MoneyGeometry, airDetail: string | null): MapPill[] {
  const disrupted = airDetail !== null;
  const nodes = nodeIndex(network);
  const pills: MapPill[] = [];

  // Sea lane: centered under the middle of the longest chain's longest leg.
  if (!disrupted) {
    for (const chain of seaLaneChains(routes)) {
      const first = nodes.get(chain[0].edge.from);
      const last = nodes.get(chain[chain.length - 1].edge.to);
      if (!first || !last) continue;
      const fromC = continentOf(first.lon, first.lat);
      const toC = continentOf(last.lon, last.lat);
      if (fromC === toC) continue;
      const text = `${fromC} TO ${toC} SEA LANE`.toUpperCase();
      const longest = chain.map((r) => new Polyline(sampleEdge(r.edge, nodes))).reduce((a, b) => (b.length > a.length ? b : a));
      const mid = longest.atFraction(0.5);
      const { w, h } = largePillBox(text);
      const near = longest.pts.filter((p) => Math.abs(p[0] - mid[0]) < w / 2 + 10);
      const lowest = Math.max(...near.map((p) => p[1]));
      const box = placeBox(spiral(mid[0] - w / 2, lowest + 23, w, h), layout);
      if (box) pills.push({ key: `lane-${chain[0].id}`, text, big: true, bg: tierColor[4], fg: color.ocean, x: box.x, y: box.y });
    }
  }

  // Air freight: beside the middle of the western-most air arc.
  const air = routes.filter((r) => r.edge.mode === "air" && r.state !== "blocked");
  if (air.length) {
    const arcs = air.map((r) => new Polyline(sampleEdge(r.edge, nodes)));
    const mids = arcs.map((a) => a.atFraction(0.5));
    const m = mids.reduce((a, b) => (b[1] > a[1] ? b : a));
    const text = disrupted ? `MORE AIR FREIGHT${airDetail ? `, AT ${airDetail}` : ""}`.toUpperCase() : "AIR FREIGHT";
    const { w, h } = smallPillBox(text);
    const box = placeBox(spiral(m[0] - 37, m[1] - 31, w, h), layout);
    if (box) pills.push({ key: "air", text, big: false, bg: tierColor[4], fg: color.ocean, x: box.x, y: box.y });
  }

  // Revenue line.
  if (!disrupted && mg.revenue.length && layout.hq) {
    const text = "REVENUE TO APPLE PARK";
    const { w, h } = smallPillBox(text);
    const hub = mg.revenue[0].hub;
    const box = placeBox(
      spiral((layout.hq.offMap ? layout.hq.pin.anchor : layout.hq.anchor)[0] + 80, hub[1] + 86, w, h),
      layout,
    );
    if (box) pills.push({ key: "revenue", text, big: false, bg: color.moneyIn, fg: color.ocean, x: box.x, y: box.y });
  }
  return pills;
}
