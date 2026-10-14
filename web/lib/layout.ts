// Where nodes, their label pills, and regional group labels go on the map.

import { DEFAULT_FRAME, project, WORLD_BOUNDS, type Pt } from "./geo";
import { nodeIndex, sampleEdge } from "./routes";
import { size } from "./tokens";
import type { Network, NetworkEdge, NetworkNode, NodeKind } from "./types";

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

const overlaps = (a: Box, b: Box, pad = 2) =>
  a.x < b.x + b.w + pad && b.x < a.x + a.w + pad && a.y < b.y + b.h + pad && b.y < a.y + a.h + pad;

const inside = (p: Pt, b: Box) => p[0] >= b.x && p[0] <= b.x + b.w && p[1] >= b.y && p[1] <= b.y + b.h;

/** Symbol size in px for each node kind (docs/design-spec.md, Node symbols). */
export function symbolSize(kind: NodeKind): number {
  switch (kind) {
    case "assembly":
      return size.assembly;
    case "supplier_major":
    case "mine":
    case "refinery":
      return size.major;
    case "supplier_minor":
      return size.minor;
    case "port":
    case "airport":
    case "canal":
    case "border":
      return size.port;
    case "carrier":
      return size.carrier;
    default:
      return size.store;
  }
}

export const isSales = (n: NetworkNode) => n.tier === 6 && n.kind !== "hq";
const isShippingKind = (k: NodeKind) => k === "port" || k === "airport" || k === "canal" || k === "border";

/** Rough continent for a point, used to name regional groups and sea lanes. */
export function continentOf(lon: number, lat: number): string {
  if (lon < -30) return lat > 13 ? "North America" : "South America";
  if (lat > 35 && lon < 45) return "Europe";
  if (lon < 52 && lat < 35 && !(lon > 34 && lat > 12)) return "Africa";
  if (lon > 110 && lat < -10) return "Australia";
  return "Asia";
}

/** Estimated pill size: small pills are 12 px Archivo bold at 85% width, padding 4 × 9. */
export function smallPillBox(text: string): { w: number; h: number } {
  return { w: Math.round(text.length * 7.25 + 18), h: 23 };
}

export function largePillBox(text: string): { w: number; h: number } {
  return { w: Math.round(text.length * 10.6 + 32), h: 39 };
}

export interface NodeLabel {
  nodeId: string;
  text: string;
  x: number;
  y: number;
}

export interface GroupLabel {
  key: string;
  text: string;
  x: number;
  y: number;
  nodeIds: string[];
}

export interface HqCard {
  /** The card at Apple Park's real location. */
  x: number;
  y: number;
  /** Apple Park's real location, where money lines end. */
  anchor: Pt;
  /** True when Apple Park is outside the concept-art view (it is, at Cupertino). */
  offMap: boolean;
  /** Where the card is pinned on screen while Apple Park is out of view (top-left, as in the concept art). */
  pin: { x: number; y: number; anchor: Pt };
}

/** The 1440 × 810 concept view, inset 4 px, for keeping its pills tidy. */
const FRAME: Box = { x: DEFAULT_FRAME.x + 4, y: DEFAULT_FRAME.y + 4, w: DEFAULT_FRAME.w - 8, h: DEFAULT_FRAME.h - 8 };
const WORLD: Box = { x: WORLD_BOUNDS.x0 + 4, y: WORLD_BOUNDS.y0 + 4, w: WORLD_BOUNDS.x1 - WORLD_BOUNDS.x0 - 8, h: WORLD_BOUNDS.y1 - WORLD_BOUNDS.y0 - 8 };

/** Pills for things in the concept view stay inside it; pills elsewhere only need to stay on the world. */
function frameFor(anchor: Pt): Box {
  return inside(anchor, DEFAULT_FRAME) ? FRAME : WORLD;
}

const within = (b: Box, f: Box) => b.x >= f.x && b.y >= f.y && b.x + b.w <= f.x + f.w && b.y + b.h <= f.y + f.h;

export interface MapLayout {
  points: Map<string, Pt>;
  labels: NodeLabel[];
  groups: GroupLabel[];
  hq: HqCard | null;
  /** Boxes already used by labels and cards, for placing more pills later. */
  taken: Box[];
  /** Node symbol boxes and sampled route points to keep pills off. */
  obstacles: { boxes: Box[]; pts: Pt[] };
}

/** Candidate boxes spiralling out from a preferred top-left corner, nearest first. */
export function spiral(x: number, y: number, w: number, h: number, maxR = 160, step = 8): Box[] {
  const out: Box[] = [{ x, y, w, h }];
  for (let r = step; r <= maxR; r += step) {
    const n = Math.max(8, Math.round((2 * Math.PI * r) / step));
    for (let i = 0; i < n; i++) {
      const a = (i / n) * 2 * Math.PI;
      out.push({ x: Math.round(x + r * Math.cos(a)), y: Math.round(y + r * Math.sin(a)), w, h });
    }
  }
  return out;
}

/** First candidate box that stays in frame and clear of `taken` and `obstacles`; it is then marked taken. */
export function placeBox(candidates: Box[], layout: MapLayout, opts: { ignoreRoutes?: boolean; anchor?: Pt } = {}): Box | null {
  const first = candidates[0];
  // Stay in the concept view when the thing being labelled is in it.
  const anchor = opts.anchor ?? (first ? ([first.x + first.w / 2, first.y + first.h / 2] as Pt) : null);
  const frame = anchor ? frameFor(anchor) : FRAME;
  const pick = candidates.find(
    (b) =>
      within(b, frame) &&
      !layout.taken.some((o) => overlaps(b, o)) &&
      !layout.obstacles.boxes.some((o) => overlaps(b, o)) &&
      (opts.ignoreRoutes || !layout.obstacles.pts.some((p) => inside(p, b))),
  );
  if (pick) layout.taken.push(pick);
  return pick ?? null;
}

function labelText(n: NetworkNode): string | null {
  const strip = (s: string) => s.replace(/\s+(assembly|port|plant|factory)$/i, "").trim();
  switch (n.kind) {
    case "assembly":
      return strip(n.name).toUpperCase();
    case "supplier_major":
      return (n.region.split(",")[0] || n.name).trim().toUpperCase();
    case "port":
      return strip(n.name).toUpperCase();
    default:
      return null;
  }
}

function groupText(continent: string, nodes: NetworkNode[]): string {
  const kinds = new Set(nodes.map((n) => n.kind));
  const parts: string[] = [];
  if (kinds.has("apple_store")) parts.push("STORES");
  if (kinds.has("carrier")) parts.push("CARRIERS");
  if (kinds.has("retailer")) parts.push("RETAILERS");
  if (kinds.has("repair")) parts.push("REPAIR");
  return `${continent.toUpperCase()}: ${parts.join(", ")}`;
}

export function computeLayout(network: Network, visibleEdges: NetworkEdge[], extraObstaclePts: Pt[] = []): MapLayout {
  const points = new Map<string, Pt>();
  for (const n of network.nodes) points.set(n.id, project(n.lon, n.lat));
  const nodes = nodeIndex(network);
  const inView = (n: NetworkNode) => inside(points.get(n.id)!, DEFAULT_FRAME);
  const onWorld = (n: NetworkNode) => inside(points.get(n.id)!, WORLD);

  // Obstacles: node symbols and sampled routes.
  const nodeBoxes: Box[] = network.nodes.filter((n) => onWorld(n) && !n.waypoint).map((n) => {
    const [x, y] = points.get(n.id)!;
    const s = symbolSize(n.kind);
    return { x: x - s / 2, y: y - s / 2, w: s, h: s };
  });
  // Thin dotted air arcs may pass behind labels (as in the concept art); solid lanes may not.
  const routePts: Pt[] = [...visibleEdges.filter((e) => e.mode !== "air").flatMap((e) => sampleEdge(e, nodes, 6)), ...extraObstaclePts];
  const taken: Box[] = [];

  // Apple Park card: drawn at its real location; while that is out of view the
  // card is pinned top-left on screen, as in the concept art.
  const hqNode = network.nodes.find((n) => n.kind === "hq");
  let hq: HqCard | null = null;
  if (hqNode) {
    const p = points.get(hqNode.id)!;
    const cardH = 48;
    const pin = { x: 12, y: 12, anchor: [12 + 48, 12 + 31] as Pt };
    hq = { x: p[0] - size.hqCardW / 2, y: p[1] - cardH - 8, anchor: p, offMap: !inView(hqNode), pin };
    taken.push({ x: hq.x, y: hq.y, w: size.hqCardW, h: cardH });
    if (hq.offMap) taken.push({ x: pin.x, y: pin.y, w: size.hqCardW, h: cardH });
  }

  // Regional sales groups get one pill instead of per-node labels.
  const groups: GroupLabel[] = [];
  const byContinent = new Map<string, NetworkNode[]>();
  for (const n of network.nodes.filter((n) => isSales(n) && onWorld(n))) {
    const c = continentOf(n.lon, n.lat);
    byContinent.set(c, [...(byContinent.get(c) ?? []), n]);
  }
  for (const [continent, members] of byContinent) {
    const pts = members.map((m) => points.get(m.id)!);
    const maxX = Math.max(...pts.map((p) => p[0]));
    const maxY = Math.max(...pts.map((p) => p[1]));
    const text = groupText(continent, members);
    const box = { x: maxX, y: maxY - 25, ...smallPillBox(text) };
    taken.push(box);
    groups.push({ key: continent, text, x: box.x, y: box.y, nodeIds: members.map((m) => m.id) });
  }
  const nearSalesGroup = (n: NetworkNode) =>
    network.nodes.some((s) => isSales(s) && Math.hypot(s.lon - n.lon, s.lat - n.lat) < 12);

  // Individual pills: try left, right, below, above; skip duplicates and collisions.
  const labels: NodeLabel[] = [];
  const used = new Set<string>();
  const order: NodeKind[] = ["assembly", "supplier_major", "port"];
  const candidates = [...network.nodes]
    .filter((n) => onWorld(n) && order.includes(n.kind))
    .sort((a, b) => order.indexOf(a.kind) - order.indexOf(b.kind));
  for (const n of candidates) {
    const text = labelText(n);
    if (!text || used.has(text)) continue;
    if (isShippingKind(n.kind) && nearSalesGroup(n)) continue;
    const [cx, cy] = points.get(n.id)!;
    const r = symbolSize(n.kind) / 2;
    const { w, h } = smallPillBox(text);
    const options: Box[] = [
      { x: cx - r - 4 - w, y: cy - h / 2, w, h },
      { x: cx + r + 4, y: cy - h / 2, w, h },
      { x: cx - w / 2, y: cy + r + 13, w, h },
      { x: cx - w / 2, y: cy - r - 8 - h, w, h },
    ];
    const ownBox: Box = { x: cx - r, y: cy - r, w: 2 * r, h: 2 * r };
    const frame = frameFor([cx, cy]);
    const fits = (b: Box) =>
      within(b, frame) &&
      !nodeBoxes.some((o) => o !== ownBox && !(o.x === ownBox.x && o.y === ownBox.y) && overlaps(b, o)) &&
      !taken.some((o) => overlaps(b, o)) &&
      !routePts.some((p) => inside(p, b));
    const pick = options.find(fits);
    if (!pick) continue;
    used.add(text);
    taken.push(pick);
    labels.push({ nodeId: n.id, text, x: Math.round(pick.x), y: Math.round(pick.y) });
  }

  return { points, labels, groups, hq, taken, obstacles: { boxes: nodeBoxes, pts: routePts } };
}
