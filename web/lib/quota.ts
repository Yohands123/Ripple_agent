// The "with plan" quota line for any set of chosen options, using only the scenario file.
//
// The file gives `noAction` and `withPlan` (the plan made of the default-on options).
// Each option's weight is the midpoint of its `unitsRecovered` range. The chosen
// options recover that share of the gap between `noAction` and `withPlan`. Until the
// optimizer fills `unitsRecovered` (all zero), the default-on options share it equally,
// which is an assumption and is labeled as one in the panel.

import type { Scenario } from "./types";

export interface PlanLine {
  values: number[];
  /** True when option weights were not in the file and an equal split was assumed. */
  equalSplitAssumed: boolean;
  /** True when the chosen options are exactly the file's default plan. */
  isDefaultPlan: boolean;
  sentence: string;
}

const mid = ([lo, hi]: [number, number]) => (lo + hi) / 2;

/** Null when the scenario has no quota (the data marks it unknown). */
export function planLine(scenario: Scenario, chosen: Set<string>): PlanLine | null {
  const { quota, options } = scenario;
  if (!quota) return null;
  const isDefault = options.every((o) => o.defaultOn === chosen.has(o.id));
  // The optimizer's own result for this exact set of options, when the file has it.
  const exact = quota.optionPlans?.find((p) => p.optionIds.length === chosen.size && p.optionIds.every((id) => chosen.has(id)));
  if (exact) {
    return { values: exact.withPlan, equalSplitAssumed: false, isDefaultPlan: isDefault, sentence: isDefault ? quota.recoverySentence : recoverySentence(exact.withPlan, quota.target) };
  }
  const hasWeights = options.some((o) => mid(o.unitsRecovered) > 0);
  const weight = (o: (typeof options)[number]) => (hasWeights ? Math.max(0, mid(o.unitsRecovered)) : o.defaultOn ? 1 : 0);
  const defaultTotal = options.filter((o) => o.defaultOn).reduce((s, o) => s + weight(o), 0);
  const chosenTotal = options.filter((o) => chosen.has(o.id)).reduce((s, o) => s + weight(o), 0);
  const share = defaultTotal > 0 ? chosenTotal / defaultTotal : 0;
  const isDefaultPlan = options.every((o) => o.defaultOn === chosen.has(o.id));

  const values = quota.noAction.map((na, i) => {
    const gain = (quota.withPlan[i] ?? na) - na;
    const ceiling = Math.max(quota.target[i] ?? 0, quota.withPlan[i] ?? 0);
    return Math.min(ceiling, na + gain * share);
  });

  return { values, equalSplitAssumed: !hasWeights, isDefaultPlan, sentence: isDefaultPlan ? quota.recoverySentence : recoverySentence(values, quota.target) };
}

/** "Back on target in week N" after the deepest dip, or that it does not recover in the window. */
export function recoverySentence(values: number[], target: number[]): string {
  if (values.length === 0) return "";
  const gap = values.map((v, i) => (target[i] ?? 0) - v);
  const trough = gap.indexOf(Math.max(...gap));
  if (gap[trough] <= (target[trough] ?? 0) * 0.02) return "On target throughout";
  for (let i = trough + 1; i < values.length; i++) {
    if (values[i] >= (target[i] ?? 0) * 0.98) return `Back on target in week ${i + 1}`;
  }
  return `Not back on target within ${values.length} weeks`;
}
