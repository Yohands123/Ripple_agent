"use client";

import { useMemo, useState } from "react";
import { planLine } from "@/lib/quota";
import type { Network, Scenario } from "@/lib/types";
import PanelHeader from "./PanelHeader";
import QuotaChart from "./QuotaChart";
import SensitivitySection from "./SensitivitySection";

const MAX_AFFECTED = 5;

interface Props {
  sample: boolean;
  scenario: Scenario;
  /** Show actual outcomes next to predictions (once a replay reaches the end). */
  showActual?: boolean;
  network: Network | null;
  onClear: () => void;
  onSelectNode?: (nodeId: string) => void;
  /** Scenario picker, shown first so another event can be chosen. */
  picker?: React.ReactNode;
  children?: React.ReactNode;
}

export default function DisruptionPanel({ sample, scenario, showActual = false, network, onClear, onSelectNode, picker, children }: Props) {
  // Remount-free reset: options start from the file's defaults whenever the scenario changes.
  const [choice, setChoice] = useState<{ id: string; chosen: Set<string> }>(() => defaults(scenario));
  const chosen = choice.id === scenario.id ? choice.chosen : defaults(scenario).chosen;
  const plan = useMemo(() => planLine(scenario, chosen), [scenario, chosen]);

  const names = new Map((network?.nodes ?? []).map((n) => [n.id, n.name]));
  const affected = [...scenario.predictions].sort((a, b) => b.pHit - a.pHit).slice(0, MAX_AFFECTED);
  const anyLowConfidence = affected.some((p) => p.lowConfidence);
  const actual = new Map(scenario.actual.map((a) => [a.nodeId, a]));
  const withActual = showActual && affected.some((p) => actual.has(p.nodeId));

  const toggle = (id: string) => {
    const next = new Set(chosen);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setChoice({ id: scenario.id, chosen: next });
  };

  return (
    <>
      <PanelHeader sample={sample} />
      {picker}

      <section>
        <div className="heading-row">
          <h2 className="panel-heading">WHAT&apos;S WRONG</h2>
          <button type="button" className="text-button" onClick={onClear}>
            Back to a normal week
          </button>
        </div>
        <div className="headline">{scenario.headline}</div>
        {scenario.unknowns && scenario.unknowns.length > 0 && (
          <div className="panel-tiny">Not known from public data: {scenario.unknowns.join("; ")}.</div>
        )}
      </section>

      <section>
        <h2 className="panel-heading">WHAT&apos;S AFFECTED</h2>
        {affected.length === 0 ? (
          <div className="panel-note">No predictions in this scenario yet.</div>
        ) : (
          <div className="affected-list">
            {affected.map((p) => (
              <button
                key={p.nodeId}
                type="button"
                className={withActual ? "affected-row with-actual" : "affected-row"}
                onClick={() => onSelectNode?.(p.nodeId)}
                title={`Chance of a hit ${p.pHit.toFixed(2)}, 95% interval ${p.ciLow.toFixed(2)} to ${p.ciHigh.toFixed(2)}${p.lowConfidence ? ", low confidence" : ""}`}
              >
                <span className="affected-name">{names.get(p.nodeId) ?? p.nodeId}</span>
                <span className="affected-track">
                  <span className={p.lowConfidence ? "affected-bar dashed" : "affected-bar"} style={{ width: `${Math.round(p.pHit * 100)}%` }} />
                </span>
                <span className="affected-score">{p.pHit.toFixed(2)}</span>
                {withActual && (
                  <span className={actual.get(p.nodeId)?.hit ? "affected-actual hit" : "affected-actual"}>
                    {actual.has(p.nodeId) ? (actual.get(p.nodeId)!.hit ? "HIT" : "NO HIT") : ""}
                  </span>
                )}
              </button>
            ))}
          </div>
        )}
        {anyLowConfidence && <div className="panel-tiny">Dashed bar: low-confidence prediction</div>}
      </section>

      <section>
        <h2 className="panel-heading">WHAT CAN BE SHIFTED</h2>
        {scenario.options.length === 0 && <div className="panel-note">No options to shift are in the data for this event.</div>}
        {scenario.options.map((o) => (
          <div key={o.id} className="option-row">
            <input type="checkbox" id={`opt-${o.id}`} checked={chosen.has(o.id)} onChange={() => toggle(o.id)} />
            <label htmlFor={`opt-${o.id}`}>{o.label}</label>
            <div className="option-detail">{o.detail}</div>
          </div>
        ))}
        {plan?.equalSplitAssumed && scenario.options.length > 0 && (
          <div className="panel-tiny">Assumption: option effects not yet estimated, so the plan&apos;s gain is split evenly.</div>
        )}
      </section>

      <section>
        <h2 className="panel-heading">WILL WE MEET QUOTA?</h2>
        {scenario.quota && plan ? (
          <>
            <QuotaChart target={scenario.quota.target} noAction={scenario.quota.noAction} withPlan={plan.values} />
            <div className="recovery" aria-live="polite">
              {plan.sentence}
            </div>
          </>
        ) : (
          <div className="panel-note">Production quota and recovery are not known from public data.</div>
        )}
      </section>

      <SensitivitySection scenario={scenario} />

      {children}
    </>
  );
}

function defaults(s: Scenario) {
  return { id: s.id, chosen: new Set(s.options.filter((o) => o.defaultOn).map((o) => o.id)) };
}
