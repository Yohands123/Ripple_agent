import { color } from "@/lib/tokens";
import type { ForecastSeries, Forecasts } from "@/lib/types";

const W = 344;
const H = 92;
const PAD_TOP = 6;
const PAD_BOTTOM = 18;

const MEDIAN = color.textPrimary;
const BAND = "rgba(241,245,242,0.16)";
const HISTORY = color.textSecondary;
const BASELINE = color.textHeading;

function monthLabel(iso: string): string {
  const [y, m] = iso.split("-").map(Number);
  return `${["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m - 1]} ${String(y).slice(2)}`;
}

/** History, then the forecast median with its 80% band (q10 to q90) next to the seasonal-naive baseline. */
function FanChart({ s }: { s: ForecastSeries }) {
  const dates = [...s.history.map((h) => h.date), ...s.forecast.map((f) => f.date)];
  const uniq = [...new Set(dates)];
  const xi = new Map(uniq.map((d, i) => [d, i]));
  const values = [
    ...s.history.map((h) => h.value),
    ...s.forecast.flatMap((f) => [f.q10, f.q90]),
    ...s.baseline.map((b) => b.value),
  ];
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const x = (d: string) => (uniq.length < 2 ? W / 2 : ((xi.get(d) ?? 0) * W) / (uniq.length - 1));
  const y = (v: number) => (hi === lo ? H / 2 : PAD_TOP + (1 - (v - lo) / (hi - lo)) * (H - PAD_TOP - PAD_BOTTOM));
  const path = (pts: [string, number][]) => pts.map(([d, v], i) => `${i ? "L" : "M"}${x(d).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");

  // Forecast lines start from the last observed point so they join the history.
  const last = s.history[s.history.length - 1];
  const anchor: [string, number][] = last ? [[last.date, last.value]] : [];
  const band =
    s.forecast.length > 0
      ? `${path([...anchor, ...s.forecast.map((f) => [f.date, f.q90] as [string, number])])} ${[...s.forecast]
          .reverse()
          .map((f) => `L${x(f.date).toFixed(1)} ${y(f.q10).toFixed(1)}`)
          .join(" ")}${last ? ` L${x(last.date).toFixed(1)} ${y(last.value).toFixed(1)}` : ""} Z`
      : "";
  const first = uniq[0];
  const end = uniq[uniq.length - 1];

  return (
    <svg
      width="100%"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`${s.label} in ${s.unit}: last value ${last?.value ?? "unknown"}, forecast median ${s.forecast.map((f) => f.q50).join(", ")}, 80% range ${s.forecast
        .map((f) => `${f.q10} to ${f.q90}`)
        .join("; ")}, baseline ${s.baseline.map((b) => b.value).join(", ")}.`}
      style={{ display: "block", overflow: "visible" }}
      data-fan={s.id}
    >
      {band && <path d={band} fill={BAND} />}
      <path d={path(s.history.map((h) => [h.date, h.value]))} fill="none" stroke={HISTORY} strokeWidth={2} />
      <path d={path([...anchor, ...s.baseline.map((b) => [b.date, b.value] as [string, number])])} fill="none" stroke={BASELINE} strokeWidth={1.5} strokeDasharray="4 4" />
      <path d={path([...anchor, ...s.forecast.map((f) => [f.date, f.q50] as [string, number])])} fill="none" stroke={MEDIAN} strokeWidth={2.5} />
      {first && (
        <text x={0} y={H - 2} fill={color.textHeading} fontSize={11}>
          {monthLabel(first)}
        </text>
      )}
      {end && end !== first && (
        <text x={W} y={H - 2} fill={color.textHeading} fontSize={11} textAnchor="end">
          {monthLabel(end)}
        </text>
      )}
    </svg>
  );
}

/** Input cost forecasts from forecasts.json; a quiet note when the file is missing or empty. */
export default function ForecastSection({ forecasts }: { forecasts: Forecasts | null }) {
  return (
    <section>
      <h2 className="panel-heading">INPUT COST FORECASTS</h2>
      {!forecasts || forecasts.series.length === 0 ? (
        <div className="panel-note">Cost forecasts are not available yet.</div>
      ) : (
        <div className="fan-list">
          {forecasts.series.map((s) => (
            <div key={s.id} className="fan">
              <div className="fan-title">
                {s.label} <span className="fan-unit">{s.unit}</span>
              </div>
              <FanChart s={s} />
              <div className="fan-legend">
                <span>
                  <span className="fan-swatch" style={{ background: MEDIAN }} /> Forecast
                </span>
                <span>
                  <span className="fan-swatch band" /> 80% range
                </span>
                <span>
                  <span className="fan-swatch dashed" /> Seasonal naive
                </span>
              </div>
              <div className="panel-tiny">
                Error (MASE) {s.metrics.mase.toFixed(2)} vs {s.metrics.baselineMase.toFixed(2)} for the baseline; the 80% range held{" "}
                {Math.round(s.metrics.coverage80 * 100)}% of past values.{" "}
                {s.source.url ? (
                  <a href={s.source.url} target="_blank" rel="noreferrer">
                    {s.source.title}
                  </a>
                ) : (
                  s.source.title
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
