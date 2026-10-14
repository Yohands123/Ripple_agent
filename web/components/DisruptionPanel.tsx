"use client";

import { useMemo, useState } from "react";
import { planLine } from "@/lib/quota";
import type { Network, Scenario } from "@/lib/types";
import PanelHeader from "./PanelHeader";
import QuotaChart from "./QuotaChart";

const MAX_AFFECTED = 5;

interface Props {
  sample: boolean;
  scenario: Scenario;
  network: Network | null;
  onClear: () => void;
  onSelectNode?: (nodeId: string) => void;
  children?: React.ReactNode;
}

export default function DisruptionPanel({ sample, scenario, network, onClear, onSelectNode, children }: Props) {
  // Remount-free reset: options start from the file's defaults whenever the scenario changes.
  const [choice, setChoice] = useState<{ id: string; chosen: Set<string> }>(() => defaults(scenario));
  const chosen = choice.id === scenario.id ? choice.chosen : defaults(scenario).chosen;
  const plan = useMemo(() => planLine(scenario, chosen), [scenario, chosen]);

  const names = new Map((network?.nodes ?? []).map((n) => [n.id, n.name]));
  const affected = [...scenario.predictions].sort((a, b) => b.pHit - a.pHit).slice(0, MAX_AFFECTED);
  const anyLowConfidence = affected.some((p) => p.lowConfidence);

  const toggle = (id: string) => {
    const next = new Set(chosen);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setChoice({ id: scenario.id, chosen: next });
  };

  return (
    <>
      <PanelHeader sample={sample} />

      <section>
        <h2 className="panel-heading">WHAT&apos;S WRONG</h2>
        <div className="headline">{scenario.headline}</div>
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
                className="affected-row"
                onClick={() => onSelectNode?.(p.nodeId)}
                title={`Chance of a hit ${p.pHit.toFixed(2)}, 95% interval ${p.ciLow.toFixed(2)} to ${p.ciHigh.toFixed(2)}${p.lowConfidence ? ", low confidence" : ""}`}
              >
                <span className="affected-name">{names.get(p.nodeId) ?? p.nodeId}</span>
                <span className="affected-track">
                  <span className={p.lowConfidence ? "affected-bar dashed" : "affected-bar"} style={{ width: `${Math.round(p.pHit * 100)}%` }} />
                </span>
                <span className="affected-score">{p.pHit.toFixed(2)}</span>
              </button>
            ))}
          </div>
        )}
        {anyLowConfidence && <div className="panel-tiny">Dashed bar: low-confidence prediction</div>}
      </section>

      <section>
        <h2 className="panel-heading">WHAT CAN BE SHIFTED</h2>
        {scenario.options.map((o) => (
          <div key={o.id} className="option-row">
            <input type="checkbox" id={`opt-${o.id}`} checked={chosen.has(o.id)} onChange={() => toggle(o.id)} />
            <label htmlFor={`opt-${o.id}`}>{o.label}</label>
            <div className="option-detail">{o.detail}</div>
          </div>
        ))}
        {plan.equalSplitAssumed && scenario.options.length > 0 && (
          <div className="panel-tiny">Assumption: option effects not yet estimated, so the plan&apos;s gain is split evenly.</div>
        )}
      </section>

      <section>
        <h2 className="panel-heading">WILL WE MEET QUOTA?</h2>
        <QuotaChart target={scenario.quota.target} noAction={scenario.quota.noAction} withPlan={plan.values} />
        <div className="recovery" aria-live="polite">
          {plan.sentence}
        </div>
      </section>

      {children}

      <div style={{ marginTop: "auto" }}>
        <button type="button" className="text-button" onClick={onClear}>
          Back to a normal week
        </button>
      </div>
    </>
  );
}

function defaults(s: Scenario) {
  return { id: s.id, chosen: new Set(s.options.filter((o) => o.defaultOn).map((o) => o.id)) };
}
