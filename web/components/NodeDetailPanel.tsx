"use client";

import { tierColorOf, tierLabel } from "@/lib/tokens";
import type { Trace } from "@/lib/trace";
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
  repair: "Repair and recycling",
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
  /** The node's trace, for the Connections chain. */
  trace?: Trace | null;
  /** Clicking a link of the chain. */
  onChain?: (part: ChainPart) => void;
  children?: React.ReactNode;
}

export type ChainPart =
  | "upMines"
  | "upRefineries"
  | "suppliers"
  | "self"
  | "factories"
  | "gateways"
  | "salesRegions"
  | "money"
  | "repairSites"
  | "refineries";

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** "12 suppliers → this factory → 2 ports and airports → 3 sales regions → Apple Park", each link clickable. */
function Connections({ node, trace, onChain }: { node: NetworkNode; trace: Trace; onChain?: (p: ChainPart) => void }) {
  const c = trace.counts;
  const self =
    node.kind === "assembly" ? "this factory" : node.kind === "sales_region" ? "this sales region" : `this ${KIND_LABEL[node.kind]?.toLowerCase() ?? "site"}`;
  // A sales region or repair site: where returned devices and recovered metals go.
  if (trace.returnEdges.length && (node.kind === "sales_region" || node.kind === "repair")) {
    const back: { key: ChainPart; text: string; n: number }[] = [{ key: "self", text: self, n: 1 }];
    if (c.repairSites) back.push({ key: "repairSites", text: plural(c.repairSites, "repair or recycling site"), n: c.repairSites });
    if (c.refineries) back.push({ key: "refineries", text: plural(c.refineries, "refinery", "refineries"), n: c.refineries });
    return (
      <section data-section="connections">
        <h2 className="panel-heading">CONNECTIONS</h2>
        <ChainLinks parts={back} onChain={onChain} />
        <div className="panel-tiny">Inferred return routes: trade-ins and repairs go back for refurbishment and recycling, and recovered metals back to refineries.</div>
      </section>
    );
  }
  // Upstream by tier: mining regions, then refineries, then the parts suppliers.
  const parts: { key: ChainPart; text: string; n: number }[] = [];
  if (c.upMines) parts.push({ key: "upMines", text: plural(c.upMines, "mining region"), n: c.upMines });
  if (c.upRefineries) parts.push({ key: "upRefineries", text: plural(c.upRefineries, "refinery", "refineries"), n: c.upRefineries });
  const direct = c.suppliers - c.upMines - c.upRefineries;
  if (direct || !parts.length) parts.push({ key: "suppliers", text: plural(direct, "supplier"), n: direct });
  parts.push({ key: "self", text: self, n: 1 });
  if (node.kind !== "assembly") parts.push({ key: "factories", text: plural(c.factories, "factory", "factories"), n: c.factories });
  parts.push({ key: "gateways", text: plural(c.gateways, "port or airport", "ports and airports"), n: c.gateways });
  parts.push({ key: "salesRegions", text: plural(c.salesRegions, "sales region"), n: c.salesRegions });
  if (trace.money) parts.push({ key: "money", text: "Apple Park", n: 1 });
  return (
    <section data-section="connections">
      <h2 className="panel-heading">CONNECTIONS</h2>
      <ChainLinks parts={parts} onChain={onChain} />
      <div className="panel-tiny">
        Upstream from supply links; downstream along the inferred routes it ships by. {c.suppliers === 0 && "No public source links suppliers to this site."}
      </div>
    </section>
  );
}

function ChainLinks({ parts, onChain }: { parts: { key: ChainPart; text: string; n: number }[]; onChain?: (p: ChainPart) => void }) {
  return (
    <div className="chain">
      {parts.map((p, i) => (
        <span key={p.key} className="chain-part">
          {i > 0 && <span className="chain-arrow" aria-hidden="true">→</span>}
          <button type="button" className="chain-link" disabled={p.n === 0} onClick={() => onChain?.(p.key)} data-chain={p.key}>
            {p.text}
          </button>
        </span>
      ))}
    </div>
  );
}

/** A node's details: what it is, its predicted hit with interval, SHAP drivers, and actual CAR. */
export default function NodeDetailPanel({ sample, node, scenario, onClose, trace, onChain, children }: Props) {
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

      {trace && <Connections node={node} trace={trace} onChain={onChain} />}

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
