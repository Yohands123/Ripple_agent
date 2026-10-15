// The trace for a clicked node: its upstream suppliers (through supply edges, as far as
// they go: refineries, mining regions) and its downstream path (assembly site, the
// ports and airports it ships through, the sea or air route, the sales regions, and the
// money back to Apple Park), and for a sales region or repair site the return routes
// onward (repair, recycling, recovered metals back to refineries). Built only from the network's edges.

import { isReturn, isRoute, isSupply, nodeIndex } from "./routes";
import type { Network, NetworkEdge, NetworkNode } from "./types";

const GATEWAY = new Set(["port", "airport"]);
const PASS_THROUGH = new Set(["canal", "chokepoint", "border"]);

export interface TraceStep {
  /** Edge ids in this step, in the order pulses travel. */
  edges: string[];
}

export interface Trace {
  root: string;
  /** Upstream node id → hops from the root (1 = direct supplier). */
  upstream: Map<string, number>;
  /** Downstream node ids. */
  downstream: Set<string>;
  /** Supply edges upstream, by hop (hop 1 first). */
  upstreamEdges: NetworkEdge[][];
  /** Route edges downstream, in travel order: to gateways, line haul, to sales regions. */
  downstreamEdges: NetworkEdge[][];
  /** Return routes onward from the root, by step (sales region → repair → recycling → refinery). */
  returnEdges: NetworkEdge[][];
  /** Counts for the Connections chain. */
  counts: {
    /** Every upstream site; `upMines` and `upRefineries` count the tier 1 and 2 ones among them. */
    suppliers: number;
    upMines: number;
    upRefineries: number;
    factories: number;
    gateways: number;
    salesRegions: number;
    repairSites: number;
    refineries: number;
  };
  /** Node ids behind each link of the chain, for clicking. */
  members: {
    suppliers: string[];
    upMines: string[];
    upRefineries: string[];
    factories: string[];
    gateways: string[];
    salesRegions: string[];
    repairSites: string[];
    refineries: string[];
  };
  /** True when the path reaches a sales region, so revenue flows back to Apple Park. */
  money: boolean;
}

const MAX_UPSTREAM_HOPS = 4;

export function buildTrace(network: Network, rootId: string): Trace | null {
  const nodes = nodeIndex(network);
  const root = nodes.get(rootId);
  if (!root) return null;
  const supply = network.edges.filter((e) => isSupply(e, nodes));
  const routes = network.edges.filter((e) => isRoute(e) && !e.alternativeTo && !e.detourOnly);

  // Upstream: suppliers of the root, their suppliers, and so on.
  const upstream = new Map<string, number>();
  const upstreamEdges: NetworkEdge[][] = [];
  let frontier = [rootId];
  for (let hop = 1; hop <= MAX_UPSTREAM_HOPS && frontier.length; hop++) {
    const into = supply.filter((e) => frontier.includes(e.to) && e.from !== rootId && !upstream.has(e.from));
    if (!into.length) break;
    upstreamEdges.push(into);
    const next: string[] = [];
    for (const e of into) {
      if (!upstream.has(e.from)) {
        upstream.set(e.from, hop);
        next.push(e.from);
      }
    }
    frontier = next;
  }

  // Downstream: the factories this node supplies (or itself), then their transport path.
  const factories = new Set<string>();
  const downstream = new Set<string>();
  const downstreamEdges: NetworkEdge[][] = [];
  if (root.kind === "assembly") factories.add(rootId);
  else {
    const toFactory: NetworkEdge[] = [];
    let f = [rootId];
    const seen = new Set(f);
    for (let i = 0; i < MAX_UPSTREAM_HOPS && f.length; i++) {
      const out = supply.filter((e) => f.includes(e.from) && !seen.has(e.to));
      toFactory.push(...out);
      f = [];
      for (const e of out) {
        seen.add(e.to);
        const n = nodes.get(e.to);
        if (n?.kind === "assembly") factories.add(e.to);
        else f.push(e.to);
        downstream.add(e.to);
      }
    }
    if (toFactory.length) downstreamEdges.push(toFactory);
  }

  // Factory → gateway (or straight onto a line haul when the file has no access link).
  const fromFactories = routes.filter((e) => factories.has(e.from));
  const gateways = new Set<string>();
  const toGateway = fromFactories.filter((e) => GATEWAY.has(nodes.get(e.to)?.kind ?? "") && e.mode === "road");
  for (const e of toGateway) gateways.add(e.to);
  if (toGateway.length) downstreamEdges.push(toGateway);

  // Line haul by sea or air from the gateways (or factories), through canals and straits.
  const haulFrom = new Set([...gateways, ...factories]);
  const haul: NetworkEdge[] = [];
  const destinations = new Set<string>();
  let reach = [...haulFrom];
  const visited = new Set(reach);
  for (let i = 0; i < 4 && reach.length; i++) {
    const out = routes.filter((e) => reach.includes(e.from) && (e.mode === "sea" || e.mode === "air") && !visited.has(e.to));
    reach = [];
    for (const e of out) {
      haul.push(e);
      visited.add(e.to);
      const k = nodes.get(e.to)?.kind ?? "";
      // Continue only through canals and straits; a port or airport is a destination.
      if (PASS_THROUGH.has(k)) reach.push(e.to);
      else destinations.add(e.to);
    }
  }
  if (haul.length) downstreamEdges.push(haul);

  // Destination → sales region.
  const salesRegions = new Set<string>();
  const toSales = routes.filter((e) => (destinations.has(e.from) || gateways.has(e.from)) && isSalesNode(nodes.get(e.to)));
  for (const e of toSales) salesRegions.add(e.to);
  if (toSales.length) downstreamEdges.push(toSales);

  // Returns: from a sales region (or a repair site) along return routes, as far as they go.
  const returns = network.edges.filter(isReturn);
  const returnEdges: NetworkEdge[][] = [];
  const repairSites = new Set<string>();
  const refineries = new Set<string>();
  let back = [rootId];
  const backSeen = new Set(back);
  for (let i = 0; i < MAX_UPSTREAM_HOPS && back.length; i++) {
    const out = returns.filter((e) => back.includes(e.from) && !backSeen.has(e.to));
    if (!out.length) break;
    returnEdges.push(out);
    back = [];
    for (const e of out) {
      backSeen.add(e.to);
      back.push(e.to);
      downstream.add(e.to);
      const k = nodes.get(e.to)?.kind;
      if (k === "repair") repairSites.add(e.to);
      else if (k === "refinery") refineries.add(e.to);
    }
  }

  for (const id of [...factories, ...gateways, ...destinations, ...salesRegions]) if (id !== rootId) downstream.add(id);
  for (const e of haul) {
    for (const v of e.viaNodeIds ?? []) downstream.add(v);
    if (PASS_THROUGH.has(nodes.get(e.to)?.kind ?? "")) downstream.add(e.to);
  }

  const upOf = (kind: string) => [...upstream.keys()].filter((id) => nodes.get(id)?.kind === kind);
  const upMines = upOf("mine");
  const upRefineries = upOf("refinery");

  return {
    root: rootId,
    upstream,
    downstream,
    upstreamEdges,
    downstreamEdges,
    returnEdges,
    counts: {
      suppliers: upstream.size,
      upMines: upMines.length,
      upRefineries: upRefineries.length,
      factories: factories.size,
      gateways: gateways.size,
      salesRegions: salesRegions.size,
      repairSites: repairSites.size,
      refineries: refineries.size,
    },
    members: {
      suppliers: [...upstream.keys()].filter((id) => !upMines.includes(id) && !upRefineries.includes(id)),
      upMines,
      upRefineries,
      factories: [...factories],
      gateways: [...gateways],
      salesRegions: [...salesRegions],
      repairSites: [...repairSites],
      refineries: [...refineries],
    },
    money: salesRegions.size > 0,
  };
}

const isSalesNode = (n: NetworkNode | undefined) => Boolean(n && (n.kind === "sales_region" || (n.tier === 6 && n.kind !== "hq")));

/** Every edge on the trace. */
export const traceEdgeIds = (t: Trace) => new Set([...t.upstreamEdges.flat(), ...t.downstreamEdges.flat(), ...t.returnEdges.flat()].map((e) => e.id));
