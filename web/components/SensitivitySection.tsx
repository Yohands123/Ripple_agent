import type { Scenario } from "@/lib/types";

/** Ranked bars of scenario.sensitivity; renders nothing when it is missing or empty. */
export default function SensitivitySection({ scenario }: { scenario: Scenario }) {
  const rows = [...(scenario.sensitivity ?? [])].sort((a, b) => Math.abs(b.spearman) - Math.abs(a.spearman));
  if (rows.length === 0) return null;
  return (
    <section data-section="sensitivity">
      <h2 className="panel-heading">WHAT MATTERS MOST</h2>
      <div className="sens-list">
        {rows.map((r) => (
          <div key={r.assumption} className="sens-row">
            <span className="sens-name">{r.assumption}</span>
            <span className="sens-track">
              <span className="sens-bar" style={{ width: `${Math.min(1, Math.abs(r.spearman)) * 100}%` }} />
            </span>
            <span className="sens-value">
              {r.spearman >= 0 ? "+" : "−"}
              {Math.abs(r.spearman).toFixed(2)}
            </span>
          </div>
        ))}
      </div>
      <div className="panel-tiny">Rank correlation of each assumption with the outcome across simulated runs; longer bars matter more.</div>
    </section>
  );
}
