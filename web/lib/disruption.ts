// The map during a dropped disruption, built only from the network and the scenario file.

import { project, type Pt } from "./geo";
import { largePillBox, symbolSize, placeBox, smallPillBox, spiral, type MapLayout } from "./layout";
import { Polyline, sampleSmooth } from "./polyline";
import { edgeGeometry, edgeLonLat, nodeIndex, sampleEdge, smoothPath } from "./routes";
import {
  cardEdgeDistance,
  COIN_SPEED,
  moneyGeometry,
  routePills,
  SHIP_SPACING,
  SHIP_SPEED,
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
  const nodes = nodeIndex(network);
  const ll = edgeLonLat(edge, nodes);
  if (!ll) return null;
  const shared = new Set<string>();
  for (const other of network.edges) {
    if (other.id === edge.id || other.mode !== "sea") continue;
    for (const p of edgeLonLat(other, nodes) ?? []) shared.add(key(p));
  }
  let start = 0;
  while (start + 1 < ll.length && shared.has(key(ll[start])) && shared.has(key(ll[start + 1]))) start++;
  let end = ll.length - 1;
  while (end - 1 > start && shared.has(key(ll[end])) && shared.has(key(ll[end - 1]))) end--;
  return ll.slice(start, end + 1).map(([lon, lat]) => project(lon, lat));
}

function optionMatching(scenario: Scenario, re: RegExp) {
  return scenario.options.find((o) => re.test(o.id) || re.test(o.label));
}

/** How many revenue coins are at risk, and how they split into delayed and lost. */
export function atRiskCoins(scenario: Scenario): { delayed: number; lost: number } {
  const [lo, hi] = scenario.money.revenueAtRisk;
  const mid = (lo + hi) / 2;
  const n =
    mid > 0 && scenario.money.coinUsd > 0
      ? Math.min(MAX_AT_RISK_COINS, Math.max(1, Math.round(mid / scenario.money.coinUsd)))
      : DEFAULT_AT_RISK_COINS;
  const delayed = Math.round(n * Math.min(1, Math.max(0, scenario.money.delayedShare)));
  return { delayed, lost: n - delayed };
}

/**
 * `progress` (0..1] is how far through the event the replay is: the queue builds
 * and revenue coins turn delayed or lost as it advances.
 */
export function buildDisruptionScene(network: Network, layout: MapLayout, scenario: Scenario, progress = 0.5): Scene {
  const p = Math.min(1, Math.max(0, progress));
  const nodes = nodeIndex(network);
  const shockIds = new Set(scenario.shock.nodeIds);
  const { blocked, detour, expedited } = scenario.affectedRoutes;
  const stateOf = (id: string): RouteState =>
    blocked.includes(id) ? "blocked" : detour.includes(id) ? "detour" : expedited.includes(id) ? "expedited" : "normal";

  // Routes.
  const routes: RouteDraw[] = [];
  const paths = new Map<string, Polyline>();
  for (const edge of network.edges) {
    const state = stateOf(edge.id);
    const tint = tierColor[edge.carriesTier] ?? color.pillLight;
    if (state === "detour") {
      const pts = trimmedDetour(edge, network);
      if (!pts || pts.length < 2) continue;
      routes.push({ id: edge.id, edge, d: smoothPath(pts), state, color: tint });
      paths.set(edge.id, new Polyline(sampleSmooth(pts)));
      continue;
    }
    const g = edgeGeometry(edge, nodes);
    if (!g) continue;
    routes.push({ id: edge.id, edge, d: g.d, state, color: tint });
    paths.set(edge.id, new Polyline(sampleEdge(edge, nodes)));
  }
  routes.sort((a, b) => Number(b.edge.mode === "air") - Number(a.edge.mode === "air"));

  // Shock zones.
  const zones = scenario.shock.nodeIds
    .map((id) => nodes.get(id))
    .filter((n) => n !== undefined)
    .map((n) => {
      const [x, y] = layout.points.get(n.id)!;
      return { key: n.id, x, y, d: ZONE_DIAMETER };
    });
  for (const z of zones) layout.taken.push({ x: z.x - z.d / 2, y: z.y - z.d / 2, w: z.d, h: z.d });

  // Ships.
  const movers: Mover[] = [];
  const pills: MapPill[] = [];
  let queuedUpstream: string | null = null;
  for (const r of routes) {
    if (r.edge.mode !== "sea" || r.edge.carriesTier !== 4 || r.state === "detour") continue;
    const path = paths.get(r.id)!;
    const count = Math.max(1, Math.round(path.length / SHIP_SPACING));
    if (r.state === "blocked") {
      for (let i = 0; i < count; i++) {
        movers.push({ id: `ship-${r.id}-${i}`, kind: "ship", path, offset: ((i + 0.5) / count) * path.length, speed: 0, opacity: 0.35 });
      }
      continue;
    }
    const intoShock = shockIds.has(r.edge.to);
    const queueLen = intoShock ? (QUEUE_SHIPS + 1) * QUEUE_GAP : 0;
    const travel = path.length - queueLen;
    for (let i = 0; i < count; i++) {
      movers.push({
        id: `ship-${r.id}-${i}`,
        kind: "ship",
        path,
        offset: ((i + 0.5) / count) * travel,
        speed: SHIP_SPEED,
        span: [0, travel],
      });
    }
    if (intoShock) {
      // Ships bunch up before the blockage; the blocked ship lies across the chokepoint.
      const queued = Math.max(1, Math.ceil(QUEUE_SHIPS * p));
      for (let k = 1; k <= queued; k++) {
        const [x, y] = path.at(path.length - k * QUEUE_GAP);
        const at: Pt = [x + (k % 2 === 0 ? 9 : -6), y];
        movers.push({ id: `queue-${r.id}-${k}`, kind: "ship", path: new Polyline([at, at]), offset: 0, speed: 0, enter: "enter-coins" });
      }
      const end = path.at(path.length);
      movers.push({ id: `blocked-ship-${r.id}`, kind: "ship", path: new Polyline([[end[0], end[1] + 4], [end[0], end[1] + 4]]), offset: 0, speed: 0, rotate: 58 });
      // Name the water they queue in: the last shipping node the lane passes before the shock.
      const via = (r.edge.via ?? []).map(key);
      const upstream = network.nodes.filter((n) => (n.kind === "canal" || n.kind === "port") && via.includes(key([n.lon, n.lat])));
      if (upstream.length) {
        const last = upstream.reduce((a, b) => (via.lastIndexOf(key([b.lon, b.lat])) > via.lastIndexOf(key([a.lon, a.lat])) ? b : a));
        queuedUpstream = last.region;
      }
    }
  }
  for (const r of routes.filter((r) => r.state === "detour" && r.edge.mode === "sea")) {
    const path = paths.get(r.id)!;
    // Fewer ships take the long way round.
    const count = Math.max(1, Math.round(path.length / (SHIP_SPACING * 3)));
    for (let i = 0; i < count; i++) {
      movers.push({ id: `ship-${r.id}-${i}`, kind: "ship", path, offset: ((i + 0.5) / count) * path.length, speed: SHIP_SPEED });
    }
  }

  // Money: spend continues; revenue coins split into one on time, delayed, and lost.
  const money: MoneyLine[] = [];
  const mg = moneyGeometry(network, layout);
  const full = atRiskCoins(scenario);
  const risk = { delayed: Math.round(full.delayed * p), lost: Math.round(full.lost * p) };
  mg.revenue.forEach((rev, i) => {
    const path = new Polyline(sampleSmooth(rev.pts));
    money.push({ id: `revenue-${i}`, kind: "in", d: smoothPath(rev.pts), path });
    const end = layout.hq ? cardEdgeDistance(path, layout.hq.x + size.hqCardW + size.coin / 2) : path.length;
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
    const from = path.atFraction(0.4);
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
    const path = new Polyline(sampleSmooth(mg.spend.pts));
    money.push({ id: "spend", kind: "out", d: smoothPath(mg.spend.pts), path });
    for (let k = 0; k < 3; k++) {
      movers.push({ id: `blue-${k}`, kind: "coin", coin: "blue", size: size.coin, path, offset: (k / 3) * path.length * 0.9, speed: COIN_SPEED });
    }
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
  if (detourOpt && detourRoute) {
    const text = `${detourOpt.label}: ${detourOpt.detail}`.toUpperCase();
    const { w, h } = largePillBox(text);
    const at = paths.get(detourRoute.id)!.atFraction(0.3);
    const box = placeBox(spiral(at[0] + 10, at[1] + 40, w, h, 160), layout, { ignoreRoutes: true });
    if (box) pills.push({ key: "detour", text, big: true, bg: tierColor[4], fg: color.ocean, x: box.x, y: box.y });
  }
  const airOpt = optionMatching(scenario, /air/i);
  pills.push(...routePills(network, layout, routes, mg, airOpt?.detail ?? ""));

  // Regional groups with predicted hits run low on stock.
  const groupText: Record<string, string> = {};
  const hitIds = new Set(scenario.predictions.filter((pr) => pr.pHit >= 0.5).map((pr) => pr.nodeId));
  for (const g of layout.groups) {
    if (g.nodeIds.some((id) => hitIds.has(id))) groupText[g.key] = `${g.key.toUpperCase()}: STOCK RUNNING LOW`;
  }

  const captions: Caption[] = [];
  if (mg.spend && layout.hq?.offMap) {
    captions.push({ key: "spend-caption", text: "Payments from Apple Park, across the Pacific", x: size.mapW - 20 - 170, y: mg.spend.target[1] + 60, w: 170, color: "#9CC6EE" });
  }

  // Predicted hits (rings) and, once the event is over, actual outcomes.
  const markers: Marker[] = [];
  for (const pr of scenario.predictions) {
    const at = layout.points.get(pr.nodeId);
    const n = nodes.get(pr.nodeId);
    if (!at || !n || pr.pHit < 0.5) continue;
    markers.push({ key: `pred-${pr.nodeId}`, kind: "predicted", x: at[0], y: at[1], r: symbolSize(n.kind) / 2 + 6, low: pr.lowConfidence });
  }
  if (p >= 1) {
    for (const a of scenario.actual) {
      const at = layout.points.get(a.nodeId);
      const n = nodes.get(a.nodeId);
      if (!at || !n) continue;
      markers.push({ key: `actual-${a.nodeId}`, kind: a.hit ? "actual-hit" : "actual-miss", x: at[0], y: at[1], r: symbolSize(n.kind) / 2 + 6, low: false });
    }
  }

  const visibleEdges = network.edges;
  return { zones, groupText, routes, money, movers, pills, captions, visibleEdges, markers };
}
