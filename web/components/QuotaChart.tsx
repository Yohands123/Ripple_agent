import { color, tierColor } from "@/lib/tokens";

const W = 344;
const H = 118;
const TOP = 24;
const BOTTOM = 92;

interface Props {
  target: number[];
  noAction: number[];
  withPlan: number[];
}

/** Dashed gold quota, grey no-action line, green with-plan line, red shaded gap. */
export default function QuotaChart({ target, noAction, withPlan }: Props) {
  const n = target.length;
  if (n === 0) return <div className="panel-note">No quota data in this scenario.</div>;
  const hi = Math.max(...target, ...withPlan, ...noAction);
  const lo = Math.min(...noAction, ...withPlan);
  const x = (i: number) => (n === 1 ? W / 2 : (i * W) / (n - 1));
  const y = (v: number) => (hi === lo ? TOP : BOTTOM - ((v - lo) / (hi - lo)) * (BOTTOM - TOP));
  const line = (vals: number[]) => vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const gap = `${line(noAction)} ${target
    .map((v, i) => `L${x(n - 1 - i).toFixed(1)} ${y(target[n - 1 - i]).toFixed(1)}`)
    .join(" ")} Z`;
  const mid = Math.floor((n - 1) / 2);
  const ticks = n > 2 ? [0, mid, n - 1] : [...Array(n).keys()];

  return (
    <>
      <svg
        width="100%"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Weekly output against quota over ${n} weeks. With plan: ${withPlan.join(", ")}. No action: ${noAction.join(", ")}. Quota: ${target.join(", ")}.`}
        style={{ display: "block", overflow: "visible" }}
      >
        <path d={gap} fill="rgba(214,69,61,0.28)" />
        <path d={line(target)} fill="none" stroke={color.moneyIn} strokeWidth={2} strokeDasharray="5 5" />
        <path d={line(noAction)} fill="none" stroke={color.textSecondary} strokeWidth={2} />
        <path d={line(withPlan)} fill="none" stroke={tierColor[6]} strokeWidth={3} data-line="with-plan" />
        {ticks.map((i) => (
          <text
            key={i}
            x={x(i)}
            y={114}
            fill={color.textHeading}
            fontSize={11}
            textAnchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"}
          >
            Wk {i + 1}
          </text>
        ))}
        <text x={W} y={16} fill={color.moneyIn} fontSize={11} textAnchor="end">
          Quota
        </text>
      </svg>
      <div className="chart-legend">
        <div>
          <span style={{ color: tierColor[6], fontWeight: 800 }}>━</span> With plan
        </div>
        <div>
          <span style={{ color: color.textSecondary, fontWeight: 800 }}>━</span> No action
        </div>
      </div>
    </>
  );
}
