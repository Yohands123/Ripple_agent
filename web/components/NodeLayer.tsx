"use client";

import type { MapLayout, NodeLabel } from "@/lib/layout";
import { labelLevel, symbolSize } from "@/lib/layout";
import { tierColor } from "@/lib/tokens";
import type { Network } from "@/lib/types";
import { NodeSymbol, Pill } from "./Glyphs";
import { useZoom } from "./MapStage";

/**
 * Node labels keep their screen size while the map zooms, so only the labels that fit at
 * the current zoom show: the biggest clusters when zoomed out, more as you zoom in.
 */
function NodeLabels({ labels }: { labels: NodeLabel[] }) {
  const level = labelLevel(useZoom());
  return (
    <>
      {labels
        .filter((l) => l.minK <= level)
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
  selectedId?: string | null;
  /** Replacement text for regional group pills, keyed by continent. */
  groupText?: Record<string, string>;
}

// Shipping dots sit under everything else, assembly hexagons on top.
const Z: Partial<Record<string, number>> = { port: 0, airport: 0, canal: 0, border: 0, assembly: 2 };

/** Node symbols, label pills, regional group pills, and the Apple Park card. */
export default function NodeLayer({ network, layout, onSelect, selectedId, groupText }: Props) {
  // Sites with a known or inferred tier draw over grey (unknown-tier) sites.
  const known = (t: number | null) => (t == null ? 0 : 1);
  const ordered = [...network.nodes].sort((a, b) => (Z[a.kind] ?? 1) - (Z[b.kind] ?? 1) || known(a.tier) - known(b.tier));
  return (
    <>
      {ordered.map((n) => {
        if (n.kind === "hq" || n.waypoint) return null;
        const [x, y] = layout.points.get(n.id)!;
        const s = symbolSize(n.kind);
        const label = `${n.name}, ${n.region}`;
        return (
          <button
            key={n.id}
            type="button"
            className={`node${selectedId === n.id ? " node-selected" : ""}`}
            data-node-id={n.id}
            data-kind={n.kind}
            aria-label={label}
            title={label}
            onClick={() => onSelect?.(n.id)}
            style={{ left: x - s / 2, top: y - s / 2, width: s, height: s }}
          >
            <NodeSymbol kind={n.kind} tier={n.tier} size={s} />
          </button>
        );
      })}

      <NodeLabels labels={layout.labels} />

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
