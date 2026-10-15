"use client";

import { useState } from "react";
import type { ScenarioIndexEntry, ScenarioType } from "@/lib/types";

const TYPES: { type: ScenarioType; label: string }[] = [
  { type: "sea", label: "Sea" },
  { type: "sky", label: "Sky" },
  { type: "land", label: "Land" },
  { type: "policy", label: "Policy" },
  { type: "demand", label: "Demand" },
];

interface Props {
  index: ScenarioIndexEntry[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

/** Every scenario in scenarios/index.json, filterable by type. */
export default function ScenarioPicker({ index, selectedId, onSelect }: Props) {
  const [filter, setFilter] = useState<ScenarioType | "all">("all");
  if (index.length === 0) {
    return (
      <section>
        <h2 className="panel-heading">SCENARIO</h2>
        <div className="panel-note">No scenarios available yet.</div>
      </section>
    );
  }
  const shown = filter === "all" ? index : index.filter((s) => s.type === filter);
  const counts = new Map<ScenarioType, number>();
  for (const s of index) counts.set(s.type, (counts.get(s.type) ?? 0) + 1);
  const chips: { key: ScenarioType | "all"; label: string; n: number }[] = [
    { key: "all", label: "All", n: index.length },
    ...TYPES.map((t) => ({ key: t.type, label: t.label, n: counts.get(t.type) ?? 0 })),
  ];
  const value = shown.some((s) => s.id === selectedId) ? (selectedId ?? "") : "";

  return (
    <section data-section="scenario-picker">
      <h2 className="panel-heading">SCENARIO</h2>
      <div className="chips" role="group" aria-label="Filter scenarios by type">
        {chips.map((c) => (
          <button
            key={c.key}
            type="button"
            className={filter === c.key ? "chip on" : "chip"}
            aria-pressed={filter === c.key}
            disabled={c.n === 0}
            onClick={() => setFilter(c.key)}
            data-filter={c.key}
          >
            {c.label}
          </button>
        ))}
      </div>
      <select className="scenario-select" aria-label="Scenario" value={value} onChange={(e) => e.target.value && onSelect(e.target.value)}>
        {value === "" && <option value="">Choose a scenario</option>}
        {shown.map((s) => (
          <option key={s.id} value={s.id}>
            {s.title.includes(s.start.slice(0, 4)) ? s.title : `${s.title} (${s.start.slice(0, 4)})`}
          </option>
        ))}
      </select>
    </section>
  );
}
