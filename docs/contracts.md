# Data contract

The pipeline writes these files to `web/public/data/real/`. The interface
reads `web/public/data/real/` when it exists and otherwise falls back to
`web/public/data/fixtures/`, a copy of `contracts/fixtures/`. Only the human
edits this contract; it stays frozen while the autopilot runs.

This version describes what the real export contains (updated 2026-10-14,
with the human's approval). The fixtures in `contracts/fixtures/` are an
older, smaller subset of the same shapes, and they remain valid.

Conventions for every file:

- Ranges are always `[low, high]`.
- Field marked **nullable** may be `null`, meaning "not known from public
  data". The interface shows it as unknown and never fills in a number.
- Field marked **optional** may be left out entirely.
- `sources` is always a list of `{ "title": "...", "url": "https://..." }`.
- `assumption: true` marks a value that is assumed, not measured. The
  interface labels it as an assumption and shows it as a range.
- `sampleData: true` marks illustrative values. The interface shows a
  "Sample data" tag whenever any loaded file has it.
- Free-text `...Definition`, `...Basis`, `scope`, and `note` fields explain
  how a value was made. The interface may show them as fine print, and must
  not drop a caveat that changes the meaning of a number.

## Files

| File | What it holds |
|---|---|
| `network.json` | The default network: the most recent event's Supplier List year |
| `networks/<eventId>.json` | The network for one event, from that event's own Supplier List year |
| `scenarios/index.json` | The list of scenarios for the picker |
| `scenarios/<id>.json` | One past or hypothetical disruption |
| `metrics.json` | Backtest results for the model |
| `forecasts.json` | Input cost forecasts (phase 2; may be missing) |

## `network.json` and `networks/<eventId>.json`: the supply chain for one Supplier List year

Both files have the same shape. A scenario names its own network in
`networkPath`.

```json
{
  "snapshotYear": 2021,
  "sampleData": false,
  "eventId": "suez-2021",
  "asOfDate": "2021-03-23",
  "scope": "Disclosed supplier locations. Physical transport links and production tiers are unavailable.",
  "cohort": {
    "snapshotYear": 2021,
    "eventYear": 2021,
    "publicationYear": 2022,
    "yearBasis": "explicit fiscal year",
    "locationCoverage": "disclosed locations",
    "basis": "Own-year procurement coverage, published retrospectively",
    "assumption": false,
    "proxyApproved": false,
    "companyOnlyExportApproved": false
  },
  "cohortBasis": "Supplier lists were published retrospectively. ...",
  "coverage": { "matchedLocations": 704, "manufacturingLocations": 704 },
  "nodes": [
    {
      "id": "location-0003eb8a1f66c95b",
      "companyId": "supplier-5313be216c8bb1fc",
      "name": "Jabil Incorporated — Maharashtra",
      "kind": "supplier_major",
      "locationRole": "manufacturing",
      "tier": 4,
      "tierStatus": "inferred",
      "tierBasis": "mapped from part type",
      "lon": 76.1,
      "lat": 19.44,
      "precision": "province",
      "region": "Maharashtra",
      "ticker": "JBL",
      "partType": "electronics manufacturing services",
      "partTypeScope": "Company product category, not an Apple-specific bill of materials",
      "appleRevenueShare": 0.2,
      "sources": [{ "title": "Apple Supplier List FY2021", "url": "https://..." }],
      "attributeSources": {
        "partType": { "source": { "title": "Jabil annual report FY2020", "url": "https://..." }, "filedOn": "2020-10-22" },
        "appleRevenueShare": { "source": { "title": "Jabil annual report FY2020", "url": "https://..." }, "filedOn": "2020-10-22" },
        "size": {
          "source": { "title": "SEC company facts: total assets in USD", "url": "https://..." },
          "filedOn": "2021-01-08",
          "periodEnd": "2020-11-30",
          "assetsUsd": 15269478000
        }
      }
    }
  ],
  "edges": [
    {
      "id": "e-0001",
      "from": "tsmc-hsinchu",
      "to": "foxconn-zhengzhou",
      "mode": "air",
      "carriesTier": 3,
      "status": "inferred",
      "sources": []
    }
  ]
}
```

Top level:

- `snapshotYear`: the Supplier List year the nodes come from.
- `eventId`, `asOfDate` (optional): the event this network was built for,
  and the date it describes. The default `network.json` has them too.
- `scope` (optional): one sentence on what the network does and does not
  cover. The interface shows it as fine print.
- `cohort` (optional): how the Supplier List year was chosen for the event.
  - `snapshotYear`, `eventYear`, `publicationYear`: numbers.
  - `yearBasis`, `basis`, `locationCoverage`: free text.
  - `assumption`: true when the year match is approximate, for example the
    2011 events, which use the January 2012 company roster.
  - `proxyApproved`, `companyOnlyExportApproved`: true when the human
    approved a proxy list or a company-only export for this event.
- `cohortBasis` (optional): free text explaining the cohort rules.
- `coverage` (optional): how many locations were matched.
  - `matchedLocations`, `manufacturingLocations`: counts.
  - `unlocatedCompanies` (optional): companies with no disclosed site.
  - `locationCoverage` (optional): `"undisclosed"` when the list gives
    companies only. Such a network has no nodes; its scenario uses
    `companyPredictions` instead (see below).
- `edges` may be empty. The real export has no edges yet, because physical
  transport routes are not public. While `edges` is empty, the interface
  draws typical lanes from public geography, labeled as typical and not
  supplier-specific. Those lanes exist only in the interface and are never
  written to these files.

Nodes:

- `kind`: `mine`, `refinery`, `supplier_major`, `supplier_minor`, `assembly`,
  `port`, `airport`, `canal`, `border`, `apple_store`, `carrier`, `retailer`,
  `repair`, `hq`. The real export currently uses `supplier_major` only.
- `companyId` (optional): groups the sites of one company. Company-level
  values (`ticker`, `appleRevenueShare`, predictions) are shared by all its
  sites.
- `locationRole` (optional): `manufacturing` or `headquarters`.
- `tier` (**nullable**): 1 to 7, matching the tier colors in
  `design-spec.md`. `null` means unknown, and the interface draws the node in
  neutral grey.
- `tierStatus` (optional): `known` (stated in a source), `inferred` (mapped
  from `partType`), or `unknown` (`tier` is `null`). An inferred tier is never
  presented as known.
- `tierBasis` (optional): free text, for example `"mapped from part type"`
  or `"part type unavailable"`.
- `precision`: `exact`, `city`, `province`, `country`.
- `ticker`, `partType`, `appleRevenueShare` are **nullable**.
- `partTypeScope` (optional): what `partType` describes. In the real export it
  is the company's product category, not an Apple bill of materials.
- `attributeSources` (optional): a source for each company attribute, keyed
  by attribute: `partType`, `appleRevenueShare`, `size`. Each entry has
  `source`, `filedOn`, and, for `size`, `periodEnd` and `assetsUsd`.

Edges:

- `mode`: `sea`, `air`, `road`, `rail`.
- `status`: `known` or `inferred`. The interface draws inferred edges dashed.
- `via` (optional): waypoints as `[[lon, lat], ...]` between `from` and `to`,
  so sea routes follow real lanes instead of straight lines. Air routes omit
  it and are drawn as arcs.

## `scenarios/<id>.json`: one past or hypothetical disruption

```json
{
  "id": "suez-2021",
  "title": "Suez Canal blocked",
  "type": "sea",
  "start": "2021-03-23",
  "end": "2021-03-29",
  "dateBasis": "Ever Given grounding and canal reopening",
  "endBasis": "Canal reopened; subsequent shipping backlog continued",
  "snapshotYear": 2021,
  "networkPath": "networks/suez-2021.json",
  "cohort": { "snapshotYear": 2021, "eventYear": 2021, "publicationYear": 2022, "...": "as in the network" },
  "sampleData": true,
  "sources": [{ "title": "Reuters: traffic resumes after Ever Given refloated, March 29, 2021", "url": "https://..." }],
  "shock": {
    "nodeIds": [],
    "capacityLoss": null,
    "location": {
      "lon": 32.55,
      "lat": 30.0,
      "precision": "city",
      "basis": "Natural Earth city point; not an exact disrupted-facility coordinate",
      "sources": [{ "title": "...", "url": "https://..." }]
    }
  },
  "headline": "Suez Canal blocked. Supplier stock responses are shown; production losses are unknown.",
  "outcomeDefinition": "Company market-model CAR over trading days 0 to +10; hit when t < -1.96. Not a measurement of factory damage or production loss.",
  "unknowns": ["Apple production capacity loss", "Physical supplier transport routes"],
  "predictions": [
    {
      "nodeId": "location-0003eb8a1f66c95b",
      "pHit": 0.044,
      "ciLow": 0.027,
      "ciHigh": 0.070,
      "lowConfidence": true,
      "shap": [{ "feature": "sourcing_hhi", "value": 0.033 }],
      "shapBaseValue": -3.13,
      "shapMeanRawScore": -3.06,
      "predictionScope": "Company-level market-response projection shared by disclosed sites; not a site-specific damage observation",
      "outcomeObservable": true
    }
  ],
  "companyPredictions": [],
  "actual": [
    { "nodeId": "location-0003eb8a1f66c95b", "hit": false, "car": -0.071, "scope": "Company-level CAR shared by disclosed sites" }
  ],
  "options": [
    {
      "id": "assumed-detour",
      "label": "Assumed detour reserve",
      "detail": "Illustrative indexed capacity and costs; individual recovery is not additive with other options",
      "unitsRecovered": [17.6, 74.0],
      "extraCostUsd": [26.0, 176.2],
      "daysToEffect": 14,
      "daysToEffectRange": [14, 14],
      "defaultOn": true,
      "assumption": true,
      "inputRanges": { "capacityPerWeek": [8, 18], "leadWeeks": [1, 2], "rampWeeks": [1, 3], "costUsdPerIndexUnit": [1, 3] }
    }
  ],
  "quota": {
    "weeks": ["2021-03-23"],
    "target": [100],
    "noAction": [59.6],
    "withPlan": [59.6],
    "noActionRange": [[45.7, 74.3]],
    "withPlanRange": [[45.7, 74.3]],
    "optionPlans": [{ "optionIds": ["assumed-detour"], "withPlan": [59.6], "withPlanRange": [[45.7, 74.3]], "extraCostUsd": [26.0, 176.2] }],
    "recoverySentence": "Median indexed plan reaches the assumed weekly target from week 4",
    "unit": "indexed demand units; 100 is an assumed weekly reference, not a count of devices",
    "scope": "Illustrative indexed planning exercise; not estimated Apple production, shipping capacity, or actual procurement",
    "assumption": true
  },
  "money": { "coinUsd": 500000000, "revenueAtRisk": null, "delayedShare": null, "assumption": false },
  "affectedRoutes": { "blocked": [], "detour": [], "expedited": [] },
  "sensitivity": [{ "assumption": "initialCapacityFraction", "spearman": -0.95 }],
  "optimization": { "solver": "OR-Tools GLOP", "draws": 1000, "assumption": true, "scope": "...", "...": "see below" }
}
```

Identity and dates:

- `type`: `sea`, `sky`, `land`, `policy`, `demand`.
- `dateBasis`, `endBasis` (optional): what the `start` and `end` dates
  observe. For most real events, `end` is the onset or announcement window,
  not the end of the disruption.
- `networkPath` (optional): the network file for this event, relative to
  the data folder. When it is missing, the interface uses `network.json`.
  Each historical event uses the Supplier List from its own year, so the
  interface loads this file for the scenario.
- `cohort` (optional): as in the network.
- `sources` (optional): sources for the event itself.

Shock:

- `shock.nodeIds` may be empty when no node is the shock itself.
- `shock.capacityLoss` (**nullable**): share of capacity lost, 0 to 1.
- `shock.location` (optional): where the event happened.
  - `lon`, `lat`, `precision`.
  - `basis`: free text.
  - `sources`.

  The interface draws the shock zone here when `shock.nodeIds` is empty. For
  a sea event it closes the nearest typical chokepoint, and for a port city
  it closes that port.

Text:

- `headline`: one sentence for the panel.
- `outcomeDefinition` (optional): what `hit`, `car`, and `pHit` measure. In
  the real export these are company stock responses, not factory damage.
  The interface shows it next to predictions and actual results.
- `unknowns` (optional): things the data does not know for this event, shown
  in the panel as a list.

Predictions and outcomes:

- `predictions[]`: one per node.
  - `pHit`, `ciLow`, `ciHigh`: probabilities, 0 to 1.
  - `lowConfidence`: boolean.
  - `shap`: `[{ "feature", "value" }]`, contributions to the log odds.
  - Optional: `shapBaseValue` and `shapMeanRawScore` (numbers); `predictionScope` (free
    text on what the prediction covers); `outcomeObservable` (false when no
    actual outcome can exist for that node).
- `companyPredictions` (optional): for events whose network has company names
  but no locations (the 2011 events). Each entry has:
  - the same probability and SHAP fields as `predictions[]`, plus
    `predictionScope` and `outcomeObservable`;
  - `companyId`, `supplier` (the company name), `ticker` (**nullable**), and
    `sources`;
  - `actual` (**nullable**): `{ "hit", "car" }`.
- `actual[]`: `{ "nodeId", "hit", "car" }`, plus an optional `scope` (free
  text). It is empty for hypothetical scenarios.

Recovery plan:

- `options[]`: recovery options.
  - `unitsRecovered` and `extraCostUsd` are ranges.
  - `daysToEffectRange` (optional) is a range around `daysToEffect`.
  - `inputRanges` (optional) is the assumed input for the optimizer, with
    ranges `capacityPerWeek`, `leadWeeks`, `rampWeeks`, and
    `costUsdPerIndexUnit`.
- `options` may be empty when no plan is modeled.
- `quota` (**nullable**): `null` when production is not modeled. When
  present:
  - `weeks`, `target`, `noAction`, `withPlan`, and `recoverySentence` as
    before.
  - Optional:
    - `noActionRange`, `withPlanRange`: per-week ranges.
    - `optionPlans`: the result for each combination of options, as
      `optionIds`, `withPlan`, `withPlanRange`, and `extraCostUsd`. The
      interface uses the plan matching the chosen options when it exists.
    - `unit`: what the numbers count. The real export uses an index, where
      100 is an assumed weekly reference, not a count of devices.
    - `scope`, `assumption`.

Money and routes:

- `money.revenueAtRisk` (**nullable**, range) and `money.delayedShare`
  (**nullable**, 0 to 1). When either is `null`, the interface draws no
  at-risk coins and says the amount is unknown.
- `affectedRoutes`: edge ids. All three lists may be empty.

Model notes:

- `sensitivity` (filled by the optimizer, may be empty):
  `[{ "assumption": "initialCapacityFraction", "spearman": -0.95 }]`, sorted
  by absolute value, largest first.
- `optimization` (optional): how the plan was computed.
  - `solver`, `ortoolsVersion`, `seed`, `draws`, `pairedOptionCombinations`.
  - `baseCapacityRange`: per-week ranges.
  - `defaultExtraCostUsd`: a range.
  - `inputRanges`: the assumed ranges and their `approval` record.
  - `scope`, `assumption`, and free-text `costDefinition`, `rangeDefinition`,
    and `sensitivityDefinition`.

## `scenarios/index.json`

```json
[{ "id": "suez-2021", "title": "Suez Canal blocked", "type": "sea", "start": "2021-03-23" }]
```

## `metrics.json`: model results for the backtest panel

```json
{
  "model": "lightgbm",
  "sampleData": false,
  "events": 7,
  "predictionEvents": 9,
  "rows": 820,
  "loeo": [
    {
      "eventId": "suez-2021",
      "rows": 121,
      "hits": 8,
      "auc": 0.53,
      "brier": 0.06,
      "baselineAuc": 0.64,
      "logisticBrier": 0.07,
      "distanceAuc": 0.88,
      "distanceBrier": 0.06
    }
  ],
  "overall": { "auc": [0.40, 0.56], "brier": [0.03, 0.07], "baselineAuc": [0.49, 0.68], "distanceAuc": [0.53, 0.74] },
  "overallPoint": { "auc": 0.45, "brier": 0.05, "baselineAuc": 0.58, "distanceAuc": 0.63 },
  "calibration": [{ "binMid": 0.05, "predicted": 0.04, "observed": 0.05, "n": 811 }],
  "cohorts": [{ "eventId": "suez-2021", "snapshotYear": 2021, "...": "as in the network cohort" }],
  "excludedEvents": [
    { "eventId": "taiwan-2024", "snapshotYear": 2024, "reason": "No verified own-year Supplier List", "source": { "title": "...", "url": "https://..." } }
  ],
  "excludedFromMetrics": [{ "eventId": "japan-2011", "rows": 54, "hits": 0, "reason": "Single observed supplier outcome class" }],
  "evaluationPolicy": {
    "approved": true,
    "approvalDate": "2026-10-14",
    "singleClassEvents": "exclude-from-metrics",
    "userDecision": "Exclude single-class events from metrics",
    "scope": "...",
    "limitation": "..."
  },
  "bootstrapEventDraws": 2000,
  "ensembleMembersPerFold": 200,
  "probabilityDefinition": "...",
  "baselineDefinition": "...",
  "evaluationDefinition": "...",
  "shapDefinition": "...",
  "lowConfidenceRule": "...",
  "limitations": ["..."]
}
```

- `events`: events in the metrics. `predictionEvents`: events with exported
  predictions (it includes events excluded from the metrics).
- `loeo[]`: leave-one-event-out results.
  - `baselineAuc` is the logistic-regression baseline, and `distanceAuc` and
    `distanceBrier` are the distance-only baseline.
  - `logisticBrier`, `distanceAuc`, `distanceBrier`, `rows`, and `hits` are
    optional.
- `overall`: `[low, high]` 95% bootstrap intervals. `distanceAuc` is optional.
- `overallPoint` (optional): the point estimates for the same metrics.
- `calibration[].predicted` (optional): the mean predicted probability in the
  bin.
- `cohorts`, `excludedEvents`, `excludedFromMetrics`, `evaluationPolicy`
  (optional): which events count and why. The interface lists excluded
  events with their reasons rather than hiding them.
- `bootstrapEventDraws`, `ensembleMembersPerFold` (optional): numbers.
- `...Definition`, `lowConfidenceRule`, `limitations` (optional): free text.

## `forecasts.json`: input cost forecasts (phase 2; may be missing)

```json
{
  "sampleData": false,
  "asOf": "2026-10-14",
  "model": {
    "id": "amazon/chronos-bolt-small",
    "title": "Amazon Chronos-Bolt small pretrained forecasting model",
    "url": "https://huggingface.co/amazon/chronos-bolt-small",
    "revision": "772f3d2...",
    "weightsSha256": "06a6a19...",
    "releasedOn": "2024-11-26",
    "device": "cpu",
    "torchVersion": "2.14.1+cpu",
    "quantiles": [0.1, 0.5, 0.9],
    "quantileRearrangement": "Sorted independently at each forecast step"
  },
  "evaluationDefinition": "...",
  "intervalDefinition": "...",
  "baselineIntervalDefinition": "...",
  "limitations": ["..."],
  "series": [
    {
      "id": "copper",
      "label": "Copper",
      "unit": "USD per tonne",
      "source": { "title": "World Bank commodity prices", "url": "https://..." },
      "definitionSource": { "title": "...", "url": "https://...", "basis": "..." },
      "availabilityNote": "...",
      "historyThrough": "2026-09-01",
      "forecastStatus": "latest verified vintage",
      "history": [{ "date": "2026-01-01", "value": 0, "weeklyObservations": 4 }],
      "forecast": [{ "date": "2026-11-01", "q10": 0, "q50": 0, "q90": 0 }],
      "baseline": [{ "date": "2026-11-01", "value": 0 }],
      "metrics": {
        "mase": 0.0,
        "baselineMase": 1.0,
        "coverage80": 0.0,
        "baselineCoverage80": 0.0,
        "pinballLoss": 0.0,
        "baselinePinballLoss": 0.0,
        "origins": 24,
        "horizonMonths": 6,
        "scoredPredictions": 144,
        "firstTarget": "2024-05-01",
        "lastTarget": "2026-09-01",
        "aggregation": "...",
        "afterPublicReleaseOneMonth": { "...": "the same metric fields, plus note" }
      }
    }
  ]
}
```

- Top level: `asOf`, `model`, the three `...Definition` fields, and
  `limitations` are optional.
- Per series, these are optional:
  - `definitionSource`, `availabilityNote`: notes on the data. The freight
    series is archived and is a regional route, not a global rate.
  - `historyThrough`: the last month of history.
  - `forecastStatus`: `latest verified vintage` or `archived`.
  - `history[].weeklyObservations`: weekly points averaged into the month.
- `metrics` must have `mase`, `baselineMase`, and `coverage80`; every other
  metric field is optional.
