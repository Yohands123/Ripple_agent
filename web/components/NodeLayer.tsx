"use client";

import { useMemo, type CSSProperties } from "react";
import { bubbleSize, COUNTRY_K, isClusterable, type Cluster } from "@/lib/declutter";
import type { MapLayout, NodeLabel } from "@/lib/layout";
import { labelLevel, symbolSize } from "@/lib/layout";
import { tierColor, tierColorOf } from "@/lib/tokens";
import type { Network, NetworkNode } from "@/lib/types";
import { NodeSymbol, Pill } from "./Glyphs";
import { useStage, useZoom } from "./MapStage";

/** How a node is drawn for the trace or the disruption ripple. */
export interface NodeLook {
  /** CSS classes, e.g. "dimmed" or "traced". */
  className?: string;
  /** `upstream` or `downstream` when the node is on a trace. */
  traced?: "upstream" | "downstream" | "self";
  /** Fill override (e.g. predicted risk), with the delay before it appears, in seconds. */
  fill?: string;
  delay?: number;
}

/**
 * Node labels keep their screen size while the map zooms, so only the labels that fit at
 * the current zoom show: the biggest clusters when zoomed out, more as you zoom in.
 */
function NodeLabels({ labels, hidden, level }: { labels: NodeLabel[]; hidden: (id: string) => boolean; level: number }) {
  return (
    <>
      {labels
        .filter((l) => l.minK <= level && !hidden(l.nodeId))
        .map((l) => (
          <Pill
            key={`label-${l.nodeId}`}
            className="node-label"
            data-label={l.text}
            style={{ left: l.x, top: l.y, transformOrigin: `${l.origin[0]}px ${l.origin[1]}px` }}
          >
            {l.text}
          </Pill>
        ))}
    </>
  );
}

interface Props {
  network: Network;
  layout: MapLayout;
  onSelect?: (nodeId: string) => void;
  onHover?: (nodeId: string | null) => void;
  selectedId?: string | null;
  /** Replacement text for regional group pills, keyed by continent. */
  groupText?: Record<string, string>;
  /** Hide supplier sites (the Suppliers layer toggle). */
  hideSuppliers?: boolean;
  /** Per-node look for the trace and the ripple. */
  look?: (id: string) => NodeLook | undefined;
}

// Mining regions are soft glows under everything; shipping dots under the rest; assembly hexagons on top.
const Z: Partial<Record<string, number>> = { mine: -1, port: 0, airport: 0, canal: 0, chokepoint: 0, border: 0, assembly: 2 };

/** A cluster of supplier sites: a bubble with a count, colored by the tier most of them have. Click to zoom in. */
function Bubble({ c, look, onHover, k }: { c: Cluster; look?: NodeLook; onHover?: (id: string | null) => void; k: number }) {
  const { goTo } = useStage();
  const d = bubbleSize(c.members.length);
  const fill = look?.fill ?? tierColorOf(c.tier);
  const style: CSSProperties = {
    left: c.x - d / 2,
    top: c.y - d / 2,
    width: d,
    height: d,
    background: fill,
    ...(look?.delay != null ? ({ "--ripple-delay": `${look.delay}s` } as CSSProperties) : {}),
  };
  return (
    <button
      type="button"
      className={`cluster${look?.className ? ` ${look.className}` : ""}`}
      data-cluster={c.members.length}
      data-traced={look?.traced}
      aria-label={`${c.members.length} supplier sites. Zoom in to see them.`}
      title={`${c.members.length} supplier sites`}
      style={style}
      onClick={() => goTo([c.x, c.y], Math.max(k * 2.2, k < 1.5 ? 2.4 : COUNTRY_K))}
      onPointerEnter={() => onHover?.(c.members[0].id)}
      onPointerLeave={() => onHover?.(null)}
    >
      {c.members.length}
    </button>
  );
}

/** Node symbols (supplier sites clustered until zoomed into a country), label pills, regional group pills, and the Apple Park card. */
/**
 * Sites placed at the same point (e.g. several companies at one province's centre) fan out
 * in a small ring when zoomed into a country, so each can be seen and clicked.
 */
function fanOut(nodes: NetworkNode[], points: Map<string, [number, number]>, k: number): Map<string, [number, number]> {
  const out = new Map<string, [number, number]>();
  if (k < COUNTRY_K) return out;
  const at = new Map<string, NetworkNode[]>();
  for (const n of nodes) {
    if (!isClusterable(n)) continue;
    const [x, y] = points.get(n.id)!;
    const key = `${x.toFixed(1)},${y.toFixed(1)}`;
    at.set(key, [...(at.get(key) ?? []), n]);
  }
  for (const group of at.values()) {
    if (group.length < 2) continue;
    // Rings of up to 8, 22 screen px apart.
    group.forEach((n, i) => {
      const ring = Math.floor(i / 8) + 1;
      const inRing = Math.min(8, group.length - (ring - 1) * 8);
      const a = ((i % 8) / inRing) * 2 * Math.PI;
      const r = (22 * ring) / k;
      out.set(n.id, [Math.cos(a) * r, Math.sin(a) * r]);
    });
  }
  return out;
}

export default function NodeLayer(props: Props) {
  // Redrawn when the zoom level changes, not on every zoom step.
  const level = labelLevel(useZoom());
  const { network, layout, onSelect, onHover, selectedId, groupText, hideSuppliers, look } = props;
  return useMemo(
    () => <Nodes {...{ network, layout, onSelect, onHover, selectedId, groupText, hideSuppliers, look }} level={level} />,
    [network, layout, onSelect, onHover, selectedId, groupText, hideSuppliers, look, level],
  );
}

function Nodes({ network, layout, onSelect, onHover, selectedId, groupText, hideSuppliers = false, look, level }: Props & { level: number }) {
  const k = level;
  const fan = fanOut(network.nodes, layout.points, k);
  const clusters = layout.clusters.get(level) ?? [];
  const bubbles = clusters.filter((c) => c.members.length > 1);
  const inBubble = new Set(bubbles.flatMap((c) => c.members.map((m) => m.id)));
  // A bubble takes the look of its most prominent member (e.g. the highest predicted risk).
  const bubbleLook = (c: Cluster): NodeLook | undefined => {
    if (!look) return undefined;
    const looks = c.members.map((m) => look(m.id)).filter((l): l is NodeLook => Boolean(l));
    // The highest-risk member's color: on the risk ramp, the lower the green channel, the redder.
    return looks.find((l) => l.traced) ?? looks.filter((l) => l.fill).sort((a, b) => greenOf(a.fill!) - greenOf(b.fill!))[0] ?? looks[0];
  };

  const shown = (n: NetworkNode) => n.kind !== "hq" && !n.waypoint && !inBubble.has(n.id) && !(hideSuppliers && isClusterable(n));
  const ordered = [...network.nodes].filter(shown).sort((a, b) => (Z[a.kind] ?? 1) - (Z[b.kind] ?? 1) || known(a.tier) - known(b.tier));
  const hidden = (id: string) => {
    const n = network.nodes.find((x) => x.id === id);
    return Boolean(n && hideSuppliers && isClusterable(n));
  };

  return (
    <>
      {ordered.map((n) => {
        const [px, py] = layout.points.get(n.id)!;
        const [dx, dy] = fan.get(n.id) ?? [0, 0];
        const [x, y] = [px + dx, py + dy];
        const s = symbolSize(n.kind);
        const label = `${n.name}, ${n.region}`;
        const l = look?.(n.id);
        return (
          <button
            key={n.id}
            type="button"
            className={`node${selectedId === n.id ? " node-selected" : ""}${l?.className ? ` ${l.className}` : ""}`}
            data-node-id={n.id}
            data-kind={n.kind}
            data-traced={l?.traced}
            aria-label={label}
            title={label}
            onClick={() => onSelect?.(n.id)}
            onPointerEnter={() => onHover?.(n.id)}
            onPointerLeave={() => onHover?.(null)}
            style={{ left: x - s / 2, top: y - s / 2, width: s, height: s, ...(l?.delay != null ? ({ "--ripple-delay": `${l.delay}s` } as CSSProperties) : {}) }}
          >
            <NodeSymbol kind={n.kind} tier={n.tier} size={s} fill={l?.fill} />
          </button>
        );
      })}

      {!hideSuppliers && bubbles.map((c) => <Bubble key={c.id} c={c} look={bubbleLook(c)} onHover={onHover} k={k} />)}

      <NodeLabels labels={layout.labels} hidden={hidden} level={level} />

      {layout.groups.map((g) => (
        <Pill key={`group-${g.key}`} bg={tierColor[6]} style={{ left: g.x, top: g.y }}>
          {groupText?.[g.key] ?? g.text}
        </Pill>
      ))}

      {layout.hq && (
        <div className="hq-card" data-hq="real" style={{ left: layout.hq.x, top: layout.hq.y }}>
          APPLE PARK
          <br />
          CUPERTINO
        </div>
      )}
    </>
  );
}

/** Green channel of an rgb() color: lower is redder on the risk ramp. */
const greenOf = (c: string) => Number(c.match(/\d+/g)?.[1] ?? 255);

// Sites with a known or inferred tier draw over grey (unknown-tier) sites.
const known = (t: number | null) => (t == null ? 0 : 1);
