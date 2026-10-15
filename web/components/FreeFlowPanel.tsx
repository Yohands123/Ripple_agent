"use client";

import { tierColor, tierLabel, size } from "@/lib/tokens";
import { formatUsd } from "@/lib/format";
import type { Scenario } from "@/lib/types";
import { Coin, KeySymbol } from "./Glyphs";
import PanelHeader from "./PanelHeader";

interface Props {
  sample: boolean;
  /** The scenario the button will drop; its first week supplies the normal-week quota. */
  scenario: Scenario | null;
  onDrop: () => void;
  children?: React.ReactNode;
}

export default function FreeFlowPanel({ sample, scenario, onDrop, children }: Props) {
  const q = scenario?.quota;
  // An indexed quota (an assumed reference, not device counts) says nothing about a normal week.
  const indexed = Boolean(q?.unit);
  const shipped = indexed ? undefined : q?.noAction[0];
  const target = indexed ? undefined : q?.target[0];
  const filled = shipped != null && target ? Math.floor((shipped / target) * size.quotaBlocks) : 0;

  return (
    <>
      <PanelHeader sample={sample} />

      <div className="status-line">
        <div className="status-dot" style={{ background: tierColor[6] }} />
        All lanes clear
      </div>

      <section>
        <h2 className="panel-heading">IPHONE QUOTA THIS WEEK</h2>
        <div className="quota-bar" role="img" aria-label={`${filled} of ${size.quotaBlocks} quota blocks filled`}>
          {Array.from({ length: size.quotaBlocks }, (_, i) => (
            <div key={i} className={i < filled ? "quota-block filled" : "quota-block"} />
          ))}
        </div>
        <div className="panel-note">
          {shipped != null && target != null
            ? `On track: ${Math.round(shipped).toLocaleString("en-US")} of ${Math.round(target).toLocaleString("en-US")} units shipped`
            : indexed
              ? "Weekly quota is not public. Events use an assumed index instead (100 = a normal week)."
              : "Quota data not available"}
        </div>
      </section>

      <section>
        <h2 className="panel-heading">MONEY</h2>
        <div className="key-grid key-grid-2" style={{ gap: 10 }}>
          <div className="key-item"><Coin kind="gold" size={size.coinLegend} />Revenue in</div>
          <div className="key-item"><Coin kind="blue" size={size.coinLegend} />Spend out</div>
          <div className="key-item"><Coin kind="grey" size={size.coinLegend} />Delayed sales</div>
          <div className="key-item"><Coin kind="red" size={size.coinLegend} />Lost sales</div>
        </div>
        <div className="panel-small" style={{ marginTop: 8 }}>
          {scenario ? `1 coin = ${formatUsd(scenario.money.coinUsd)} per week` : "1 coin = a fixed amount per week"}
        </div>
      </section>

      <section>
        <h2 className="panel-heading">MAP KEY</h2>
        <div className="key-grid key-grid-2" style={{ gap: "9px 10px" }}>
          <div className="key-item"><KeySymbol kind="assembly" />Assembly factory</div>
          <div className="key-item"><KeySymbol kind="major" />Major supplier</div>
          <div className="key-item"><KeySymbol kind="minor" />Smaller supplier</div>
          <div className="key-item"><KeySymbol kind="port" />Port or canal</div>
          <div className="key-item"><KeySymbol kind="store" />Apple Store</div>
          <div className="key-item"><KeySymbol kind="retailer" />Other retailer</div>
          <div className="key-item"><KeySymbol kind="carrier" />Phone carrier</div>
        </div>
      </section>

      <section>
        <h2 className="panel-heading">TIER COLORS</h2>
        <div className="key-grid key-grid-4" style={{ gap: "7px 8px" }}>
          {[1, 2, 3, 4, 5, 6, 7].map((t) => (
            <div key={t} className="tier-item">
              <div className="tier-swatch" style={{ background: tierColor[t] }} />
              {t} {tierLabel[t]}
            </div>
          ))}
        </div>
      </section>

      {children}

      <div style={{ marginTop: "auto" }}>
        <button type="button" className="drop-button" onClick={onDrop} disabled={!scenario}>
          Drop a disruption
        </button>
      </div>
    </>
  );
}
