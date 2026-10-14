# M10 consumer handoff

The user approved nine events, preservation of missing-year gaps, and
company-only 2011 exports. `data/sources/event_expansion.json` records the
decision; no human-owned contract or web code is edited by Codex.

- Load every scenario's `networkPath`, including the two empty physical
  networks for Japan/Thailand 2011. Their event anchors remain available at
  `shock.location`. Empty factories are a coverage gap, not a loading failure.
- Read `scenario.companyPredictions` for those two events. Company IDs,
  supplier names, intervals, SHAP and company CARs do not imply coordinates.
  Surface `cohort.basis` and the undisclosed-location coverage note.
- Both 2011 supplier samples contain no hits. The user chose to exclude those
  events from all reported metrics, recorded in `evaluation_policy.json` and
  `auc_contract_proposal.md`. Metrics cover seven events/820 observations;
  nine scenario exports and all company predictions remain available.
  `excludedFromMetrics` explains why no event-metric entry exists. Do not
  substitute a zero score or imply that pooled scores cover all nine events.
- `metrics.loeo[].baselineAuc` is logistic regression; `distanceAuc` is the
  separate distance rule. The consumer currently calls the former "distance
  alone" in `ReplaySection.tsx`; those labels need to match the exported
  definitions.
- Existing M9 `quota.optionPlans` contains all eight exact switch combinations.
  Select the entry matching the enabled option IDs. Individual option recovery
  ranges overlap and cannot be added. Keep the sample-data and assumption
  labels for illustrative plans; actual Apple capacity/revenue stay unknown.

The nine-event index intentionally excludes Japan–Korea 2019, Taiwan 2024 and
Helene 2024. Their missing FY2019/FY2024 cohort evidence is documented in
`data/review/event_gaps.json`; no nearby-year substitution was approved.
