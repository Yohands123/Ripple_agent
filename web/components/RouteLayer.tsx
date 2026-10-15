"use client";

import { useMemo } from "react";
import { labelLevel } from "@/lib/layout";
import type { MoneyLine, RouteDraw } from "@/lib/scene";
import { color, route as R } from "@/lib/tokens";
import { useZoom } from "./MapStage";

// Inferred links are dashed versions of their normal style (docs/design-spec.md, Routes).
const INFERRED_SEA_DASH = "26 13";
const INFERRED_LINE_DASH = "12 8";
const INFERRED_AIR_DASH = "5 8";

/** Hierarchy: the backbone at full strength, other inferred routes thinner at half strength, supplier links faint. */
const RANK = {
  backbone: { opacity: 1, width: 1 },
  inferred: { opacity: 0.5, width: 0.6 },
  supplier: { opacity: 0.25, width: 0.4 },
  context: { opacity: 0.25, width: 0.4 },
} as const;

/**
 * Zoomed in, lines keep their concept-art screen widths and dash lengths (z = 1 / zoom);
 * zoomed out they thin with the map.
 */
type Scale = { w: (n: number) => number; dash: (s: string | undefined) => string | undefined };

function scaler(z: number): Scale {
  return {
    w: (n) => n * z,
    dash: (s) => (s && z !== 1 ? s.split(/\s+/).map((v) => String(Number(v) * z)).join(" ") : s),
  };
}

function Route({ r, sc }: { r: RouteDraw; sc: Scale }) {
  const rank = RANK[r.rank];
  return (
    <g opacity={rank.opacity} data-rank={r.rank} data-mode={r.edge.mode} data-count={r.count} className="route">
      <RouteBody r={r} w={rank.width} sc={sc} />
    </g>
  );
}

function RouteBody({ r, w, sc }: { r: RouteDraw; w: number; sc: Scale }) {
  const { edge, d } = r;
  const inferred = edge.status === "inferred";
  const common = { d, fill: "none", strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

  if (r.state === "blocked") {
    return (
      <g data-route={r.id} data-state="blocked" opacity={R.blockedOpacity} className="enter-grey ripple-red">
        <path
          {...common}
          stroke={color.blocked}
          strokeWidth={sc.w(edge.mode === "air" ? R.airWidth : 6)}
          strokeDasharray={edge.mode === "air" ? sc.dash(R.airDash) : undefined}
        />
        {edge.mode === "sea" && <path d={d} fill="none" stroke={color.ocean} strokeWidth={sc.w(R.seaTickWidth)} strokeDasharray={sc.dash(R.seaTickDash)} />}
      </g>
    );
  }

  if (r.state === "detour") {
    return (
      <path
        data-route={r.id}
        data-state="detour"
        className="enter-grey"
        {...common}
        stroke={r.color}
        strokeWidth={sc.w(R.detourWidth)}
        strokeDasharray={sc.dash(R.detourDash)}
      />
    );
  }

  switch (edge.mode) {
    case "air":
      return (
        <path
          data-route={r.id}
          data-state={r.state}
          {...common}
          stroke={r.color}
          strokeWidth={sc.w((r.width ?? (r.state === "expedited" ? R.airWidthExpedited : R.airWidth)) * w)}
          strokeDasharray={sc.dash(inferred ? INFERRED_AIR_DASH : R.airDash)}
        />
      );
    case "road":
      return (
        <g data-route={r.id} data-state={r.state}>
          <path {...common} stroke={r.color} strokeWidth={sc.w(5 * w)} strokeDasharray={sc.dash(inferred ? INFERRED_LINE_DASH : undefined)} />
          {w === 1 && <path d={d} fill="none" stroke={color.ocean} strokeWidth={sc.w(1)} strokeDasharray={sc.dash(inferred ? INFERRED_LINE_DASH : undefined)} />}
        </g>
      );
    case "rail":
      return (
        <g data-route={r.id} data-state={r.state}>
          <path {...common} stroke={r.color} strokeWidth={sc.w(3)} strokeDasharray={sc.dash(inferred ? INFERRED_LINE_DASH : undefined)} />
          <path d={d} fill="none" stroke={r.color} strokeWidth={sc.w(9)} strokeDasharray={sc.dash("2 8")} />
        </g>
      );
    default:
      return (
        <g data-route={r.id} data-state={r.state}>
          <path {...common} stroke={r.color} strokeWidth={sc.w(R.seaWidth * w)} strokeDasharray={sc.dash(inferred ? INFERRED_SEA_DASH : undefined)} />
          <path d={d} fill="none" stroke={color.ocean} strokeWidth={sc.w(R.seaTickWidth)} strokeDasharray={sc.dash(R.seaTickDash)} opacity={0.9} />
        </g>
      );
  }
}

export default function RouteLayer({ routes, money }: { routes: RouteDraw[]; money: MoneyLine[] }) {
  // Widths follow the zoom level (not every zoom step), so zooming stays smooth.
  const level = labelLevel(useZoom());
  return useMemo(() => <Routes routes={routes} money={money} z={1 / Math.max(1, level)} />, [routes, money, level]);
}

function Routes({ routes, money, z }: { routes: RouteDraw[]; money: MoneyLine[]; z: number }) {
  const sc = scaler(z);
  const under = routes.filter((r) => r.state !== "detour");
  const over = routes.filter((r) => r.state === "detour");
  return (
    <g data-layer="routes">
      {money
        .filter((m) => m.d)
        .map((m) => (
          <path
            key={m.id}
            data-money={m.kind}
            d={m.d}
            fill="none"
            stroke={m.kind === "in" ? color.moneyIn : color.moneyOut}
            strokeWidth={sc.w(m.kind === "in" ? R.moneyInWidth : R.moneyOutWidth)}
            strokeLinecap="round"
          />
        ))}
      {under.map((r) => (
        <Route key={r.id} r={r} sc={sc} />
      ))}
      {over.map((r) => (
        <Route key={r.id} r={r} sc={sc} />
      ))}
    </g>
  );
}
