import { humanize } from "@/lib/format";
import type { Scenario } from "@/lib/types";

const TOP = 6;

/**
 * A plain name for an assumption: the file's own label, or a readable version of its code.
 * Codes like "assumed-detour.rampWeeks" name an option and one of its inputs: "Assumed detour reserve: ramp weeks".
 */
export function assumptionLabel(code: string, scenario: Scenario, label?: string): string {
  if (label) return label;
  const [optionId, input] = code.split(".");
  const option = input ? scenario.options.find((o) => o.id === optionId) : undefined;
  if (option && input) return `${option.label}: ${humanize(input).toLowerCase()}`;
  return humanize(code);
}

/** The six assumptions that matter most (scenario.sensitivity); renders nothing when it is missing or empty. */
export default function SensitivitySection({ scenario }: { scenario: Scenario }) {
  const rows = [...(scenario.sensitivity ?? [])].sort((a, b) => Math.abs(b.spearman) - Math.abs(a.spearman)).slice(0, TOP);
  if (rows.length === 0) return null;
  return (
    <section data-section="sensitivity">
      <h2 className="panel-heading">WHAT MATTERS MOST</h2>
      <div className="sens-list">
        {rows.map((r) => (
          <div key={r.assumption} className="sens-row" title={r.assumption}>
            <span className="sens-name">{assumptionLabel(r.assumption, scenario, r.label)}</span>
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
