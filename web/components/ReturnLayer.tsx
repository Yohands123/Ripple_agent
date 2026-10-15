"use client";

import { useMemo } from "react";
import { labelLevel } from "@/lib/layout";
import { edgeLine, isReturn, nodeIndex } from "@/lib/routes";
import { tierColor } from "@/lib/tokens";
import type { Network } from "@/lib/types";
import { useZoom } from "./MapStage";

/** Dash and gap of a return route, screen px at zoom 1. */
const DASH = 7;
const GAP = 6;

/**
 * Return routes: sales regions to repair and recycling sites, and recovered metals back
 * to refineries. Pink (tier 7), dashed because every one is inferred, with the dashes
 * flowing along the route, against the usual direction of goods. Under reduced motion
 * the dashes stand still (globals.css).
 */
export default function ReturnLayer({ network }: { network: Network }) {
  const level = labelLevel(useZoom());
  return useMemo(() => {
    const z = 1 / Math.max(1, level);
    const nodes = nodeIndex(network);
    const lines = network.edges.filter(isReturn).flatMap((e) => {
      const g = edgeLine(e, nodes);
      return g ? [{ e, d: g.d }] : [];
    });
    return (
      <g data-layer="returns">
        {lines.map(({ e, d }) => (
          <path
            key={e.id}
            d={d}
            fill="none"
            stroke={tierColor[7]}
            strokeWidth={2.4 * z}
            strokeDasharray={`${DASH * z} ${GAP * z}`}
            strokeLinecap="round"
            opacity={0.85}
            className="return-route"
            style={{ ["--flow" as string]: `${-(DASH + GAP) * z}` }}
            data-return={e.id}
            data-stage={e.returnStage}
          />
        ))}
      </g>
    );
  }, [network, level]);
}
