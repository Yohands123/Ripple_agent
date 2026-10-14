// Illustrative trade lanes: typical sea lanes and air corridors from public geography.
//
// The real export states that supplier transport routes are unknown (it has no edges).
// So the map keeps the concept art's lanes, ships, and flights, these lanes are added
// only when the network has no edges of its own. They are marked `inferred` (drawn
// dashed) and `illustrative`, and the panel says they are not supplier-specific.
// Once the pipeline exports its own edges, this layer is not used.

import { continentOf } from "./layout";
import type { Network, NetworkEdge, NetworkNode, NodeKind, Scenario, Source } from "./types";

const SOURCE: Source = {
  title: "Illustrative lane from public geography (major shipping lanes and chokepoints); not a supplier-specific route",
  url: "",
};

function node(id: string, name: string, kind: NodeKind, lon: number, lat: number, region: string, extra: Partial<NetworkNode> = {}): NetworkNode {
  return {
    id,
    name,
    kind,
    tier: 5,
    lon,
    lat,
    precision: "city",
    region,
    ticker: null,
    partType: null,
    appleRevenueShare: null,
    sources: [SOURCE],
    illustrative: true,
    ...extra,
  };
}

const NODES: NetworkNode[] = [
  node("lane-port-shanghai", "Shanghai port", "port", 121.8, 31.0, "China"),
  node("lane-port-hongkong", "Hong Kong port", "port", 114.2, 22.0, "Hong Kong"),
  node("lane-port-singapore", "Singapore port", "port", 104.0, 1.2, "Singapore"),
  node("lane-bab-el-mandeb", "Bab-el-Mandeb", "canal", 43.4, 12.6, "Red Sea"),
  node("lane-suez-canal", "Suez Canal", "canal", 32.5, 30.0, "Egypt"),
  node("lane-port-rotterdam", "Rotterdam port", "port", 4.0, 51.9, "Netherlands"),
  node("lane-port-losangeles", "Los Angeles port", "port", -118.2, 33.7, "California, USA"),
  node("lane-port-newyork", "New York port", "port", -74.0, 40.6, "New York, USA"),
  node("lane-airport-frankfurt", "Frankfurt airport", "airport", 8.57, 50.03, "Germany"),
  // Where the trans-Pacific lane leaves the east edge of the map and re-enters on the west.
  node("lane-dateline-east", "International Date Line", "border", 180, 41, "Pacific Ocean", { waypoint: true }),
  node("lane-dateline-west", "International Date Line", "border", -180, 41, "Pacific Ocean", { waypoint: true }),
];

function edge(id: string, from: string, to: string, mode: "sea" | "air", via: [number, number][] = [], extra: Partial<NetworkEdge> = {}): NetworkEdge {
  return { id, from, to, mode, carriesTier: 4, status: "inferred", sources: [SOURCE], via: via.length ? via : undefined, illustrative: true, ...extra };
}

const EDGES: NetworkEdge[] = [
  // Asia to Europe through Suez, split at the chokepoints so a shock can stop part of it.
  edge("lane-sea-shanghai-hongkong", "lane-port-shanghai", "lane-port-hongkong", "sea", [[122.6, 28], [119.8, 24.2]]),
  edge("lane-sea-hongkong-singapore", "lane-port-hongkong", "lane-port-singapore", "sea", [[112, 12]]),
  edge("lane-sea-singapore-babelmandeb", "lane-port-singapore", "lane-bab-el-mandeb", "sea", [[99, 4.5], [93, 6], [81, 5], [60, 12], [48, 12.5]]),
  edge("lane-sea-babelmandeb-suez", "lane-bab-el-mandeb", "lane-suez-canal", "sea", [[38, 20], [34, 27.5]]),
  edge("lane-sea-suez-rotterdam", "lane-suez-canal", "lane-port-rotterdam", "sea", [[32.3, 31.6], [25, 34], [15, 36], [5, 37.5], [-5.6, 36], [-11, 38], [-9, 45], [-3, 49.5]]),
  // Around Africa: only drawn as a detour when Suez or the Red Sea is shut.
  edge(
    "lane-sea-cape",
    "lane-port-singapore",
    "lane-port-rotterdam",
    "sea",
    [[81, 5], [70, -5], [55, -20], [52, -30], [35, -36], [18.5, -36], [5, -25], [-10, -5], [-22, 15], [-18, 30], [-12, 40], [-9, 45], [-3, 49.5]],
    { detourOnly: true, avoids: ["lane-suez-canal", "lane-bab-el-mandeb"], label: "Detour around Africa" },
  ),
  // Across the Pacific, split where it crosses the date line.
  edge("lane-sea-transpacific-east", "lane-port-shanghai", "lane-dateline-east", "sea", [[130, 32.5], [145, 36.5], [163, 39.5]]),
  edge("lane-sea-transpacific-west", "lane-dateline-west", "lane-port-losangeles", "sea", [[-160, 40], [-140, 37.5], [-125, 34.5]]),
  // Across the Atlantic.
  edge("lane-sea-transatlantic", "lane-port-rotterdam", "lane-port-newyork", "sea", [[-3, 49.5], [-12, 49], [-30, 46], [-50, 42], [-65, 40.5]]),
  // Air freight, Asia to Europe.
  edge("lane-air-hongkong-frankfurt", "lane-port-hongkong", "lane-airport-frankfurt", "air"),
  edge("lane-air-shanghai-frankfurt", "lane-port-shanghai", "lane-airport-frankfurt", "air"),
];

/** True when the network has no routes of its own, so illustrative lanes are drawn instead. */
export function needsIllustrativeLanes(network: Network): boolean {
  return network.edges.length === 0;
}

/** The network plus illustrative lanes, or the network unchanged when it has its own edges. */
export function withIllustrativeLanes(network: Network): Network {
  if (!needsIllustrativeLanes(network)) return network;
  return { ...network, nodes: [...network.nodes, ...NODES], edges: [...EDGES] };
}

const SEA_SHOCK_RADIUS_DEG = 12;
const PORT_SHOCK_RADIUS_DEG = 1.5;

/**
 * For a scenario that gives only a shock location (no shock nodes, no affected routes),
 * work out which illustrative lanes it touches. Sea shocks close the nearest chokepoint;
 * a shock at a port closes lanes leaving it. Inland shocks touch no lanes.
 * Scenarios with their own shock nodes or affected routes are returned unchanged.
 */
export function withIllustrativeEffects(scenario: Scenario, network: Network): Scenario {
  const lanes = network.edges.filter((e) => e.illustrative);
  const loc = scenario.shock.location;
  const own = scenario.shock.nodeIds.length > 0 || Object.values(scenario.affectedRoutes).some((l) => l.length > 0);
  if (lanes.length === 0 || !loc || own) return scenario;

  const laneNodes = network.nodes.filter((n) => n.illustrative && !n.waypoint);
  const dist = (n: NetworkNode) => Math.hypot(n.lon - loc.lon, n.lat - loc.lat);
  const nearest = (kinds: NodeKind[], radius: number) =>
    laneNodes.filter((n) => kinds.includes(n.kind) && dist(n) <= radius).sort((a, b) => dist(a) - dist(b))[0];
  const hit = scenario.type === "sea" ? nearest(["canal"], SEA_SHOCK_RADIUS_DEG) : nearest(["port"], PORT_SHOCK_RADIUS_DEG);
  if (!hit) return scenario;

  // A detour exists when a detour-only lane avoids the shocked chokepoint.
  const detours = lanes.filter((e) => e.detourOnly && e.avoids?.includes(hit.id));
  const rejoin = new Set(detours.map((d) => d.to));

  // Block lanes leaving the shocked point, following the chain until a detour rejoins it.
  const blocked: string[] = [];
  const sea = lanes.filter((e) => e.mode === "sea" && !e.detourOnly);
  let frontier = [hit.id];
  const seen = new Set<string>();
  while (frontier.length) {
    const next: string[] = [];
    for (const id of frontier) {
      for (const e of sea.filter((x) => x.from === id && !seen.has(x.id))) {
        seen.add(e.id);
        blocked.push(e.id);
        if (detours.length > 0 && !rejoin.has(e.to)) next.push(e.to);
      }
    }
    frontier = next;
  }

  // Flights out of a shut port are grounded too.
  const air = lanes.filter((e) => e.mode === "air");
  if (hit.kind === "port") for (const e of air) if (e.from === hit.id) blocked.push(e.id);

  // Air freight picks up the slack on flights to the continent the blocked sea lanes were heading for.
  const byId = new Map(network.nodes.map((n) => [n.id, n]));
  const continent = (id: string) => {
    const n = byId.get(id);
    return n ? continentOf(n.lon, n.lat) : "";
  };
  const cutOff = new Set(blocked.map((id) => lanes.find((e) => e.id === id)!).filter((e) => e.mode === "sea").map((e) => continent(e.to)));
  const expedited = air.filter((e) => !blocked.includes(e.id) && cutOff.has(continent(e.to))).map((e) => e.id);

  return {
    ...scenario,
    shock: { ...scenario.shock, nodeIds: [hit.id] },
    affectedRoutes: { blocked, detour: detours.map((d) => d.id), expedited },
  };
}
