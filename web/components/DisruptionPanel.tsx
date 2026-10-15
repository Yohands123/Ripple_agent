"use client";

import { useMemo, useState } from "react";
import { planLine } from "@/lib/quota";
import type { Network, Scenario } from "@/lib/types";
import PanelHeader from "./PanelHeader";
import QuotaChart from "./QuotaChart";
import SensitivitySection from "./SensitivitySection";
import AffectedSection from "./AffectedSection";

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
  /** Suppliers reached at each hop of the ripple. */
  hops?: number[];
  children?: React.ReactNode;
}

export default function DisruptionPanel({ sample, scenario, showActual = false, network, onClear, onSelectNode, picker, hops, children }: Props) {
  // Remount-free reset: options start from the file's defaults whenever the scenario changes.
  const [choice, setChoice] = useState<{ id: string; chosen: Set<string> }>(() => defaults(scenario));
  const chosen = choice.id === scenario.id ? choice.chosen : defaults(scenario).chosen;
  const plan = useMemo(() => planLine(scenario, chosen), [scenario, chosen]);

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

      <AffectedSection scenario={scenario} network={network} showActual={showActual} onSelectNode={onSelectNode} hops={hops} />

      <section>
        <h2 className="panel-heading">WHAT CAN BE SHIFTED</h2>
        {scenario.options.length === 0 && <div className="panel-note">No options to shift are in the data for this event.</div>}
        {scenario.options.map((o) => (
          <div key={o.id} className="option-row">
            <input type="checkbox" id={`opt-${o.id}`} checked={chosen.has(o.id)} onChange={() => toggle(o.id)} />
            <label htmlFor={`opt-${o.id}`}>{o.label}</label>
            <div className={o.detail.length > 32 ? "option-detail long" : "option-detail"}>{o.detail}</div>
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
            {scenario.quota.unit && (
              <div className="panel-tiny" data-note="quota-unit">
                Assumption: {scenario.quota.unit}.{scenario.quota.scope ? ` ${scenario.quota.scope}.` : ""}
              </div>
            )}
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
