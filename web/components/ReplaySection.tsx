"use client";

import type { Metrics, Scenario } from "@/lib/types";

interface Props {
  scenario: Scenario;
  metrics: Metrics | null;
  day: number;
  totalDays: number;
  onDay: (day: number) => void;
}

const f2 = (n: number) => n.toFixed(2);
const range = (r: [number, number]) => `${f2(r[0])} to ${f2(r[1])}`;

/** Timeline scrubber for replaying an event, with the model's backtest results. */
export default function ReplaySection({ scenario, metrics, day, totalDays, onDay }: Props) {
  const event = metrics?.loeo.find((e) => e.eventId === scenario.id);
  const excluded = metrics?.excludedFromMetrics?.find((e) => e.eventId === scenario.id);
  // Older files call the distance baseline `baselineAuc`; newer ones add `distanceAuc` and a separate comparison model.
  const distance = (e: { baselineAuc: number; distanceAuc?: number }) => e.distanceAuc ?? e.baselineAuc;
  const comparison = (e: { baselineAuc: number; distanceAuc?: number }) => (e.distanceAuc != null ? e.baselineAuc : null);
  const overallDistance = metrics ? (metrics.overall.distanceAuc ?? metrics.overall.baselineAuc) : null;

  return (
    <section>
      <h2 className="panel-heading">REPLAY THE EVENT</h2>
      <div className="replay">
        <input
          type="range"
          min={1}
          max={totalDays}
          step={1}
          value={day}
          onChange={(e) => onDay(Number(e.target.value))}
          aria-label="Day of the event"
          aria-valuetext={`Day ${day} of ${totalDays}`}
          className="replay-range"
        />
        <div className="replay-day">
          Day {day} of {totalDays}
        </div>
      </div>
      <div className="replay-legend">
        <span className="marker-key predicted" /> Predicted hit
        <span className="marker-key actual-hit" /> Actual hit
        <span className="marker-key actual-miss" /> No hit
      </div>
      {scenario.actual.length === 0 ? (
        <div className="panel-tiny">No actual outcomes recorded for this event.</div>
      ) : day < totalDays ? (
        <div className="panel-tiny">Actual outcomes appear on the last day.</div>
      ) : null}
      {metrics && event && (
        <div className="model-result" data-result="event">
          Model tested on this event without training on it: AUC {f2(event.auc)}, against {f2(distance(event))} for distance alone
          {comparison(event) != null && <> and {f2(comparison(event)!)} for a simple logistic model</>}.
          {distance(event) > event.auc && " Distance alone did better here."} Across {metrics.events} events: AUC {range(metrics.overall.auc)} (95%
          interval), against {range(overallDistance!)} for distance alone.
        </div>
      )}
      {metrics && !event && (
        <div className="model-result" data-result="overall">
          {excluded && <>This event is left out of the model results: {excluded.reason.replace(/;.*$/, "")}. </>}
          Across {metrics.events} past events the model scored AUC {range(metrics.overall.auc)} (95% interval), against {range(overallDistance!)} for
          distance alone.
        </div>
      )}
    </section>
  );
}
