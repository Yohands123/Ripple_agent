// The map during a dropped disruption, built only from the network and the scenario file.

import { project, type Pt } from "./geo";
import { largePillBox, symbolSize, placeBox, smallPillBox, spiral, type MapLayout } from "./layout";
import { Polyline, sampleSmooth } from "./polyline";
import { laneLabel, trimOverlaps, type Band } from "./declutter";
import { lineGeometry } from "./georoute";
import { edgeLonLat, edgeRank, isRoute, nodeIndex } from "./routes";
import {
  cardEdgeDistance,
  COIN_SPEED,
  drawRoutes,
  edgeColor,
  laneShips,
  longestOf,
  moneyCoins,
  moneyGeometry,
  revenuePaths,
  routePills,
  type Caption,
  type Marker,
  type MapPill,
  type MoneyLine,
  type Mover,
  type RouteDraw,
  type RouteState,
  type Scene,
} from "./scene";
import { color, size, tierColor } from "./tokens";
import type { Network, NetworkEdge, Scenario } from "./types";

const ZONE_DIAMETER = 92;
const QUEUE_SHIPS = 5;
const QUEUE_GAP = 18;
/** Coins drawn for revenue at risk when the scenario gives no amount yet. */
const DEFAULT_AT_RISK_COINS = 8;
const MAX_AT_RISK_COINS = 10;
const FALL_DISTANCE = 96;
const FALL_SPEED = 16;

const key = ([lon, lat]: Pt) => `${lon.toFixed(2)},${lat.toFixed(2)}`;

/**
 * A detour is drawn only where it leaves the normal lanes: leading and trailing
 * waypoints shared with other sea routes are trimmed, keeping the branch points.
 */
export function trimmedDetour(edge: NetworkEdge, network: Network): Pt[] | null {
  // Returns lon/lat points.
  const nodes = nodeIndex(network);
  const ll = edgeLonLat(edge, nodes);
  if (!ll) return null;
  const shared = new Set<string>();
  for (const other of network.edges) {
    // Only the normal lanes count: other detours may run the same way round.
    if (other.id === edge.id || other.mode !== "sea" || other.alternativeTo || other.detourOnly) continue;
    for (const p of edgeLonLat(other, nodes) ?? []) shared.add(key(p));
  }
  let start = 0;
  while (start + 1 < ll.length && shared.has(key(ll[start])) && shared.has(key(ll[start + 1]))) start++;
  let end = ll.length - 1;
  while (end - 1 > start && shared.has(key(ll[end])) && shared.has(key(ll[end - 1]))) end--;
  return ll.slice(start, end + 1);
}

/** The water ships wait in before the shock: the previous chokepoint on the lane, or where the lane starts. */
function upstreamWater(edge: NetworkEdge, network: Network, shockIds: Set<string>): string | null {
  const nodes = nodeIndex(network);
  const ids = edge.viaNodeIds ?? [];
  const i = ids.findIndex((id) => shockIds.has(id));
  const before = i > 0 ? nodes.get(ids[i - 1]) : undefined;
  if (before) return before.kind === "chokepoint" && /mandeb/i.test(before.name) ? "Red Sea" : before.region || before.name;
  // Older files: the last canal or port the lane passes before the shock, or the chokepoint it starts at.
  const via = (edge.via ?? []).map(key);
  const upstream = network.nodes.filter((n) => (n.kind === "canal" || n.kind === "port") && via.includes(key([n.lon, n.lat])));
  if (upstream.length) {
    return upstream.reduce((a, b) => (via.lastIndexOf(key([b.lon, b.lat])) > via.lastIndexOf(key([a.lon, a.lat])) ? b : a)).region;
  }
  const from = nodes.get(edge.from);
  return from?.kind === "canal" ? from.region : null;
}

function optionMatching(scenario: Scenario, re: RegExp) {
  return scenario.options.find((o) => re.test(o.id) || re.test(o.label));
}

/**
 * How many revenue coins are at risk, and how they split into delayed and lost.
 * None when the data says revenue at risk or the delayed share is unknown (null).
 */
export function atRiskCoins(scenario: Scenario): { delayed: number; lost: number } {
  const { revenueAtRisk, delayedShare } = scenario.money;
  if (revenueAtRisk == null || delayedShare == null) return { delayed: 0, lost: 0 };
  const [lo, hi] = revenueAtRisk;
  const mid = (lo + hi) / 2;
  const n =
    mid > 0 && scenario.money.coinUsd > 0
      ? Math.min(MAX_AT_RISK_COINS, Math.max(1, Math.round(mid / scenario.money.coinUsd)))
      : DEFAULT_AT_RISK_COINS;
  const delayed = Math.round(n * Math.min(1, Math.max(0, delayedShare)));
  return { delayed, lost: n - delayed };
}

/**
 * `progress` (0..1] is how far the disruption has built up: the queue grows and
 * revenue coins turn delayed or lost as it advances. `showActual` adds actual
 * outcomes (known only once the event is over).
 */
export function buildDisruptionScene(
  network: Network,
  layout: MapLayout,
  scenario: Scenario,
  progress = 1,
  showActual = false,
  band: Band = "world",
  showRoads = band === "country",
): Scene {
  const p = Math.min(1, Math.max(0, progress));
  const nodes = nodeIndex(network);
  const shockIds = new Set(scenario.shock.nodeIds);
  const { blocked, detour, expedited } = scenario.affectedRoutes;
  const stateOf = (id: string): RouteState =>
    blocked.includes(id) ? "blocked" : detour.includes(id) ? "detour" : expedited.includes(id) ? "expedited" : "normal";

  // Routes: open lanes, closed lanes greyed, detours drawn only where they leave the lanes.
  const detourIds = new Set(detour);
  const base = network.edges.filter((e) => isRoute(e) && !detourIds.has(e.id) && !e.detourOnly && !e.alternativeTo);
  const routes: RouteDraw[] = drawRoutes(base, nodes, band, stateOf, showRoads);
  // Detours that run the same way round are drawn once.
  const detourLines = network.edges
    .filter((e) => detourIds.has(e.id))
    .map((edge) => ({ edge, ll: trimmedDetour(edge, network) }))
    .filter((x): x is { edge: NetworkEdge; ll: Pt[] } => Boolean(x.ll && x.ll.length > 1))
    .map((x) => ({ edge: x.edge, lonlat: lineGeometry(x.ll, "smooth").lonlat }))
    .sort((a, b) => b.lonlat.length - a.lonlat.length);
  trimOverlaps(detourLines.map((x) => ({ id: x.edge.id, lonlat: x.lonlat }))).forEach((g, i) => {
    const edge = detourLines[i].edge;
    if (g.d) routes.push({ id: edge.id, edge, d: g.d, pieces: g.pieces, state: "detour", color: edgeColor(edge), rank: edgeRank(edge) });
  });
  const paths = new Map<string, Polyline[]>(routes.map((r) => [r.id, r.pieces.map((p) => new Polyline(p))]));

  // Shock zones.
  const zones = scenario.shock.nodeIds
    .map((id) => nodes.get(id))
    .filter((n) => n !== undefined)
    .map((n) => {
      const [x, y] = layout.points.get(n.id)!;
      return { key: n.id, x, y, d: ZONE_DIAMETER };
    });
  // Shocks that are not a node in the network carry a location instead.
  const loc = scenario.shock.location;
  if (zones.length === 0 && loc) {
    const [x, y] = project(loc.lon, loc.lat);
    zones.push({ key: "shock-location", x, y, d: ZONE_DIAMETER });
  }
  for (const z of zones) layout.taken.push({ x: z.x - z.d / 2, y: z.y - z.d / 2, w: z.d, h: z.d });

  // Ships: moving on open lanes, stopped and faded on closed ones, fewer on detours.
  const movers: Mover[] = [
    ...laneShips(routes.filter((r) => r.state === "normal" || r.state === "expedited"), band),
    ...laneShips(routes.filter((r) => r.state === "blocked"), band, { speed: 0, opacity: 0.35 }),
    // Fewer ships take the long way round.
    ...laneShips(routes.filter((r) => r.state === "detour"), band, { gapFactor: 3 }),
  ];
  const pills: MapPill[] = [];

  // Ships bunch up before the blockage on the first lane into (or through) the shock.
  let queuedUpstream: string | null = null;
  const zone = zones[0];
  const queueLane = zone
    ? routes.find((r) => r.edge.mode === "sea" && (shockIds.has(r.edge.to) || (r.edge.viaNodeIds ?? []).some((id) => shockIds.has(id))))
    : undefined;
  if (zone && queueLane) {
    const full = paths.get(queueLane.id) ?? [];
    // The stretch of lane nearest the shock, and the distance along it where the shock is.
    let best: { path: Polyline; at: number; d: number } | null = null;
    for (const path of full) {
      const at = path.project([zone.x, zone.y]);
      const [x, y] = path.at(at);
      const d = Math.hypot(x - zone.x, y - zone.y);
      if (!best || d < best.d) best = { path, at, d };
    }
    if (best && best.d < ZONE_DIAMETER) {
      const queued = Math.max(1, Math.ceil(QUEUE_SHIPS * p));
      for (let k = 1; k <= queued; k++) {
        const [x, y] = best.path.at(best.at - k * QUEUE_GAP);
        const at: Pt = [x + (k % 2 === 0 ? 9 : -6), y];
        movers.push({ id: `queue-${queueLane.id}-${k}`, kind: "ship", path: new Polyline([at, at]), offset: 0, speed: 0, enter: "enter-coins" });
      }
      const end = best.path.at(best.at);
      movers.push({ id: `blocked-ship-${queueLane.id}`, kind: "ship", path: new Polyline([[end[0], end[1] + 4], [end[0], end[1] + 4]]), offset: 0, speed: 0, rotate: 58 });
      queuedUpstream = upstreamWater(queueLane.edge, network, shockIds);
    }
  }

  // Money: spend continues; revenue coins split into one on time, delayed, and lost.
  const money: MoneyLine[] = [];
  const mg = moneyGeometry(network, layout);
  const full = atRiskCoins(scenario);
  const risk = { delayed: Math.round(full.delayed * p), lost: Math.round(full.lost * p) };
  mg.revenue.forEach((rev, i) => {
    const { d, paths: revPaths } = revenuePaths(rev);
    const path = revPaths[0];
    if (!path) return;
    revPaths.forEach((pp, j) => money.push({ id: j === 0 ? `revenue-${i}` : `revenue-${i}-${j}`, kind: "in", d: j === 0 ? d : "", path: pp }));
    // Revenue still arriving: one coin on the stretch before the pinned card.
    const end = layout.hq?.offMap ? cardEdgeDistance(path, layout.hq.pin.x + size.hqCardW + size.coin / 2) : path.length;
    movers.push({ id: `gold-${i}`, kind: "coin", coin: "gold", size: size.coin, path, offset: end * 0.9, speed: COIN_SPEED, span: [end * 0.45, end] });

    if (i > 0) return;
    const hub = rev.hub;
    const stackX = hub[0] + 23;
    for (let k = 0; k < risk.delayed; k++) {
      const at: Pt = [stackX, hub[1] + 34 - k * size.delayedOffset];
      movers.push({ id: `grey-${k}`, kind: "coin", coin: "grey", size: size.coin, path: new Polyline([at, at]), offset: 0, speed: 0, enter: "enter-coins" });
    }
    if (risk.delayed > 0) {
      const text = "DELAYED";
      const { w, h } = smallPillBox(text);
      const top = hub[1] + 34 - (risk.delayed - 1) * size.delayedOffset - size.coin / 2;
      const box = placeBox(spiral(stackX + 16, top - 5, w, h, 80), layout);
      if (box) pills.push({ key: "delayed", text, big: false, bg: color.textSecondary, fg: color.ocean, x: box.x, y: box.y });
    }
    // Lost coins fall from the visible stretch of the line (before the pinned Apple Park card).
    const from = path.at(end * 0.4);
    const fall = new Polyline(sampleSmooth([from, [from[0] - 8, from[1] + FALL_DISTANCE * 0.33], [from[0] + 6, from[1] + FALL_DISTANCE * 0.66], [from[0] - 6, from[1] + FALL_DISTANCE]]));
    for (let k = 0; k < risk.lost; k++) {
      const turn = [0, 25, -30, 40][k % 4] || 30;
      movers.push({
        id: `red-${k}`,
        kind: "coin",
        coin: "red",
        size: size.coin,
        path: fall,
        offset: (k / Math.max(1, risk.lost)) * fall.length,
        speed: FALL_SPEED,
        fall: true,
        rotate: turn,
        enter: "enter-coins",
      });
    }
    if (risk.lost > 0) {
      const text = "LOST";
      const { w, h } = smallPillBox(text);
      const box = placeBox(spiral(from[0] + 20, from[1] + FALL_DISTANCE * 0.8, w, h, 80), layout, { ignoreRoutes: true });
      if (box) pills.push({ key: "lost", text, big: false, bg: color.alert, fg: "#FFFFFF", x: box.x, y: box.y });
    }
  });
  if (mg.spend) {
    // Spend keeps flowing during a disruption.
    const spendOnly = moneyCoins({ revenue: [], spend: mg.spend }, layout);
    money.push(...spendOnly.lines);
    movers.push(...spendOnly.movers);
  }

  // Pills: the shock, the queue, the detour, air freight.
  for (const z of zones) {
    const text = scenario.title.toUpperCase();
    const { w, h } = largePillBox(text);
    const box = placeBox(spiral(z.x + 36, z.y - 26, w, h, 120), layout, { ignoreRoutes: true });
    if (box) pills.push({ key: `shock-${z.key}`, text, big: true, bg: color.alert, fg: "#FFFFFF", x: box.x, y: box.y });
    if (queuedUpstream) {
      const qText = `SHIPS QUEUED IN THE ${queuedUpstream}`.toUpperCase();
      const q = smallPillBox(qText);
      const qb = placeBox(spiral(z.x + 38, z.y + 20, q.w, q.h, 120), layout, { ignoreRoutes: true });
      if (qb) pills.push({ key: `queue-${z.key}`, text: qText, big: false, bg: color.pillLight, fg: color.ocean, x: qb.x, y: qb.y });
    }
  }
  const detourOpt = optionMatching(scenario, /detour/i);
  const detourRoute = routes.find((r) => r.state === "detour");
  // A short option note reads well on the map ("+10 to 14 days"); a long one is left to the panel and the lane's name is used.
  const short = (t: string | undefined) => (t && t.length <= 32 ? t : undefined);
  const detourText =
    detourOpt && short(detourOpt.detail)
      ? `${detourOpt.label}: ${detourOpt.detail}`
      : detourRoute && (laneLabel(detourRoute.edge) ?? detourRoute.edge.label ?? (detourOpt ? detourOpt.label : undefined));
  if (detourText && detourRoute) {
    const text = detourText.toUpperCase();
    const { w, h } = largePillBox(text);
    const at = (longestOf(paths.get(detourRoute.id)!) ?? new Polyline([[0, 0]])).atFraction(0.3);
    const box = placeBox(spiral(at[0] + 10, at[1] + 40, w, h, 160), layout, { ignoreRoutes: true, anchor: at });
    if (box) pills.push({ key: "detour", text, big: true, bg: tierColor[4], fg: color.ocean, x: box.x, y: box.y });
  }
  const airOpt = optionMatching(scenario, /air/i);
  pills.push(...routePills(network, layout, routes, mg, short(airOpt?.detail) ?? ""));

  // Regional groups with predicted hits run low on stock.
  const groupText: Record<string, string> = {};
  const hitIds = new Set(scenario.predictions.filter((pr) => pr.pHit >= 0.5).map((pr) => pr.nodeId));
  for (const g of layout.groups) {
    if (g.nodeIds.some((id) => hitIds.has(id))) groupText[g.key] = `${g.key.toUpperCase()}: STOCK RUNNING LOW`;
  }

  const captions: Caption[] = [];
  if (mg.spend && layout.hq?.offMap) {
    const spot = placeBox(spiral(size.mapW - 20 - 170, mg.spend.target[1] + 60, 170, 30, 120), layout, { ignoreRoutes: true });
    if (spot) captions.push({ key: "spend-caption", text: "Payments from Apple Park, across the Pacific", x: spot.x, y: spot.y, w: 170, color: "#9CC6EE" });
  }

  // Predicted hits (rings) and, once the event is over, actual outcomes.
  const markers: Marker[] = [];
  for (const pr of scenario.predictions) {
    const at = layout.points.get(pr.nodeId);
    const n = nodes.get(pr.nodeId);
    if (!at || !n || pr.pHit < 0.5) continue;
    markers.push({ key: `pred-${pr.nodeId}`, kind: "predicted", x: at[0], y: at[1], r: symbolSize(n.kind) / 2 + 6, low: pr.lowConfidence });
  }
  if (showActual) {
    for (const a of scenario.actual) {
      const at = layout.points.get(a.nodeId);
      const n = nodes.get(a.nodeId);
      if (!at || !n) continue;
      markers.push({ key: `actual-${a.nodeId}`, kind: a.hit ? "actual-hit" : "actual-miss", x: at[0], y: at[1], r: symbolSize(n.kind) / 2 + 6, low: false });
    }
  }

  const visibleEdges = routes.map((r) => r.edge);
  return { zones, groupText, routes, money, movers, pills, captions, visibleEdges, markers };
}
