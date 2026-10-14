// Supplier stacks: an assembly factory, its direct suppliers (tier 1), and their suppliers (tier 2),
// taken only from the network's edges.

import type { Network, NetworkNode, Scenario } from "./types";

const SHIPPING = new Set(["port", "airport", "canal", "border"]);

export interface StackGroup {
  partType: string;
  nodes: NetworkNode[];
}

export interface StackLevel {
  key: "factory" | "tier1" | "tier2";
  title: string;
  groups: StackGroup[];
  /** Tier 2 is only partly known from public data. */
  partial: boolean;
}

export interface Chute {
  /** Between which levels: 0 = factory↔tier 1, 1 = tier 1↔tier 2. */
  gap: 0 | 1;
  direction: "up" | "down";
  active: boolean;
}

export interface Stack {
  factory: NetworkNode;
  levels: StackLevel[];
  chutes: Chute[];
  /** Node ids with a shortage (shocked, or predicted hit) in the scenario. */
  hit: Set<string>;
}

/** Suppliers feeding `id` directly. Shipping nodes are followed through, since goods only pass them. */
function suppliersOf(id: string, network: Network, nodes: Map<string, NetworkNode>, seen = new Set<string>()): NetworkNode[] {
  const out: NetworkNode[] = [];
  for (const e of network.edges) {
    if (e.to !== id || seen.has(e.from)) continue;
    seen.add(e.from);
    const n = nodes.get(e.from);
    if (!n) continue;
    if (SHIPPING.has(n.kind)) out.push(...suppliersOf(n.id, network, nodes, seen));
    else if ((n.tier == null || n.tier <= 4) && n.kind !== "hq") out.push(n);
  }
  return out;
}

function group(list: NetworkNode[]): StackGroup[] {
  const by = new Map<string, NetworkNode[]>();
  for (const n of list) {
    const k = n.partType ?? "part type not stated";
    by.set(k, [...(by.get(k) ?? []), n]);
  }
  return [...by.entries()].sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0])).map(([partType, nodes]) => ({ partType, nodes }));
}

export function buildStack(network: Network, factoryId: string, scenario: Scenario | null, disrupted: boolean): Stack | null {
  const nodes = new Map(network.nodes.map((n) => [n.id, n]));
  const factory = nodes.get(factoryId);
  if (!factory || factory.kind !== "assembly") return null;

  const tier1 = suppliersOf(factory.id, network, nodes).filter((n) => n.id !== factory.id);
  const t1ids = new Set(tier1.map((n) => n.id));
  const tier2Map = new Map<string, NetworkNode>();
  for (const s of tier1) {
    for (const n of suppliersOf(s.id, network, nodes)) {
      if (n.id !== factory.id && !t1ids.has(n.id)) tier2Map.set(n.id, n);
    }
  }
  const tier2 = [...tier2Map.values()];

  const hit = new Set<string>();
  if (disrupted && scenario) {
    for (const id of scenario.shock.nodeIds) hit.add(id);
    for (const p of scenario.predictions) if (p.pHit >= 0.5) hit.add(p.nodeId);
  }
  const anyHit = (list: NetworkNode[]) => list.some((n) => hit.has(n.id));

  const levels: StackLevel[] = [
    { key: "factory", title: "Assembly factory", groups: group([factory]), partial: false },
    { key: "tier1", title: "Tier 1: direct suppliers", groups: group(tier1), partial: false },
    { key: "tier2", title: "Tier 2: their suppliers (partly known)", groups: group(tier2), partial: true },
  ];
  const chutes: Chute[] = [
    { gap: 0, direction: "up", active: anyHit(tier1) },
    { gap: 0, direction: "down", active: hit.has(factory.id) },
    { gap: 1, direction: "up", active: anyHit(tier2) },
    { gap: 1, direction: "down", active: hit.has(factory.id) || anyHit(tier1) },
  ];
  return { factory, levels, chutes, hit };
}
