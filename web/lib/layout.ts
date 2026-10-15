// Where nodes, their label pills, and regional group labels go on the map.

import { DEFAULT_FRAME, project, WORLD_BOUNDS, type Pt } from "./geo";
import { bubbleSize, clusterSites, type Cluster } from "./declutter";
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

/** Boxes bucketed on a grid, so "does this pill hit anything?" looks only at nearby boxes. */
class BoxGrid {
  private cells = new Map<string, Box[]>();
  constructor(
    boxes: Box[] = [],
    private cell = 40,
  ) {
    for (const b of boxes) this.add(b);
  }
  private keys(b: Box, pad: number): string[] {
    const out: string[] = [];
    const [x0, x1] = [Math.floor((b.x - pad) / this.cell), Math.floor((b.x + b.w + pad) / this.cell)];
    const [y0, y1] = [Math.floor((b.y - pad) / this.cell), Math.floor((b.y + b.h + pad) / this.cell)];
    for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) out.push(`${x},${y}`);
    return out;
  }
  add(b: Box) {
    for (const k of this.keys(b, 0)) {
      const list = this.cells.get(k);
      if (list) list.push(b);
      else this.cells.set(k, [b]);
    }
  }
  hits(b: Box, pad = 2, skip?: (o: Box) => boolean): boolean {
    for (const k of this.keys(b, pad)) for (const o of this.cells.get(k) ?? []) if (overlaps(b, o, pad) && !skip?.(o)) return true;
    return false;
  }
}

/** Points bucketed on a grid: is any point inside a box? */
class PointGrid {
  private cells = new Map<string, Pt[]>();
  constructor(
    pts: Pt[],
    private cell = 40,
  ) {
    for (const p of pts) {
      const k = `${Math.floor(p[0] / cell)},${Math.floor(p[1] / cell)}`;
      const list = this.cells.get(k);
      if (list) list.push(p);
      else this.cells.set(k, [p]);
    }
  }
  anyInside(b: Box): boolean {
    for (let x = Math.floor(b.x / this.cell); x <= Math.floor((b.x + b.w) / this.cell); x++)
      for (let y = Math.floor(b.y / this.cell); y <= Math.floor((b.y + b.h) / this.cell); y++)
        for (const p of this.cells.get(`${x},${y}`) ?? []) if (inside(p, b)) return true;
    return false;
  }
}

const pointGrids = new WeakMap<Pt[], PointGrid>();
/** The route-point grid for a layout, built once. */
const routeGrid = (pts: Pt[]) => {
  let g = pointGrids.get(pts);
  if (!g) pointGrids.set(pts, (g = new PointGrid(pts)));
  return g;
};

/** Symbol size in px for each node kind (docs/design-spec.md, Node symbols). */
export function symbolSize(kind: NodeKind): number {
  switch (kind) {
    case "assembly":
      return size.assembly;
    case "supplier_major":
      return size.major;
    case "mine":
      // A soft region marker, wider than a point symbol.
      return 48;
    case "refinery":
      return 22;
    case "supplier_minor":
      return size.minor;
    case "port":
    case "airport":
    case "canal":
    case "chokepoint":
    case "border":
    case "event_anchor":
      return size.port;
    case "carrier":
      return size.carrier;
    default:
      return size.store;
  }
}

export const isSales = (n: NetworkNode) => n.kind === "sales_region" || (n.tier === 6 && n.kind !== "hq");
const isShippingKind = (k: NodeKind) => k === "port" || k === "airport" || k === "canal" || k === "chokepoint" || k === "border";

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
  /** Lowest zoom at which the label shows. Labels keep their screen size, so zooming in makes room for more. */
  minK: number;
  /** The point the pill shrinks toward when counter-scaled, relative to its top-left, in px. */
  origin: Pt;
  /** Number of sites the label stands for. */
  weight: number;
}

/** Zoom levels at which labels are thinned or added (1 is the concept-art view). */
export const LABEL_LEVELS = [0.25, 0.35, 0.5, 0.7, 1, 1.6, 2.4, 3.5, 5, 8];

/** The level in effect at zoom k: the highest one not above it. */
export function labelLevel(k: number): number {
  let level = LABEL_LEVELS[0];
  for (const l of LABEL_LEVELS) if (l <= k + 1e-6) level = l;
  return level;
}

/** A box scaled by f about a point. */
const scaleAbout = (b: Box, o: Pt, f: number): Box => ({ x: o[0] + (b.x - o[0]) * f, y: o[1] + (b.y - o[1]) * f, w: b.w * f, h: b.h * f });

/** The point of a box closest to p. */
const nearestOn = (b: Box, p: Pt): Pt => [Math.min(b.x + b.w, Math.max(b.x, p[0])), Math.min(b.y + b.h, Math.max(b.y, p[1]))];

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
  /** Label candidates in priority order, for adding labels at other zoom levels. */
  labelCandidates: LabelCandidate[];
  /** Supplier sites gathered into clusters at each label level. */
  clusters: Map<number, Cluster[]>;
}

interface LabelCandidate {
  text: string;
  /** Sites sharing the label, nearest the cluster's centre first. */
  members: NetworkNode[];
}

/** Box options for a pill of size w x h beside a symbol of radius r at (cx, cy), at zoom level L. */
function pillOptions(cx: number, cy: number, r: number, w: number, h: number, L = 1): Box[] {
  const pw = w / L;
  const ph = h / L;
  return [
    { x: cx - r - 4 / L - pw, y: cy - ph / 2, w: pw, h: ph },
    { x: cx + r + 4 / L, y: cy - ph / 2, w: pw, h: ph },
    { x: cx - pw / 2, y: cy + r + 13 / L, w: pw, h: ph },
    { x: cx - pw / 2, y: cy - r - 8 / L - ph, w: pw, h: ph },
  ];
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
      (opts.ignoreRoutes || !routeGrid(layout.obstacles.pts).anyInside(b)),
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
    case "refinery":
      return (n.region.split(",")[0] || n.name).trim().toUpperCase();
    case "mine":
      // Mining regions are named places (e.g. a copper belt), not a site's province.
      return n.name.trim().toUpperCase();
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
  if (kinds.has("sales_region")) parts.push("SALES REGION");
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
  const routePts: Pt[] = [...visibleEdges.filter((e) => e.mode !== "air").flatMap((e) => sampleEdge(e, nodes)), ...extraObstaclePts];
  // Screen furniture over the concept view: the status pill, the year tag, and the zoom buttons.
  const taken: Box[] = [
    { x: 556, y: 14, w: 204, h: 46 },
    { x: 16, y: 700, w: 350, h: 100 },
    { x: 1250, y: 752, w: 186, h: 50 },
  ];

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
    // Apple's reporting regions are their own groups; stores and carriers group by continent.
    const c = n.salesRegion ?? continentOf(n.lon, n.lat);
    byContinent.set(c, [...(byContinent.get(c) ?? []), n]);
  }
  for (const [continent, members] of byContinent) {
    const pts = members.map((m) => points.get(m.id)!);
    const maxX = Math.max(...pts.map((p) => p[0]));
    const maxY = Math.max(...pts.map((p) => p[1]));
    const text = groupText(continent, members);
    const size0 = smallPillBox(text);
    // The concept-art spot first; nudged until it stays on the map and off other pills.
    const box =
      spiral(maxX, maxY - 25, size0.w, size0.h, 120).find((b) => within(b, frameFor([maxX, maxY])) && !taken.some((o) => overlaps(b, o))) ??
      { x: maxX, y: maxY - 25, ...size0 };
    taken.push(box);
    groups.push({ key: continent, text, x: box.x, y: box.y, nodeIds: members.map((m) => m.id) });
  }
  const nearSalesGroup = (n: NetworkNode) =>
    network.nodes.some((s) => isSales(s) && Math.hypot(s.lon - n.lon, s.lat - n.lat) < 12);

  // Label candidates: one per label text (a region can hold many sites), assembly first,
  // then the biggest clusters, so the biggest clusters keep their labels when space runs out.
  // Backbone (assembly, ports) before suppliers; among suppliers, bigger clusters first.
  const order: NodeKind[] = ["assembly", "port", "mine", "refinery", "supplier_major"];
  const byText = new Map<string, NetworkNode[]>();
  for (const n of network.nodes) {
    if (!onWorld(n) || !order.includes(n.kind)) continue;
    const text = labelText(n);
    if (!text || (isShippingKind(n.kind) && nearSalesGroup(n))) continue;
    byText.set(text, [...(byText.get(text) ?? []), n]);
  }
  const labelCandidates: LabelCandidate[] = [...byText.entries()]
    .map(([text, members]) => {
      const pts = members.map((m) => points.get(m.id)!);
      const mx = pts.reduce((s, p) => s + p[0], 0) / pts.length;
      const my = pts.reduce((s, p) => s + p[1], 0) / pts.length;
      const d = (m: NetworkNode) => Math.hypot(points.get(m.id)![0] - mx, points.get(m.id)![1] - my);
      return { text, members: [...members].sort((a, b) => d(a) - d(b)) };
    })
    .sort((a, b) => {
      const ka = Math.min(...a.members.map((m) => order.indexOf(m.kind)));
      const kb = Math.min(...b.members.map((m) => order.indexOf(m.kind)));
      return ka - kb || b.members.length - a.members.length;
    });

  const clusters = new Map(LABEL_LEVELS.map((L) => [L, clusterSites(network.nodes.filter(onWorld), points, L)]));
  // Pills keep off cluster bubbles as well as symbols.
  for (const c of clusters.get(1) ?? []) {
    if (c.members.length < 2) continue;
    const d = bubbleSize(c.members.length);
    nodeBoxes.push({ x: c.x - d / 2, y: c.y - d / 2, w: d, h: d });
  }
  const layout: MapLayout = { points, labels: [], groups, hq, taken, obstacles: { boxes: nodeBoxes, pts: routePts }, labelCandidates, clusters };
  // Individual pills at the concept-art zoom: try left, right, below, above; skip collisions.
  layout.labels = placeLabels(layout, 1, []);
  for (const l of layout.labels) taken.push(labelBox(l));
  return layout;
}

/** Cluster bubbles at zoom level L, with their boxes in map units (bubbles keep their screen size). */
function bubblesAt(layout: MapLayout, L: number): { cluster: Cluster; box: Box }[] {
  return (layout.clusters.get(L) ?? [])
    .filter((c) => c.members.length > 1)
    .map((c) => {
      const d = bubbleSize(c.members.length) / L;
      return { cluster: c, box: { x: c.x - d / 2, y: c.y - d / 2, w: d, h: d } };
    });
}

/** Zoom-1 box of a label. */
const labelBox = (l: NodeLabel): Box => ({ x: l.x, y: l.y, ...smallPillBox(l.text) });

/** Box a label covers at zoom level L. */
const labelBoxAt = (l: NodeLabel, L: number): Box => scaleAbout(labelBox(l), [l.x + l.origin[0], l.y + l.origin[1]], 1 / L);

/** Place labels not yet in `placed` at zoom level L, clear of `fixed` boxes and of `placed` as seen at L. */
function placeLabels(layout: MapLayout, L: number, placed: NodeLabel[], fixed: Box[] = layout.taken): NodeLabel[] {
  const { points, obstacles } = layout;
  const done = new Set(placed.map((l) => l.text));
  const seen = new BoxGrid(placed.filter((l) => l.minK <= L).map((l) => labelBoxAt(l, L)));
  // Cluster bubbles at this zoom: labels sit beside them, never on them.
  const bubbles = bubblesAt(layout, L);
  const bubbleOf = new Map(bubbles.flatMap((b) => b.cluster.members.map((m) => [m.id, b] as const)));
  const bubbleGrid = new BoxGrid(bubbles.map((b) => b.box));
  const fixedGrid = new BoxGrid(fixed);
  // Symbols keep their screen size when zoomed in, so they shrink in map units.
  const symScale = 1 / Math.max(1, L);
  const symbolGrid = new BoxGrid(obstacles.boxes.map((o) => ({ ...scaleAbout(o, [o.x + o.w / 2, o.y + o.h / 2], symScale), src: o }) as Box));
  const pts = routeGrid(obstacles.pts);
  const out: NodeLabel[] = [];
  for (const c of layout.labelCandidates) {
    if (done.has(c.text)) continue;
    for (const n of c.members) {
      const bubble = bubbleOf.get(n.id);
      const [cx, cy] = bubble ? [bubble.cluster.x, bubble.cluster.y] : points.get(n.id)!;
      const r0 = symbolSize(n.kind) / 2;
      const r = bubble ? bubble.box.w / 2 : r0 * symScale;
      const { w, h } = smallPillBox(c.text);
      const frame = frameFor([cx, cy]);
      const pad = 2 / L;
      // The node's own symbol is not in its label's way.
      const own = (o: Box) => {
        const src = (o as Box & { src: Box }).src;
        return Math.abs(src.x + src.w / 2 - cx) < 0.01 && Math.abs(src.y + src.h / 2 - cy) < 0.01 && Math.abs(src.w - 2 * r0) < 0.01;
      };
      const fits = (b: Box) =>
        within(b, frame) &&
        !symbolGrid.hits(b, pad, own) &&
        !fixedGrid.hits(b, pad) &&
        !seen.hits(b, pad) &&
        !bubbleGrid.hits(b, pad) &&
        !pts.anyInside(b);
      const pick = pillOptions(cx, cy, r, w, h, L).find(fits);
      if (!pick) continue;
      // Keep the zoom-1 box: the pill is counter-scaled about the point nearest its symbol.
      const o = nearestOn(pick, [cx, cy]);
      const base = scaleAbout(pick, o, L);
      const x = L === 1 ? Math.round(base.x) : base.x;
      const y = L === 1 ? Math.round(base.y) : base.y;
      out.push({ nodeId: n.id, text: c.text, x, y, minK: L, origin: [o[0] - x, o[1] - y], weight: c.members.length });
      seen.add(pick);
      break;
    }
  }
  return out;
}

/**
 * Labels for every zoom level. Zooming out keeps only the biggest clusters whose pills
 * (which keep their screen size) still fit; zooming in adds clusters as room appears.
 * Call after all other pills are in `layout.taken`; the concept-art labels are unchanged.
 */
export function withZoomLabels(layout: MapLayout): NodeLabel[] {
  const labelKeys = new Set(layout.labels.map((l) => `${l.x},${l.y}`));
  const fixed = layout.taken.filter((b) => !labelKeys.has(`${b.x},${b.y}`));
  // Placed again now that the scene's pills and captions are known, so none overlap them.
  const base = placeLabels(layout, 1, [], fixed);
  const order = new Map(layout.labelCandidates.map((c, i) => [c.text, i]));

  // Zooming out: walk down the levels; a label survives while it fits beside higher-priority survivors.
  let survivors = [...base].sort((a, b) => order.get(a.text)! - order.get(b.text)!);
  const minK = new Map(base.map((l) => [l.text, 1]));
  for (const L of LABEL_LEVELS.filter((l) => l < 1).reverse()) {
    const kept: { l: NodeLabel; b: Box }[] = [];
    for (const l of survivors) {
      const b = labelBoxAt(l, L);
      const bubbles = bubblesAt(layout, L).filter((x) => !x.cluster.members.some((m) => m.id === l.nodeId));
      if (kept.some((o) => overlaps(b, o.b, 2 / L)) || fixed.some((o) => overlaps(b, o, 2 / L)) || bubbles.some((o) => overlaps(b, o.box, 2 / L))) continue;
      kept.push({ l, b });
      minK.set(l.text, L);
    }
    survivors = kept.map((x) => x.l);
  }
  const all = base.map((l) => ({ ...l, minK: minK.get(l.text)! }));

  // Zooming in: add labels that fit at each higher level.
  for (const L of LABEL_LEVELS.filter((l) => l > 1)) all.push(...placeLabels(layout, L, all, fixed));
  return all;
}
