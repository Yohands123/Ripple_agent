"use client";

import { lineGeometry } from "@/lib/georoute";
import { labelLevel } from "@/lib/layout";
import { edgeLine, nodeIndex } from "@/lib/routes";
import type { MoneyLine } from "@/lib/scene";
import { color, route as R, tierColorOf } from "@/lib/tokens";
import type { Trace } from "@/lib/trace";
import type { Network, NetworkEdge, NetworkNode } from "@/lib/types";
import { useZoom } from "./MapStage";
import { useReducedMotion } from "./MoverLayer";

/** Seconds a pulse takes to cross one step of the trace. */
const STEP = 0.8;
const PAUSE = 0.8;
const MAX_PULSES = 160;

interface Line {
  key: string;
  d: string;
  color: string;
  dashed: boolean;
  width: number;
  /** Which step of the pulse sequence it belongs to (0 first). */
  step: number;
  kind: "upstream" | "downstream" | "money";
}

/** A supply link has no transport geometry: it is drawn as a straight line between the two places. */
function supplyLine(e: NetworkEdge, nodes: Map<string, NetworkNode>): string {
  const a = nodes.get(e.from);
  const b = nodes.get(e.to);
  if (!a || !b) return "";
  return lineGeometry([[a.lon, a.lat], [b.lon, b.lat]], "straight").d;
}

/**
 * The traced paths drawn bright over the dimmed map, with pulses travelling along them:
 * upstream first (from the furthest suppliers in towards the clicked node), then downstream.
 */
export default function TraceLayer({ network, trace, money }: { network: Network; trace: Trace; money: MoneyLine[] }) {
  const z = 1 / Math.max(1, labelLevel(useZoom()));
  const reduced = useReducedMotion();
  const nodes = nodeIndex(network);

  const lines: Line[] = [];
  // Upstream, furthest hop first, so pulses arrive at the clicked node last.
  const up = [...trace.upstreamEdges].reverse();
  up.forEach((edges, i) =>
    edges.forEach((e) => {
      const d = supplyLine(e, nodes);
      const from = nodes.get(e.from);
      if (d) lines.push({ key: `up-${e.id}`, d, color: tierColorOf(from?.tier ?? e.carriesTier), dashed: e.status === "inferred", width: 2, step: i, kind: "upstream" });
    }),
  );
  trace.downstreamEdges.forEach((edges, j) =>
    edges.forEach((e) => {
      const d = e.relation === "supply" || !e.mode ? supplyLine(e, nodes) : (edgeLine(e, nodes)?.d ?? "");
      if (d) lines.push({ key: `down-${e.id}`, d, color: color.pillLight, dashed: e.status === "inferred", width: e.mode === "air" ? 2.4 : 3.5, step: up.length + j, kind: "downstream" });
    }),
  );
  const steps = up.length + trace.downstreamEdges.length + (trace.money ? 1 : 0);
  if (trace.money) {
    for (const m of money.filter((m) => m.kind === "in" && m.d)) lines.push({ key: `money-${m.id}`, d: m.d, color: color.moneyIn, dashed: false, width: R.moneyInWidth, step: steps - 1, kind: "money" });
  }
  const cycle = steps * STEP + PAUSE;

  return (
    <g data-layer="trace" data-trace={trace.root}>
      {lines.map((l) => (
        <path
          key={l.key}
          d={l.d}
          fill="none"
          stroke={l.color}
          strokeWidth={l.width * z}
          strokeDasharray={l.dashed ? `${8 * z} ${6 * z}` : undefined}
          strokeLinecap="round"
          data-trace-line={l.kind}
        />
      ))}
      {!reduced &&
        lines.slice(0, MAX_PULSES).map((l) => {
          // Each pulse moves only during its own step of the cycle, then waits for the next cycle.
          const t0 = (l.step * STEP) / cycle;
          const t1 = ((l.step + 1) * STEP) / cycle;
          const keyTimes = `0;${t0.toFixed(4)};${t1.toFixed(4)};1`;
          return (
            <circle key={`pulse-${l.key}`} r={4.5 * z} fill={l.kind === "money" ? color.moneyIn : "#FFFFFF"} opacity={0} data-pulse={l.kind}>
              <animateMotion dur={`${cycle}s`} repeatCount="indefinite" path={l.d} keyPoints="0;0;1;1" keyTimes={keyTimes} calcMode="linear" />
              <animate attributeName="opacity" dur={`${cycle}s`} repeatCount="indefinite" values="0;0;1;1;0;0" keyTimes={`0;${t0.toFixed(4)};${(t0 + 0.0001).toFixed(4)};${t1.toFixed(4)};${Math.min(0.9999, t1 + 0.0001).toFixed(4)};1`} />
            </circle>
          );
        })}
    </g>
  );
}
