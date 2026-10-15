// The ripple when a disruption drops: from the shock and the routes it closes, out to the
// suppliers that ship through those places (hop 1), then to their own suppliers (hop 2).
// Built only from the network's edges and the scenario's shock and affected routes.

import { edgeRank, isRoute, isSupply, isSupplierKind, nodeIndex } from "./routes";
import type { Network, NetworkEdge, Scenario } from "./types";

/** Seconds after the drop when each hop is reached (hop 1 at 0.5 s, hop 2 at 1 s). */
export const HOP_DELAY = 0.5;
export const MAX_HOPS = 2;

export interface RippleLink {
  edge: NetworkEdge;
  /** The end already reached, and the supplier the wave reaches through this link. */
  from: string;
  to: string;
  hop: number;
}

export interface Ripple {
  /** Supplier id → hop at which the wave reaches it. */
  hops: Map<string, number>;
  links: RippleLink[];
  /** Suppliers reached at each hop (index 0 = hop 1). */
  counts: number[];
}

export function buildRipple(network: Network, scenario: Scenario): Ripple {
  const nodes = nodeIndex(network);
  const blocked = new Set(scenario.affectedRoutes.blocked);
  const shock = new Set(scenario.shock.nodeIds);

  // Hop 0: the shock, the places at either end of the routes it closes, and (through
  // reference road links) the factories and gateways next to those places.
  const exposed = new Set<string>(shock);
  for (const e of network.edges) {
    if (!isRoute(e)) continue;
    const through = blocked.has(e.id) || shock.has(e.from) || shock.has(e.to) || (e.viaNodeIds ?? []).some((id) => shock.has(id));
    if (!through || edgeRank(e) === "supplier") continue;
    exposed.add(e.from);
    exposed.add(e.to);
  }
  for (const e of network.edges) {
    if (!isRoute(e) || e.mode !== "road" || edgeRank(e) === "supplier") continue;
    const a = nodes.get(e.from);
    const b = nodes.get(e.to);
    if (exposed.has(e.to) && a?.kind === "assembly") exposed.add(e.from);
    if (exposed.has(e.from) && b?.kind === "assembly") exposed.add(e.to);
  }

  const hops = new Map<string, number>();
  const links: RippleLink[] = [];
  const isSite = (id: string) => {
    const n = nodes.get(id);
    return Boolean(n && isSupplierKind(n.kind));
  };
  // A supplier link (a site's road to its gateway) or a supply link joins a supplier to a reached place.
  // A metal-specific shock (cobalt) passes only along mineral links that carry that metal.
  const mineral = scenario.shock.mineral;
  const carries = (e: NetworkEdge) => !mineral || !e.metal || e.metal === mineral;
  const joins = (e: NetworkEdge) => carries(e) && (isSupply(e, nodes) || (isRoute(e) && edgeRank(e) === "supplier"));

  let frontier = exposed;
  for (let hop = 1; hop <= MAX_HOPS; hop++) {
    const next = new Set<string>();
    for (const e of network.edges) {
      if (!joins(e) && !(blocked.has(e.id) && edgeRank(e) === "supplier")) continue;
      for (const [a, b] of [
        [e.from, e.to],
        [e.to, e.from],
      ] as const) {
        if (!frontier.has(a) || !isSite(b) || hops.has(b) || exposed.has(b)) continue;
        // Hop 2 follows supply links only: the suppliers of suppliers reached at hop 1.
        if (hop > 1 && !isSupply(e, nodes)) continue;
        hops.set(b, hop);
        next.add(b);
        links.push({ edge: e, from: a, to: b, hop });
      }
    }
    frontier = next;
  }
  const counts = Array.from({ length: MAX_HOPS }, (_, i) => [...hops.values()].filter((h) => h === i + 1).length);
  return { hops, links, counts };
}

/** Risk color: from the sales gold (lowest in the event) to alert red (highest), relative to the event. */
export function riskColor(pHit: number, min: number, max: number): string {
  const t = max > min ? Math.min(1, Math.max(0, (pHit - min) / (max - min))) : 0.5;
  const lo = [0xf2, 0xc1, 0x4e];
  const hi = [0xd6, 0x45, 0x3d];
  const c = lo.map((v, i) => Math.round(v + (hi[i] - v) * t));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}
