"use client";

import type { MapLayout } from "@/lib/layout";
import { symbolSize } from "@/lib/layout";
import { size, tierColor } from "@/lib/tokens";
import type { Network } from "@/lib/types";
import { NodeSymbol, Pill } from "./Glyphs";

interface Props {
  network: Network;
  layout: MapLayout;
  onSelect?: (nodeId: string) => void;
  selectedId?: string | null;
}

// Shipping dots sit under everything else, assembly hexagons on top.
const Z: Partial<Record<string, number>> = { port: 0, airport: 0, canal: 0, border: 0, assembly: 2 };

/** Node symbols, label pills, regional group pills, and the Apple Park card. */
export default function NodeLayer({ network, layout, onSelect, selectedId }: Props) {
  const ordered = [...network.nodes].sort((a, b) => (Z[a.kind] ?? 1) - (Z[b.kind] ?? 1));
  return (
    <>
      {ordered.map((n) => {
        if (n.kind === "hq") return null;
        const [x, y] = layout.points.get(n.id)!;
        const s = symbolSize(n.kind);
        if (x < -s || y < -s || x > size.mapW + s || y > size.mapH + s) return null;
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

      {layout.labels.map((l) => (
        <Pill key={`label-${l.nodeId}`} style={{ left: l.x, top: l.y }}>
          {l.text}
        </Pill>
      ))}

      {layout.groups.map((g) => (
        <Pill key={`group-${g.key}`} bg={tierColor[6]} style={{ left: g.x, top: g.y }}>
          {g.text}
        </Pill>
      ))}

      {layout.hq && (
        <div className="hq-card" style={{ left: layout.hq.x, top: layout.hq.y }}>
          APPLE PARK
          <br />
          CUPERTINO
        </div>
      )}
    </>
  );
}
