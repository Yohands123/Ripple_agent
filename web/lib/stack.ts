// Supplier stacks: an assembly factory, its direct suppliers (tier 1), and their suppliers (tier 2),
// taken only from the network's supply edges (who supplies whom), never from transport routes.

import { isSupply, nodeIndex } from "./routes";
import type { Network, NetworkEdge, NetworkNode, Scenario } from "./types";

export interface StackItem {
  node: NetworkNode;
  /** The supply link that puts the node at this level. */
  edge: NetworkEdge;
}

export interface StackGroup {
  partType: string;
  items: StackItem[];
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

/** Suppliers feeding `id` directly through supply edges. */
export function suppliersOf(id: string, network: Network, nodes = nodeIndex(network)): StackItem[] {
  const out: StackItem[] = [];
  const seen = new Set<string>();
  for (const e of network.edges) {
    if (e.to !== id || seen.has(e.from) || !isSupply(e, nodes)) continue;
    const n = nodes.get(e.from);
    if (!n || n.kind === "hq") continue;
    seen.add(e.from);
    out.push({ node: n, edge: e });
  }
  return out;
}

/** Who `id` supplies, through supply edges. */
export function customersOf(id: string, network: Network, nodes = nodeIndex(network)): StackItem[] {
  return network.edges
    .filter((e) => e.from === id && isSupply(e, nodes) && nodes.has(e.to))
    .map((e) => ({ node: nodes.get(e.to)!, edge: e }));
}

function group(list: StackItem[]): StackGroup[] {
  const by = new Map<string, StackItem[]>();
  for (const it of list) {
    const k = it.node.partType ?? it.edge.partType ?? "part type not stated";
    by.set(k, [...(by.get(k) ?? []), it]);
  }
  return [...by.entries()].sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0])).map(([partType, items]) => ({ partType, items }));
}

export function buildStack(network: Network, factoryId: string, scenario: Scenario | null, disrupted: boolean): Stack | null {
  const nodes = nodeIndex(network);
  const factory = nodes.get(factoryId);
  if (!factory || factory.kind !== "assembly") return null;

  const tier1 = suppliersOf(factory.id, network, nodes).filter((it) => it.node.id !== factory.id);
  const t1ids = new Set(tier1.map((it) => it.node.id));
  const tier2Map = new Map<string, StackItem>();
  for (const s of tier1) {
    for (const it of suppliersOf(s.node.id, network, nodes)) {
      if (it.node.id !== factory.id && !t1ids.has(it.node.id)) tier2Map.set(it.node.id, it);
    }
  }
  const tier2 = [...tier2Map.values()];

  const hit = new Set<string>();
  if (disrupted && scenario) {
    for (const id of scenario.shock.nodeIds) hit.add(id);
    for (const p of scenario.predictions) if (p.pHit >= 0.5) hit.add(p.nodeId);
  }
  const anyHit = (list: StackItem[]) => list.some((it) => hit.has(it.node.id));
  const self: StackItem = { node: factory, edge: { id: "self", from: factory.id, to: factory.id, mode: "road", carriesTier: factory.tier, status: "known", sources: [] } };

  const levels: StackLevel[] = [
    { key: "factory", title: "Assembly factory", groups: group([self]), partial: false },
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
