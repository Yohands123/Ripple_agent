"use client";

import { lineGeometry } from "@/lib/georoute";
import { nodeIndex } from "@/lib/routes";
import { HOP_DELAY, type Ripple } from "@/lib/ripple";
import { color } from "@/lib/tokens";
import type { Network } from "@/lib/types";
import { useZoom } from "./MapStage";
import { useReducedMotion } from "./MoverLayer";

/** Waves drawn per hop at most (the highest-risk suppliers first). */
const MAX_WAVES = 220;

/**
 * The wave of a dropped disruption: lines draw outward from the places reached to the
 * suppliers they reach, hop by hop, then fade. Under reduced motion only the final state
 * (suppliers colored by risk) is shown, so nothing is drawn here.
 */
export default function RippleLayer({ network, ripple, risk }: { network: Network; ripple: Ripple; risk: Map<string, number> }) {
  const reduced = useReducedMotion();
  const z = 1 / Math.max(1, useZoom());
  if (reduced) return null;
  const nodes = nodeIndex(network);
  const byHop = new Map<number, typeof ripple.links>();
  for (const l of ripple.links) byHop.set(l.hop, [...(byHop.get(l.hop) ?? []), l]);
  const shown = [...byHop.values()].flatMap((list) => [...list].sort((a, b) => (risk.get(b.to) ?? 0) - (risk.get(a.to) ?? 0)).slice(0, MAX_WAVES));
  return (
    <g data-layer="ripple">
      {shown.map((l) => {
        const a = nodes.get(l.from);
        const b = nodes.get(l.to);
        if (!a || !b) return null;
        const { d } = lineGeometry([[a.lon, a.lat], [b.lon, b.lat]], "straight");
        return (
          <path
            key={`${l.edge.id}-${l.to}`}
            d={d}
            pathLength={1}
            className="ripple-wave"
            data-hop={l.hop}
            fill="none"
            stroke={color.alert}
            strokeWidth={2 * z}
            strokeLinecap="round"
            style={{ animationDelay: `${l.hop * HOP_DELAY}s` }}
          />
        );
      })}
    </g>
  );
}
