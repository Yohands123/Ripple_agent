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

/** Timeline scrubber for replaying an event, with the model's backtest results. */
export default function ReplaySection({ scenario, metrics, day, totalDays, onDay }: Props) {
  const event = metrics?.loeo.find((e) => e.eventId === scenario.id);

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
        <div className="model-result">
          Model tested on this event without training on it: AUC {f2(event.auc)}, against {f2(event.baselineAuc)} for distance alone. Across{" "}
          {metrics.events} events: AUC {f2(metrics.overall.auc[0])} to {f2(metrics.overall.auc[1])} (95% interval).
        </div>
      )}
      {metrics && !event && (
        <div className="model-result">
          Across {metrics.events} past events the model scored AUC {f2(metrics.overall.auc[0])} to {f2(metrics.overall.auc[1])} (95% interval),
          against {f2(metrics.overall.baselineAuc[0])} to {f2(metrics.overall.baselineAuc[1])} for distance alone.
        </div>
      )}
    </section>
  );
}
