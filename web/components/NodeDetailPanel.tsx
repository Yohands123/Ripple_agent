"use client";

import { tierColorOf, tierLabel } from "@/lib/tokens";
import type { NetworkNode, Scenario } from "@/lib/types";
import PanelHeader from "./PanelHeader";

const KIND_LABEL: Record<string, string> = {
  mine: "Mining region",
  refinery: "Refinery",
  supplier_major: "Major supplier",
  supplier_minor: "Smaller supplier",
  assembly: "Assembly factory",
  port: "Port",
  airport: "Airport",
  canal: "Canal or strait",
  border: "Border crossing",
  apple_store: "Apple Store",
  carrier: "Phone carrier",
  retailer: "Other retailer",
  repair: "Support and repair",
  hq: "Headquarters",
  sales_region: "Apple sales region",
  chokepoint: "Strait",
  event_anchor: "Event location",
};

const PRECISION_LABEL: Record<string, string> = {
  exact: "exact location",
  city: "placed at its city",
  province: "placed at its province",
  country: "placed at its country",
};

/** "hops_from_shock" → "Hops from shock" */
export function featureLabel(f: string): string {
  const s = f.replace(/_/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

interface Props {
  sample: boolean;
  node: NetworkNode;
  scenario: Scenario | null;
  onClose: () => void;
  children?: React.ReactNode;
}

/** A node's details: what it is, its predicted hit with interval, SHAP drivers, and actual CAR. */
export default function NodeDetailPanel({ sample, node, scenario, onClose, children }: Props) {
  const pred = scenario?.predictions.find((p) => p.nodeId === node.id);
  const actual = scenario?.actual.find((a) => a.nodeId === node.id);
  const shap = [...(pred?.shap ?? [])].sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
  const maxShap = Math.max(0.01, ...shap.map((s) => Math.abs(s.value)));

  return (
    <>
      <PanelHeader sample={sample} />

      <section>
        <div className="heading-row">
          <h2 className="panel-heading">{KIND_LABEL[node.kind] ?? node.kind}</h2>
          <button type="button" className="text-button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="headline">{node.name}</div>
        <div className="panel-note">
          {node.region} · {PRECISION_LABEL[node.precision] ?? node.precision}
        </div>
        <dl className="facts">
          <dt>Tier</dt>
          <dd>
            <span className="tier-swatch inline" style={{ background: tierColorOf(node.tier) }} />
            {node.tier != null ? `${node.tier} ${tierLabel[node.tier] ?? ""}` : "Not known in the data"}
            {node.tier != null && node.tierStatus === "inferred" && (
              <span className="muted" data-tier-status="inferred" title={node.confidenceKind}>
                {" "}
                (inferred{node.tierBasis ? ` ${node.tierBasis.replace(/^mapped /, "")}` : ""}
                {node.confidence ? `; confidence: ${node.confidence}` : ""})
              </span>
            )}
          </dd>
          {node.partType && (
            <>
              <dt>Part type</dt>
              <dd>{node.partType}</dd>
            </>
          )}
          {node.ticker && (
            <>
              <dt>Ticker</dt>
              <dd>{node.ticker}</dd>
            </>
          )}
          {node.appleRevenueShare != null && (
            <>
              <dt>Revenue from Apple</dt>
              <dd>{pct(node.appleRevenueShare)}</dd>
            </>
          )}
        </dl>
      </section>

      <section>
        <h2 className="panel-heading">{scenario ? `PREDICTED HIT: ${scenario.title}` : "PREDICTED HIT"}</h2>
        {pred ? (
          <>
            <div className="interval" role="img" aria-label={`Chance of a hit ${pred.pHit.toFixed(2)}, 95% interval ${pred.ciLow.toFixed(2)} to ${pred.ciHigh.toFixed(2)}`}>
              <div className="interval-track" />
              <div className={pred.lowConfidence ? "interval-band dashed" : "interval-band"} style={{ left: `${pred.ciLow * 100}%`, width: `${(pred.ciHigh - pred.ciLow) * 100}%` }} />
              <div className="interval-point" style={{ left: `${pred.pHit * 100}%` }} />
            </div>
            <div className="interval-scale">
              <span>0</span>
              <span>1</span>
            </div>
            <div className="big-number">
              {pred.pHit.toFixed(2)}
              <span className="big-number-sub">
                {" "}
                range {pred.ciLow.toFixed(2)} to {pred.ciHigh.toFixed(2)}
                {pred.lowConfidence ? ", low confidence" : ""}
              </span>
            </div>
          </>
        ) : (
          <div className="panel-note">{scenario ? "No prediction for this node in this scenario." : "No scenario loaded."}</div>
        )}
      </section>

      {shap.length > 0 && (
        <section>
          <h2 className="panel-heading">WHAT DRIVES THE PREDICTION</h2>
          <div className="shap-list">
            {shap.map((s) => (
              <div key={s.feature} className="shap-row">
                <span className="shap-name">{featureLabel(s.feature)}</span>
                <span className="shap-track">
                  <span className="shap-axis" />
                  <span
                    className={s.value >= 0 ? "shap-bar up" : "shap-bar down"}
                    style={s.value >= 0 ? { left: "50%", width: `${(s.value / maxShap) * 50}%` } : { right: "50%", width: `${(-s.value / maxShap) * 50}%` }}
                  />
                </span>
                <span className="shap-value">
                  {s.value >= 0 ? "+" : "−"}
                  {Math.abs(s.value).toFixed(2)}
                </span>
              </div>
            ))}
          </div>
          <div className="panel-tiny">Red raises the chance of a hit; grey lowers it (SHAP values).</div>
        </section>
      )}

      <section>
        <h2 className="panel-heading">WHAT ACTUALLY HAPPENED</h2>
        {actual ? (
          <div className="panel-note" style={{ color: "var(--text-body)" }}>
            <strong style={{ color: actual.hit ? "var(--coin-red)" : "var(--text-primary)" }}>{actual.hit ? "Hit" : "No hit"}</strong>: cumulative
            abnormal return {actual.car >= 0 ? "+" : "−"}
            {pct(Math.abs(actual.car))} over days 0 to +10.
          </div>
        ) : (
          <div className="panel-note">{node.ticker ? "No actual return recorded for this event." : "Not publicly listed, so no stock return to compare."}</div>
        )}
      </section>

      {children}

      <section>
        <h2 className="panel-heading">SOURCES</h2>
        {node.sources.length ? (
          <ul className="sources">
            {node.sources.map((s) => (
              <li key={s.url || s.title}>
                {s.url ? (
                  <a href={s.url} target="_blank" rel="noreferrer">
                    {s.title}
                  </a>
                ) : (
                  s.title
                )}
              </li>
            ))}
          </ul>
        ) : (
          <div className="panel-note">No sources listed{sample ? " (sample data)" : ""}.</div>
        )}
      </section>
    </>
  );
}
