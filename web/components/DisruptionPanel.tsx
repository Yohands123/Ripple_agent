"use client";

import type { Scenario } from "@/lib/types";
import PanelHeader from "./PanelHeader";

interface Props {
  sample: boolean;
  scenario: Scenario;
  onClear: () => void;
  children?: React.ReactNode;
}

export default function DisruptionPanel({ sample, scenario, onClear, children }: Props) {
  return (
    <>
      <PanelHeader sample={sample} />
      <section>
        <h2 className="panel-heading">WHAT&apos;S WRONG</h2>
        <div className="headline">{scenario.headline}</div>
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
