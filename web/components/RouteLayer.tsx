import type { MoneyLine, RouteDraw } from "@/lib/scene";
import { color, route as R } from "@/lib/tokens";

// Inferred links are dashed versions of their normal style (docs/design-spec.md, Routes).
const INFERRED_SEA_DASH = "26 13";
const INFERRED_LINE_DASH = "12 8";
const INFERRED_AIR_DASH = "5 8";

function Route({ r }: { r: RouteDraw }) {
  const { edge, d } = r;
  const inferred = edge.status === "inferred";
  const common = { d, fill: "none", strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

  if (r.state === "blocked") {
    return (
      <g data-route={r.id} data-state="blocked" opacity={R.blockedOpacity}>
        <path {...common} stroke={color.blocked} strokeWidth={edge.mode === "air" ? R.airWidth : 6} strokeDasharray={edge.mode === "air" ? R.airDash : undefined} />
        {edge.mode === "sea" && <path d={d} fill="none" stroke={color.ocean} strokeWidth={R.seaTickWidth} strokeDasharray={R.seaTickDash} />}
      </g>
    );
  }

  if (r.state === "detour") {
    return <path data-route={r.id} data-state="detour" {...common} stroke={r.color} strokeWidth={R.detourWidth} strokeDasharray={R.detourDash} />;
  }

  switch (edge.mode) {
    case "air":
      return (
        <path
          data-route={r.id}
          data-state={r.state}
          {...common}
          stroke={r.color}
          strokeWidth={r.state === "expedited" ? R.airWidthExpedited : R.airWidth}
          strokeDasharray={inferred ? INFERRED_AIR_DASH : R.airDash}
        />
      );
    case "road":
      return (
        <g data-route={r.id} data-state={r.state}>
          <path {...common} stroke={r.color} strokeWidth={5} strokeDasharray={inferred ? INFERRED_LINE_DASH : undefined} />
          <path d={d} fill="none" stroke={color.ocean} strokeWidth={1} strokeDasharray={inferred ? INFERRED_LINE_DASH : undefined} />
        </g>
      );
    case "rail":
      return (
        <g data-route={r.id} data-state={r.state}>
          <path {...common} stroke={r.color} strokeWidth={3} strokeDasharray={inferred ? INFERRED_LINE_DASH : undefined} />
          <path d={d} fill="none" stroke={r.color} strokeWidth={9} strokeDasharray="2 8" />
        </g>
      );
    default:
      return (
        <g data-route={r.id} data-state={r.state}>
          <path {...common} stroke={r.color} strokeWidth={R.seaWidth} strokeDasharray={inferred ? INFERRED_SEA_DASH : undefined} />
          <path d={d} fill="none" stroke={color.ocean} strokeWidth={R.seaTickWidth} strokeDasharray={R.seaTickDash} opacity={0.9} />
        </g>
      );
  }
}

export default function RouteLayer({ routes, money }: { routes: RouteDraw[]; money: MoneyLine[] }) {
  const under = routes.filter((r) => r.state !== "detour");
  const over = routes.filter((r) => r.state === "detour");
  return (
    <g data-layer="routes">
      {money.map((m) => (
        <path
          key={m.id}
          data-money={m.kind}
          d={m.d}
          fill="none"
          stroke={m.kind === "in" ? color.moneyIn : color.moneyOut}
          strokeWidth={m.kind === "in" ? R.moneyInWidth : R.moneyOutWidth}
          strokeLinecap="round"
        />
      ))}
      {under.map((r) => (
        <Route key={r.id} r={r} />
      ))}
      {over.map((r) => (
        <Route key={r.id} r={r} />
      ))}
    </g>
  );
}
