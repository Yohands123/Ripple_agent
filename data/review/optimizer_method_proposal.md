# M9: approved illustrative planning method

Status: explicitly approved by the user on 2026-10-14, with the decision
"Approve illustrative M9 model and ranges". The kit contains no methods document or
operational demand, capacity, ramp-up, or cost ranges. M7 deliberately leaves
these unknown. Historical market-return probabilities cannot supply them.

The solver is implemented in `ml/optimize.py`. A review-only Monte Carlo
summary is in `data/review/optimizer_preview.json`. Approved inputs are in
`data/sources/optimizer_assumptions.json`; normal runs save processed plans
for publication through the exporter. Run
`.venv/bin/python -m ml.optimize --review` to reproduce that preview.

The solver can accept evidence-based inputs later. For completing the
requested Monte Carlo demonstration now, this proposal uses an **illustrative
indexed planning exercise** alongside the real historical evidence. Its
quantities are assumptions and cannot be described as Apple's production or
recommended actions.
Scenarios containing these illustrative planning quantities are marked
`sampleData: true` so the app also shows its existing Sample data tag. Their
public supplier evidence and company-return predictions keep their provenance.

## Approved inputs

Exact machine-readable ranges are in
`data/review/optimizer_assumptions_proposed.json`. All model inputs below are
assumptions. Operational input ranges are independent uniform distributions,
not confidence intervals estimated from data.

| Input | Proposed range | Unit |
|---|---|---|
| Weekly reference demand | [100, 100] | Indexed demand units; not devices |
| Initial retained base capacity | [0.45, 0.75] | Fraction of reference demand |
| Natural recovery time | [4, 8] | Weeks |
| Cost penalty | [0.01, 0.01] | Indexed unmet units per illustrative USD |
| Detour reserve capacity | [8, 18] | Indexed units/week |
| Detour lead/ramp time | [1, 2] / [1, 3] | Weeks |
| Detour incremental unit cost | [1, 3] | Illustrative USD/index unit |
| Expedited reserve capacity | [5, 12] | Indexed units/week |
| Expedited lead/ramp time | [0, 1] / [0, 1] | Weeks |
| Expedited incremental unit cost | [4, 8] | Illustrative USD/index unit |
| Alternate supply capacity | [10, 25] | Indexed units/week |
| Alternate lead/ramp time | [2, 4] / [2, 5] | Weeks |
| Alternate incremental unit cost | [2, 5] | Illustrative USD/index unit |

The dollar costs are entirely hypothetical prices per indexed unit. They do
not convert the index to devices, lost sales, or Apple's dollars. Revenue-at-risk
and delayed-revenue share remain null. These are generic reserves, without
invented real suppliers, physical routes, or country-specific capabilities.

## Approved LP

There are eight weekly periods, with week t beginning t weeks after the
scenario start. Existing capacity recovers linearly from its initial fraction
at t=0 to full reference capacity at the sampled recovery time.

Each alternative has a sampled lead time L, ramp time R, eventual capacity C,
and incremental cost c. Its weekly capacity bound is zero when t < L, and
otherwise `C * min(1, (t - L + 1) / max(1, R))`. Time is evaluated at the start
of a weekly planning bucket. Fractional lead/ramp samples are allowed; this is
an approximate weekly bucket model, without a claim about within-week timing.

For base output b[t], alternative output x[j,t], and unmet demand u[t]:

```
minimize sum_t u[t] + lambda * sum_j,t c[j] * x[j,t]
subject to b[t] + sum_j x[j,t] + u[t] = demand[t]
           0 <= b[t] <= base_capacity[t]
           0 <= x[j,t] <= ramped_capacity[j,t]
           u[t] >= 0
```

No inventory, backlogs, shared upstream bottlenecks, fixed activation costs,
transport flow conservation, or manufacturing bill of materials are assumed.
Those extensions require corresponding inputs and methods. The cost penalty
allows paying a high cost to be worse than leaving some demand unmet.

## Monte Carlo output

Run 1,000 draws per scenario with deterministic seeds. Reuse each draw's
inputs across all eight combinations of the three switches so comparisons
are paired. The indexed assumptions are the same across scenarios; event
names and historic dates do not imply event-specific capacity estimates.

Publish 2.5th/97.5th percentile ranges for recovery and incremental cost.
An option's individual recovery compares that option alone with no options;
these individual recoveries are **not additive**. Quota lines are pointwise
medians; their weekly ranges are also supplied. Sensitivity ranks Spearman
correlations between sampled inputs and total unmet demand in the default
plan. Positive means more unmet demand. Constant/undefined correlations are
omitted rather than invented as zero.

Retain the contract's option and quota fields. Add quota `unit`, `assumption`,
`scope`, weekly `noActionRange`/`withPlanRange`, and exact `optionPlans` for
switch combinations; add option `daysToEffectRange` alongside its median
`daysToEffect`; and add `optimization` provenance, input ranges, and MC method.
The app must show the indexed/assumed scope and use combination plans to avoid
adding overlapping recovery amounts. Unknown actual production and revenue
losses stay unknown. Only `pipeline/export.py` may write app data.

Approval covers this explicit mathematical model, the listed ranges and
distributions, and these explanatory export fields. Alternatively, supply
the missing methods and operational input ranges and the solver will use them.
