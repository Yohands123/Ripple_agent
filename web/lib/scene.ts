// Everything drawn on the map for one state (free flow or a dropped disruption),
// derived only from the network, the scenario file, and the layout.

import { airBundles, airLimit, chainLabel, laneLabel, shipCounts, trimOverlaps, type Band } from "./declutter";
import { DATELINE_EAST, DATELINE_WEST, type Pt } from "./geo";
import { lineGeometry } from "./georoute";
import { continentOf, largePillBox, placeBox, smallPillBox, spiral, type MapLayout } from "./layout";
import { Polyline, sampleSmooth } from "./polyline";
import { edgeLine, edgePieces, edgeRank, isRoute, nodeIndex, smoothPath, type EdgeRank } from "./routes";
import { color, route as R, size, tierColor, type CoinKind } from "./tokens";
import type { Network, NetworkEdge, NetworkNode, Scenario } from "./types";

export type RouteState = "normal" | "blocked" | "detour" | "expedited";

export interface RouteDraw {
  id: string;
  edge: NetworkEdge;
  /** Path data as drawn (parts shared with an earlier lane are left out). */
  d: string;
  /** What is drawn, in map pixels, one polyline per run. */
  pieces: Pt[][];
  state: RouteState;
  color: string;
  /** Backbone at full strength; other inferred routes and supplier links fainter. */
  rank: EdgeRank;
  /** Stroke width override (air bundles grow with the routes they stand for). */
  width?: number;
  /** Routes an air bundle stands for. */
  count?: number;
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

/** Line color for an edge: the tier it carries, or plain light when that is unknown. */
export const edgeColor = (e: NetworkEdge) => (e.carriesTier != null ? tierColor[e.carriesTier] : undefined) ?? color.pillLight;

/** An edge as polylines in map pixels, one per side of the antimeridian. */
export function edgePolylines(edge: NetworkEdge, nodes: Map<string, NetworkNode>): Polyline[] {
  return edgePieces(edge, nodes).map((p) => new Polyline(p));
}

export const longestOf = (lines: Polyline[]) => lines.reduce<Polyline | null>((a, b) => (!a || b.length > a.length ? b : a), null);

/** Edges drawn in free flow: routes only, except those that exist only as a scenario's detour or alternative. */
export function freeFlowEdges(network: Network, scenario: Scenario | null): NetworkEdge[] {
  const detourOnly = new Set(scenario?.affectedRoutes.detour ?? []);
  return network.edges.filter((e) => isRoute(e) && !detourOnly.has(e.id) && !e.detourOnly && !e.alternativeTo);
}


/**
 * The routes drawn at a zoom band, in drawing order: lanes trimmed where they share
 * water, then air bundles (top five at world zoom). `stateOf` marks disruption states.
 */
export function drawRoutes(
  edges: NetworkEdge[],
  nodes: Map<string, NetworkNode>,
  band: Band,
  stateOf: (id: string) => RouteState = () => "normal",
  showRoads = band === "country",
): RouteDraw[] {
  // Road links are drawn only when zoomed into a country or switched on (a selected node's are drawn separately).
  const shown = edges.filter((e) => e.mode !== "road" || showRoads);
  const lanes = shown.filter((e) => e.mode !== "air");
  const order: RouteState[] = ["normal", "expedited", "blocked", "detour"];
  const rankOrder: EdgeRank[] = ["backbone", "inferred", "supplier", "context"];
  const lengthOf = (e: NetworkEdge) => edgeLine(e, nodes)?.lonlat.length ?? 0;
  // Most important first: open lanes before closed ones, backbone before the rest, longest first.
  lanes.sort(
    (a, b) =>
      order.indexOf(stateOf(a.id)) - order.indexOf(stateOf(b.id)) ||
      rankOrder.indexOf(edgeRank(a)) - rankOrder.indexOf(edgeRank(b)) ||
      lengthOf(b) - lengthOf(a),
  );
  const geo = lanes.map((e) => ({ e, line: edgeLine(e, nodes) })).filter((x) => x.line);
  const drawn = trimOverlaps(geo.map((x) => ({ id: x.e.id, lonlat: x.line!.lonlat })));
  const routes: RouteDraw[] = [];
  drawn.forEach((d, i) => {
    const e = geo[i].e;
    if (!d.d) return;
    routes.push({ id: e.id, edge: e, d: d.d, pieces: d.pieces, state: stateOf(e.id), color: edgeColor(e), rank: edgeRank(e) });
  });

  // Air: one arc per origin and destination region.
  const bundles = airBundles(
    shown.filter((e) => e.mode === "air"),
    nodes,
  );
  // Expedited and blocked bundles always show during a disruption.
  const important = (ids: NetworkEdge[]) => ids.some((x) => stateOf(x.id) !== "normal");
  const limit = airLimit(band);
  const air: RouteDraw[] = [];
  bundles.forEach((b, i) => {
    if (i >= limit && !important(b.edges)) return;
    const line = edgeLine(b.edge, nodes);
    if (!line) return;
    const states = b.edges.map((x) => stateOf(x.id));
    const state = states.includes("expedited") ? "expedited" : states.every((s) => s === "blocked") ? "blocked" : "normal";
    air.push({
      id: `air-${b.key}`,
      edge: b.edge,
      d: line.d,
      pieces: line.pieces,
      state,
      color: edgeColor(b.edge),
      rank: edgeRank(b.edge),
      width: (state === "expedited" ? R.airWidthExpedited : R.airWidth) + 0.7 * (b.count - 1),
      count: b.count,
    });
  });
  // Air arcs under sea lanes, as in the concept art.
  return [...air, ...routes];
}

/** Where revenue leaves each regional sales group: its nearest shipping node, or the group's first node. */
function salesHubs(network: Network, layout: MapLayout): NetworkNode[] {
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
    return best ?? members[0];
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
  /** Each revenue line in travel order: the concept shape (`pts`, smoothed in map px) or a globe line (`pieces`). */
  revenue: { pts?: Pt[]; pieces?: Pt[][]; d?: string; hub: Pt }[];
  /** Spend is one or two segments (split where it crosses the antimeridian), in travel order. */
  spend: { segments: Pt[][]; target: Pt } | null;
}

/**
 * Money lines: revenue from each sales region to Apple Park, spend from Apple Park to
 * the assembly nearest the Pacific. Revenue from Europe and Africa keeps the concept
 * art's shape to the pinned card; revenue from Asia crosses the Pacific, and from the
 * Americas it goes straight there.
 */
export function moneyGeometry(network: Network, layout: MapLayout): MoneyGeometry {
  if (!layout.hq) return { revenue: [], spend: null };
  const hq = layout.hq;
  const hqNode = network.nodes.find((n) => n.kind === "hq");
  const revenue: MoneyGeometry["revenue"] = salesHubs(network, layout).map((hub) => {
    const at = layout.points.get(hub.id)!;
    const c = continentOf(hub.lon, hub.lat);
    if (hqNode && (c === "Asia" || c === "Australia" || c === "North America" || c === "South America")) {
      const g = lineGeometry([[hub.lon, hub.lat], [hqNode.lon, hqNode.lat]], "arc");
      return { hub: at, pieces: g.pieces, d: g.d };
    }
    return { hub: at, pts: revenueToHq(at, hq) };
  });
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

/** A revenue line's polylines and path data, in travel order. */
export function revenuePaths(rev: MoneyGeometry["revenue"][number]): { d: string; paths: Polyline[] } {
  if (rev.pts) return { d: smoothPath(rev.pts), paths: [new Polyline(sampleSmooth(rev.pts))] };
  return { d: rev.d ?? "", paths: (rev.pieces ?? []).map((p) => new Polyline(p)) };
}

/**
 * Coins along money lines, spaced so the concept view shows the same three coins
 * per line; the rest travel on beyond it (behind the pinned card or off the edge).
 */
export function moneyCoins(mg: MoneyGeometry, layout: MapLayout): { lines: MoneyLine[]; movers: Mover[] } {
  const lines: MoneyLine[] = [];
  const movers: Mover[] = [];
  mg.revenue.forEach((rev, i) => {
    const { d, paths } = revenuePaths(rev);
    paths.forEach((path, j) => {
      const id = j === 0 ? `revenue-${i}` : `revenue-${i}-${j}`;
      lines.push({ id, kind: "in", d: j === 0 ? d : "", path });
      const concept = Boolean(rev.pts);
      const visible = concept && layout.hq?.offMap ? cardEdgeDistance(path, layout.hq.pin.x + size.hqCardW + size.coin / 2) : path.length;
      const gap = concept ? visible / MONEY_COINS : Math.max(80, path.length / MONEY_COINS);
      const n = concept ? MONEY_COINS : Math.max(1, Math.round(path.length / gap));
      for (let k = 0; k < n; k++) {
        movers.push({ id: `gold-${i}-${j}-${k}`, kind: "coin", coin: "gold", size: size.coin, path, offset: (k + 0.5) * (visible / n), speed: COIN_SPEED, span: [0, visible] });
      }
      // Beyond the concept view the line is long, so its coins are spaced wider.
      const onward = path.length - visible;
      const far = concept ? Math.round(onward / (gap * 3)) : 0;
      for (let k = 0; k < far; k++) {
        movers.push({ id: `gold-${i}-far-${k}`, kind: "coin", coin: "gold", size: size.coin, path, offset: visible + ((k + 0.5) * onward) / far, speed: COIN_SPEED, span: [visible, path.length] });
      }
    });
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

/** Sea routes joined end to end (e.g. Shenzhen → Suez → Rotterdam). */
function laneChains(routes: RouteDraw[]): RouteDraw[][] {
  const byFrom = new Map(routes.map((r) => [r.edge.from, r]));
  const hasPred = new Set(routes.map((r) => r.edge.to));
  const chains: RouteDraw[][] = [];
  for (const start of routes.filter((r) => !hasPred.has(r.edge.from))) {
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

/** Ships on the drawn parts of finished-device sea lanes: one per 200 screen px, about 20 in view. */
export function laneShips(routes: RouteDraw[], band: Band, opts: { speed?: number; opacity?: number; gapFactor?: number } = {}): Mover[] {
  const pieces = routes
    .filter((r) => r.edge.mode === "sea" && (r.edge.carriesTier === 4 || r.edge.carriesTier == null))
    .flatMap((r) => r.pieces.map((p, j) => ({ id: `${r.id}-${j}`, path: new Polyline(p) })));
  const counts = shipCounts(
    pieces.map((p) => p.path.length / (opts.gapFactor ?? 1)),
    band,
  );
  const movers: Mover[] = [];
  pieces.forEach(({ id, path }, i) => {
    const n = counts[i];
    for (let k = 0; k < n; k++) {
      movers.push({ id: `ship-${id}-${k}`, kind: "ship", path, offset: ((k + 0.5) / n) * path.length, speed: opts.speed ?? SHIP_SPEED, opacity: opts.opacity });
    }
  });
  return movers;
}

export function buildFreeFlowScene(network: Network, layout: MapLayout, scenario: Scenario | null, band: Band = "world", showRoads = band === "country"): Scene {
  const nodes = nodeIndex(network);
  const visibleEdges = freeFlowEdges(network, scenario);
  const routes = drawRoutes(visibleEdges, nodes, band, undefined, showRoads);

  const movers: Mover[] = laneShips(routes, band);
  const pills: MapPill[] = [];
  const captions: Caption[] = [];

  // Money lines and their coins.
  const mg = moneyGeometry(network, layout);
  const { lines: money, movers: coins } = moneyCoins(mg, layout);
  movers.push(...coins);

  if (mg.spend && layout.hq?.offMap) {
    const y = mg.spend.target[1];
    // The caption is a label too: placed clear of others, and nothing else may sit on it.
    const spot = placeBox(spiral(size.mapW - 20 - 170, y + 60, 170, 30, 120), layout, { ignoreRoutes: true });
    if (spot) captions.push({ key: "spend-caption", text: "Payments from Apple Park, across the Pacific", x: spot.x, y: spot.y, w: 170, color: "#9CC6EE" });
  }
  pills.push(...routePills(network, layout, routes, mg, null));

  return { routes, money, movers, pills, captions, visibleEdges: routes.map((r) => r.edge) };
}

/** Pills naming each sea lane, air freight, and the revenue line.
 * `airDetail` is null in free flow, else the air option's detail (e.g. "higher cost") during a disruption.
 */
export function routePills(network: Network, layout: MapLayout, routes: RouteDraw[], mg: MoneyGeometry, airDetail: string | null): MapPill[] {
  const disrupted = airDetail !== null;
  const nodes = nodeIndex(network);
  const pills: MapPill[] = [];

  // One label per sea lane, under the middle of its longest drawn stretch.
  if (!disrupted) {
    const byName = new Map<string, Polyline[]>();
    const add = (name: string | null, rs: RouteDraw[]) => {
      if (name) byName.set(name, [...(byName.get(name) ?? []), ...rs.flatMap((r) => r.pieces.map((p) => new Polyline(p)))]);
    };
    const lanes0 = routes.filter((r) => r.edge.mode === "sea" && r.state === "normal" && r.rank !== "supplier" && r.rank !== "context");
    for (const r of lanes0) add(laneLabel(r.edge), [r]);
    // Lanes without names: chains joined end to end are named by the continents at their ends.
    for (const chain of laneChains(lanes0.filter((r) => !laneLabel(r.edge)))) add(chainLabel(chain.map((r) => r.edge), nodes), chain);
    // Longest lanes are labelled first, so they win any collision.
    const lanes = [...byName.entries()].map(([text, lines]) => ({ text, longest: longestOf(lines)! })).sort((a, b) => b.longest.length - a.longest.length);
    for (const [i, { text, longest }] of lanes.entries()) {
      if (longest.length < 120) continue;
      const mid = longest.atFraction(0.5);
      // The two main lanes get the concept art's large pill; feeders a small one.
      const big = i < 2;
      const { w, h } = big ? largePillBox(text) : smallPillBox(text);
      const near = longest.pts.filter((p) => Math.abs(p[0] - mid[0]) < w / 2 + 10);
      const lowest = Math.max(...near.map((p) => p[1]));
      const box = placeBox(spiral(mid[0] - w / 2, lowest + 23, w, h), layout, { anchor: mid });
      if (box) pills.push({ key: `lane-${text}`, text, big, bg: tierColor[4], fg: color.ocean, x: box.x, y: box.y });
    }
  }

  // Air freight: beside the middle of the western-most air arc.
  const air = routes.filter((r) => r.edge.mode === "air" && r.state !== "blocked");
  if (air.length) {
    const arcs = air.map((r) => longestOf(r.pieces.map((p) => new Polyline(p)))).filter((p): p is Polyline => p !== null);
    const mids = arcs.map((a) => a.atFraction(0.5));
    const m = mids.reduce((a, b) => (b[1] > a[1] ? b : a));
    const text = disrupted ? `MORE AIR FREIGHT${airDetail ? `, AT ${airDetail}` : ""}`.toUpperCase() : "AIR FREIGHT";
    const { w, h } = smallPillBox(text);
    const box = placeBox(spiral(m[0] - 37, m[1] - 31, w, h), layout, { anchor: m });
    if (box) pills.push({ key: "air", text, big: false, bg: tierColor[4], fg: color.ocean, x: box.x, y: box.y });
  }

  // Revenue line.
  const concept = mg.revenue.find((r) => r.pts);
  if (!disrupted && concept && layout.hq) {
    const text = "REVENUE TO APPLE PARK";
    const { w, h } = smallPillBox(text);
    const hub = concept.hub;
    const box = placeBox(spiral((layout.hq.offMap ? layout.hq.pin.anchor : layout.hq.anchor)[0] + 80, hub[1] + 86, w, h), layout);
    if (box) pills.push({ key: "revenue", text, big: false, bg: color.moneyIn, fg: color.ocean, x: box.x, y: box.y });
  }
  return pills;
}
