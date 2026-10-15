"use client";

import type { Network, Scenario } from "@/lib/types";

const MAX_AFFECTED = 5;
/** Below this, every prediction counts as low risk. */
const LOW_RISK = 0.1;

interface Row {
  key: string;
  /** Full company name. */
  name: string;
  /** Hover text: the site and the prediction's interval. */
  title: string;
  pHit: number;
  low: boolean;
  /** True or false once the outcome is known; undefined when there is none. */
  hit?: boolean;
  nodeId?: string;
}

interface Props {
  scenario: Scenario;
  network: Network | null;
  /** Show "no hit" for suppliers that were not hit (once a replay reaches the end). Actual hits are always marked. */
  showActual?: boolean;
  onSelectNode?: (nodeId: string) => void;
  /** Suppliers reached at each hop of the ripple, when known. */
  hops?: number[];
}

/** The company part of a site name ("Jabil Incorporated — Maharashtra" → "Jabil Incorporated"). */
const companyName = (siteName: string) => siteName.split(/\s[—–]\s/)[0].trim();

const interval = (p: { pHit: number; ciLow: number; ciHigh: number; lowConfidence: boolean }) =>
  `Chance of a hit ${p.pHit.toFixed(2)}, 95% interval ${p.ciLow.toFixed(2)} to ${p.ciHigh.toFixed(2)}${p.lowConfidence ? ", low confidence" : ""}`;

/** One row per company: site predictions are company-level, so a company's sites share one. */
function rowsOf(scenario: Scenario, network: Network | null): Row[] {
  const nodes = new Map((network?.nodes ?? []).map((n) => [n.id, n]));
  const actual = new Map(scenario.actual.map((a) => [a.nodeId, a]));
  const byCompany = new Map<string, Row>();
  for (const p of scenario.predictions) {
    const n = nodes.get(p.nodeId);
    const key = n?.companyId ?? p.nodeId;
    const a = actual.get(p.nodeId);
    const prev = byCompany.get(key);
    if (prev) {
      if (a?.hit) prev.hit = true;
      else if (a && prev.hit === undefined) prev.hit = false;
      continue;
    }
    const name = n ? companyName(n.name) : p.nodeId;
    byCompany.set(key, { key, name, title: `${n ? `${n.name}. ` : ""}${interval(p)}`, pHit: p.pHit, low: p.lowConfidence, hit: a?.hit, nodeId: p.nodeId });
  }
  for (const p of scenario.companyPredictions ?? []) {
    byCompany.set(p.companyId, { key: p.companyId, name: p.supplier, title: interval(p), pHit: p.pHit, low: p.lowConfidence, hit: p.actual?.hit });
  }
  return [...byCompany.values()];
}

/** Suppliers ranked by predicted risk relative to the event's average, with actual hits marked. */
export default function AffectedSection({ scenario, network, showActual = false, onSelectNode, hops }: Props) {
  const rows = rowsOf(scenario, network);
  const avg = rows.length ? rows.reduce((s, r) => s + r.pHit, 0) / rows.length : 0;
  const top = [...rows].sort((a, b) => b.pHit - a.pHit).slice(0, MAX_AFFECTED);
  const maxRel = avg > 0 && top.length ? top[0].pHit / avg : 1;
  const highest = top[0]?.pHit ?? 0;
  const unlocated = scenario.predictions.length === 0 && (scenario.companyPredictions ?? []).length > 0;

  return (
    <section data-section="affected">
      <h2 className="panel-heading">WHAT&apos;S AFFECTED</h2>
      {hops && hops.some((n) => n > 0) && (
        <div className="hop-counts" data-hops={hops.join(",")}>
          {hops.map((n, i) => (
            <span key={i}>
              Hop {i + 1}: {n} supplier{n === 1 ? "" : "s"}
            </span>
          ))}
        </div>
      )}
      {unlocated && <div className="panel-tiny">This year&apos;s Supplier List names companies but not their sites, so they are not on the map.</div>}
      {top.length === 0 ? (
        <div className="panel-note">{scenario.contextOnly && scenario.predictionScope ? scenario.predictionScope : "No predictions in this scenario yet."}</div>
      ) : (
        <>
          {highest < LOW_RISK && (
            <div className="panel-note" data-note="low-risk">
              The model predicts low risk for every supplier in this event (highest: {highest.toFixed(2)}).
            </div>
          )}
          <div className="affected-list" data-list={unlocated ? "companies" : "sites"}>
            {top.map((r) => {
              const rel = avg > 0 ? r.pHit / avg : 0;
              const body = (
                <>
                  <span className="affected-name">{r.name}</span>
                  <span className="affected-track">
                    <span className={r.low ? "affected-bar dashed" : "affected-bar"} style={{ width: `${Math.round((rel / maxRel) * 100)}%` }} />
                  </span>
                  <span className="affected-score">
                    {r.pHit.toFixed(2)}
                    <small>{rel.toFixed(1)}× avg</small>
                  </span>
                  <span className={r.hit ? "affected-actual hit" : "affected-actual"} data-actual={r.hit === undefined ? "none" : String(r.hit)}>
                    {r.hit ? "HIT" : showActual && r.hit === false ? "NO HIT" : ""}
                  </span>
                </>
              );
              return r.nodeId ? (
                <button key={r.key} type="button" className="affected-row" onClick={() => onSelectNode?.(r.nodeId!)} title={r.title}>
                  {body}
                </button>
              ) : (
                <div key={r.key} className="affected-row" title={r.title}>
                  {body}
                </div>
              );
            })}
          </div>
          <div className="panel-tiny">
            Ranked by predicted chance of a hit; bars compare each with the event&apos;s average ({avg.toFixed(2)}). HIT marks suppliers that were actually hit.
            {top.some((r) => r.low) && " Dashed bar: low-confidence prediction."}
          </div>
        </>
      )}
      {scenario.outcomeDefinition && (
        <div className="panel-tiny" data-note="outcome">
          {scenario.outcomeDefinition}
        </div>
      )}
    </section>
  );
}
