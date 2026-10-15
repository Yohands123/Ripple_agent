# Ripple data contract

This contract describes `web/public/data/real/`, written only by
`pipeline/export.py`, and fictional examples in `contracts/fixtures/`.
The user approved nullable values, company-only predictions, backbone
extensions, and this complete contract update. Validate using
`python -m pipeline.validate <folder>`. `--frozen` diagnoses incompatibility
with the original numeric-only contract; it is not the current acceptance mode.

Ripple is a public-data resilience case study. Stock-response predictions do
not measure factory damage, production loss, Apple revenue, or recommended
operational actions. Inferences and assumptions must remain visible.

## Files and shared rules

- `network.json`: default network, currently Suez 2021.
- `networks/<eventId>.json`: own-year supplier cohort and separately dated
  reference geography for one event.
- `scenarios/index.json`: array of `{id,title,type,start}`.
- `scenarios/<eventId>.json`: shock, projections, route exposure and planning.
- `metrics.json`: company-level leave-one-event-out evaluation.
- `forecasts.json`: optional public input-cost histories and forecasts.

IDs are nonempty strings, unique within their document. Edge endpoints,
transit nodes, shock nodes, predictions and affected-route IDs reference the
event's network. `networkPath` is relative to the export folder, without
absolute paths or parent traversal. Its absence selects `network.json` for
legacy fixtures. Scenario and network `snapshotYear` must agree.

Dates use ISO `YYYY-MM-DD`; `establishedOn` may use `YYYY-MM`. Coordinates are
finite WGS84 longitude/latitude, within [-180,180]/[-90,90]. Waypoints always
use `[longitude,latitude]`. `precision` is `exact`, `city`, `province`, or
`country`; shock locations also allow `sea-area`. Exact describes a published
reference, not necessarily a surveyed factory or cargo terminal.

A `source` has descriptive `title` and absolute public HTTP(S) `url`.
`sources` is an array of these records. Real nodes/edges require sources;
empty arrays are permitted only for explicit sample fixtures. Some source
records add a `basis` explaining their interpretation. Local classification
references are separate provenance, not public source URLs.

`sampleData: true` must produce a visible sample-data indication. A scenario
can have a real historical event and still be sample data because its plan
is illustrative. Assumed quantities have `assumption: true`, ranges, and
definitions. Unknown values remain `null`; they must never become zero.

Link `status` is `known` only if a public source states the relationship;
otherwise it is `inferred`. Inferred edges have `confidence` and `basis`.
Confidence is qualitative `high`, `medium`, `low`, or `unknown`, not a
calibrated probability. `confidenceKind` explains the interpretation.

## Networks, cohorts and reference geography

Networks contain `snapshotYear`, `sampleData`, `nodes`, `edges`, plus optional
`eventId`, `asOfDate`, `scope`, `cohort`, `cohortBasis`, `coverage`, `backbone`,
and `supplyDefinition`.

`cohort` records snapshot/event/publication years, `yearBasis`,
`locationCoverage`, selection `basis`, and boolean `assumption`,
`proxyApproved`, `companyOnlyExportApproved`. Missing own-year rosters remain
gaps unless an approximation is explicitly approved. `coverage` counts
matched/manufacturing supplier locations, unlocated companies, backbone
nodes, supplier access links, backbone routes, supply links, model-eligible
supply links and tier-2 supply links. `locationCoverage: "undisclosed"` forbids
invented supplier coordinates. The 2011 company-only scenarios may still
contain separately dated backbone context.

`backbone` carries `referenceAsOf`, `scope`, `approval`, `routeDefinition`, and
`nearestGatewayDefinition`. Approval records the user decision, node kinds,
nullable carried tiers and proposal path. Contemporary reference geography
does not establish historical facility presence or Apple shipments.

Every node has `id`, `name`, `kind`, nullable `tier`, `lon`, `lat`, `precision`,
`region`, nullable `ticker`, nullable `partType`, nullable `appleRevenueShare`,
and `sources`. Known revenue shares lie in [0,1]. Node kinds are `mine`,
`refinery`, `supplier_major`, `supplier_minor`, `assembly`, `port`, `airport`,
`canal`, `border`, `apple_store`, `carrier`, `retailer`, `repair`, `hq`,
`chokepoint`, `sales_region`, `event_anchor`. Current layers are `supplier`
and `backbone`.

`companyId` groups a canonical supplier's sites and stock label. Backbone
context has no historical supplier company ID. `sourceCompany`,
`canonicalCompany`, and `supplierAliases` preserve identity provenance.
`locationRole` is `manufacturing` or `headquarters` when supplied.

`tier` is integer 1–7 or null. `tierStatus` is `known`, `inferred`, or
`unknown`; `tierBasis` explains it. Exact CSV matches fill null fields while
retaining filing-derived part types. Their status is `inferred`, basis is
`model classification, see data/reference/supplier_classes.csv`, and
confidence comes from the row. Empty CSV tiers stay null. For unmatched
names, materials/adhesives/glass/chemicals map to inferred tier 2; components
and other parts to tier 3; EMS/assembly to tier 4. Their basis is
`mapped from part type`. A missing part type leaves tier null.

`partTypeStatus` is `sourced`, `inferred`, or `unknown`. `partTypeScope`
distinguishes a company category from an Apple-specific bill of materials.
`attributeSources` contains evidence for `partType`, `appleRevenueShare`,
`size`, or `chokepoint_dependence`: `source`/`sources`, `filedOn`, and, for
size, `periodEnd` and `assetsUsd`.

`classification` retains matched company, canonical name, nullable tier/part
type, confidence, status, basis, classifier and local reference. An approved
`correction` has its own source, basis and reference. It does not silently
rewrite the supplied CSV.

Reference nodes may include `referenceAsOf`, `historicalPresenceAsserted`,
`status`, `scope`, `eventId`, `establishedOn`, `iata`, `worldPortIndex`, `mrgid`,
nullable `sourcePrecisionMeters`, `salesRegion`, `regionDefinition`, and
`gatewaySelectionBasis`. These describe a reference, not observed shipments.
`positionBasis`, `positionScope`, `positionStatus`, and
`publishedPosition: {lon,lat}` distinguish original coordinates from inferred
coastal/canal display anchors.

Assembly `products` lists evidenced product families. `productEvidence`
preserves products, public source, `availableOn`, basis, and publication-date
uncertainty notes. Conservative availability does not establish the site's
complete historical product mix.

`waypoint: true` marks an unlabelled route control node. Paired date-line
waypoints use `kind: "border"` and shared `seamId`: +180 and -180 represent the
same position on opposite map edges, not a real border facility. Never draw
a connector across the whole map between the pair.

## Edges: routes and supply relationships

Edges have `id`, `from`, `to`, `mode`, `carriesTier`, `status`, `sources`.
Current real edges also have `relation`, `confidence`, `basis`.
`carriesTier` is 1–7 or null for unknown originating tiers. Optional `layer`,
`referenceAsOf`, `purpose`, `confidenceKind`, `routingVerified`, `distanceKm`
and `distanceDefinition` state the inference. All current routes have
`routingVerified: false`; passing a geometry test does not establish actual
use, navigability, capacity, schedule, border permission or legality.

`relation: "route"` describes physical movement. Mode is `sea`, `air`, `road`,
or `rail`. Supplier roads choose the nearest curated port/airport by
great-circle reference distance, not driving distance or the nearest gateway
worldwide. Straight road connectors do not establish continuous roads or
viable crossings. Air arcs are illustrative, not documented flight paths.

Sea routes have `via` and `laneName`. `laneId` groups one lane's display
segments; `segmentIndex`/`segmentCount` are 1-based position/count.
`originId`/`destinationId` retain complete lane endpoints. Label each lane
once. `corridor`, `geometryBasis`, `geometrySources`, and
`narrowPassages: [{nodeId,scope}]` explain geometry. `viaNodeIds` identifies
transited chokepoints; `alternativeTo` references the original route.

Pacific lanes cross the North Pacific and split at the date line. Every sea
route must pass `pipeline/sea_geometry.py`, including the sampled curved ship
path, against exact pinned Natural Earth physical-land polygons. Allowances
are limited to 3 km around port endpoints and a 1 km cartographic corridor
around independently sourced Suez/Panama centerlines. Edge metadata cannot
bypass checks. Pins and offline geometry are in
`data/processed/sea_geometry.json` and `sea_land.wkb.gz`. Tolerances do not
describe surveyed channel widths or navigable water depths.

`relation: "supply"` describes who could supply whom, with null `mode`.
Tier-3 links require product compatibility and select at most three nearest
qualifying assembly hubs per company, one representative site per hub.
Tier-2 buyer links require public support. Optional `companyId`, `partType`,
`products`, `componentCategories`, `productUseEvidence`,
`assemblyProductEvidence`, `availableOn`, `supplierCategoryInferred`, and
`modelEligible` retain the inference and temporal eligibility.

Only model-eligible supply links enter historical hops. Dated evidence is
filtered before nearest-hub selection; current unsourced categories and
future assembly evidence cannot create predictive hops. Geographic supplier
exposure or an explicitly shocked assembly hub seeds zero hops. Undirected
supply traversal describes potential upstream/downstream association;
unconnected companies remain null. Route/access/shared-customer edges never
create model hops.

## Scenarios, predictions and exposures

Scenarios contain `id`, `title`, `type`, `start`, `end`, `snapshotYear`,
`sampleData`, `shock`, `headline`, `predictions`, `actual`, `options`, `quota`,
`money`, `affectedRoutes`, and `sensitivity`. Type is `sea`, `sky`, `land`,
`policy`, or `demand`. Optional extensions are `networkPath`, `cohort`,
`dateBasis`, `endBasis`, `sources`, `outcomeDefinition`, `unknowns`,
`companyPredictions`, `optimization`, and route-exposure provenance.

Date bases describe onset, announcement, report cutoff or reopening; `end`
does not automatically mean full recovery. The outcome is company
market-model CAR on trading days 0 through +10, hit when t < -1.96.
`unknowns` lists unmeasured quantities, never substituted zeros. Its production
tier entry gives the percentage of disclosed supplier sites with null tiers,
excluding backbone context. Company-only rosters have no site denominator and
say the share is unknown rather than inventing a percentage.

`shock.nodeIds` identifies sourced backbone shock locations and may be empty
if no node represents the event. `capacityLoss` is nullable or in [0,1].
`shock.location` has `lon`, `lat`, `precision`, `basis`, `sources`, independent
of the observed hit labels.

Predictions have `nodeId`, `pHit`, `ciLow`, `ciHigh`, `lowConfidence`, and
`shap: [{feature,value}]`. Require 0 <= ciLow <= pHit <= ciHigh <= 1.
`shapBaseValue` plus contributions equals `shapMeanRawScore`, the explained
point refit's raw log odds (the legacy field name is retained). `predictionScope` identifies company
projections shared by sites; `outcomeObservable` indicates a valid label.
`actual[]` contains `nodeId`, boolean `hit`, numeric `car`, optional `scope`.
Repeated display-site observations count once per company/event in metrics.

`companyPredictions[]` supports unlocated rosters: `companyId`, `supplier`,
nullable `ticker`, `sources`, the probability/SHAP/scope fields above, and
nullable `actual: {hit,car}`. No coordinates are invented for these companies.

`affectedRoutes` has `blocked`, `detour`, `expedited` arrays of physical route
IDs. Supply-edge IDs are invalid. A blocked route cannot also be available
as a detour or expedition. Real overlays carry `affectedRoutesStatus`,
`affectedRoutesBasis`, `affectedRoutesSources`, `affectedRoutesScope`.
Blocked means inferred potential exposure, not proof a gateway completely
closed or an Apple shipment stopped. Alternatives do not establish capacity,
permissions, use, or evasion of policy restrictions.

## Illustrative planning and sensitivity

Options may be empty; quota may be null. Each modeled option has `id`,
`label`, `detail`, range `unitsRecovered`, range `extraCostUsd`,
`daysToEffect`, `defaultOn`, `assumption`, optional `daysToEffectRange` and
`inputRanges`. Recoveries cannot be added independently across options.

Quota has matching arrays `weeks`, `target`, `noAction`, `withPlan`, and
`recoverySentence`. Optional per-week ranges are `noActionRange` and
`withPlanRange`. `optionPlans` gives every exact switch combination via
`optionIds`, `withPlan`, `withPlanRange`, `extraCostUsd`. `unit`, `scope`,
`assumption` remain visible: current quantities are assumed indexed demand,
not actual devices, shipments or Apple output.

Money has positive `coinUsd`, nullable range `revenueAtRisk`, nullable [0,1]
`delayedShare`, and `assumption`. Unknown money must not create estimated
coins or revenue claims. Each sensitivity item has code `assumption`,
plain-English `label`, and `spearman` in [-1,1], sorted by absolute value.
Positive correlation means more unmet indexed demand in the default plan.

Optimization preserves solver/runtime versions, seed, draws, paired
combination count, base-capacity ranges, default extra-cost range,
`inputRanges`, `scope`, `assumption`, `costDefinition`, `rangeDefinition`,
`sensitivityDefinition`. Input ranges retain explicit user approval, horizon,
demand/capacity/recovery/cost-penalty ranges, and option capacity/lead/ramp/
cost ranges. Current uniform ranges are illustrative; their percentile
intervals are not empirical confidence intervals.

## Metrics and forecasts

Metrics have `model`, `sampleData`, `events`, `loeo`, `overall`, `calibration`,
and the extensions enumerated below. `events` counts evaluated events;
`predictionEvents` also includes excluded events. `rows` counts company-event
observations. Per-event results have `eventId`, `rows`, `hits`, model
`auc`/`brier`, logistic `baselineAuc`/`logisticBrier`, distance
`distanceAuc`/`distanceBrier`. Never label `baselineAuc` as distance.

`overall` gives event-bootstrap [low,high] intervals; `overallPoint` pooled
point estimates. Calibration has `binMid`, mean `predicted`, `observed`, `n`.
`cohorts`, `excludedEvents`, `excludedFromMetrics`, `evaluationPolicy` explain
gaps and inclusion. The approved single-class policy excludes such events
from per-event and pooled metrics/calibration, while retaining predictions
and observations. Bootstrap draw/member counts, definition strings,
`lowConfidenceRule`, and `limitations` preserve methodological uncertainty.

Forecasts contain `sampleData`, optional `asOf`, model metadata, evaluation
and interval definitions, limitations, series. Model metadata includes
identity/title/public URL, revision, weights hash, release date, device,
runtime version, quantiles and rearrangement definition.

Series contain identity/label/unit/source, optional `definitionSource`,
`availabilityNote`, `historyThrough`, `forecastStatus`, and `history`,
`forecast`, `baseline`, `metrics`. History is `{date,value}` with optional
`weeklyObservations`; forecasts are `{date,q10,q50,q90}`, with ordered
quantiles; baseline is `{date,value}`. The archived freight series is a
particular regional route, not a current global rate.

Forecast metrics include MASE, baseline MASE, interval coverage, baseline
coverage, pinball losses, origins, horizon months, scored predictions,
first/last targets and aggregation. `afterPublicReleaseOneMonth` repeats
metrics for the release-aware subset and includes a note. A pre-release
backtest is not a contemporaneously available forecast.

The inventory below explicitly lists every nested field and observed type.
Generate it with `python -m pipeline.contract_inventory`; `--check` detects
undocumented export changes. Variant-specific evidence and assumption
fields are retained rather than silently discarded by loaders.

## Three-candidate nested model selection

The main `model` may be `distance`, `logistic_regression`, or `lightgbm`.
`modelReason` explains the fixed selection rule and observed pick count.
`modelSelection` records the complete seven-event nested procedure:

- `protocolVersion`, `protocolSha256`, and `selectionMetric` identify the
  frozen protocol. Features, labels and candidate settings are hashed before
  the new run. Earlier analyses had already been observed.
- `outerFolds` contains seven records. Each has `eventId`, six
  `trainingEvents`, `selectedModel`, `innerMeanAuc`, six `innerFolds`,
  `outerAuc`, `outerAuc95`, and an apparent-training LightGBM diagnostic.
  Each inner record has `heldOutEvent`, five `trainingEvents`, and `auc`
  keyed by all three candidates. The outer event is absent from every inner
  fit, score and stopping decision. Selection maximizes the arithmetic mean
  of six event AUCs; the frozen tie order is distance, logistic, LightGBM.
- `selectionCounts` maps candidate names to pick counts totaling seven.
  `mainModel` is the modal candidate; `mainModelPickCount` is its count.
  `mainModelReason` explains this choice. The export uses this family for
  every scenario, with own-event-held-out refits for evaluated events.
- `nestedAuc` and `nestedAuc95` score the probabilities from each fold's
  individually selected family. The 95% interval resamples seven event
  blocks 2,000 times with fixed saved probabilities; it does not retrain
  or repeat selection inside each bootstrap draw.
- `candidateOverall` retains each fixed candidate's pooled `auc`, `brier`,
  and `auc95`. `scoreScope` and `uncertaintyDefinition` distinguish these
  descriptive comparisons from evaluation of the complete nested selector.
  Selection of the modal family across all folds is data-dependent; its
  fixed-family top-level score must not be substituted for a different
  fold-selected nested score. They coincide when every fold picks it.

`loeo[].auc95` is an object with `auc`, `baselineAuc`, and `distanceAuc`
95% intervals. Each event uses 10,000 paired stratified company bootstrap
draws, conditional on its observed hit/non-hit counts. This is not an
event-cluster interval or a refitting interval. Correlated company returns
and retrospective cohort/feature uncertainty remain outside these bounds.

`evaluationPolicy.trainingPolicySource` identifies the newer seven-event
training rule. The two single-class 2011 events enter neither fitting nor
model selection; their company-only projections fit the modal family on
all seven eligible events and stay excluded from metrics.

Each prediction may carry `predictionModel` and `explanationMethod`.
`pHit` now comes from the selected family's full-training point refit.
`predictionIntervalDefinition` describes 200 event-bootstrap uncertainty
refits of that family; percentile bounds are conservatively expanded to
include the point if needed. `ensembleMembersPerFold` counts these refits,
not averaging in the reported point estimator.

`shap` remains an exact additive raw-score decomposition for that point
refit. `explanationMethod` distinguishes native TreeSHAP, interventional
linear SHAP, and exact single-input distance SHAP using the empirical
training-distance background. Distance log odds are clipped numerically at
probabilities 1e-12 and 1-1e-12 for finite explanations. The legacy field
`shapMeanRawScore` now names the explained point refit's raw score; it is not
a bootstrap mean. Base plus contributions still equals that raw score.

Node `layer` is `supplier` or `backbone`; edge `layer` may be `backbone`,
`supplier_access`, or `supply`. `relation` distinguishes movement routes
from possible supply relationships. `laneName` is the label, `corridor` the
geographic description, `viaNodeIds` the transited nodes, and `alternativeTo`
the referenced original route. Edge `confidence` is qualitative, with
`confidenceKind` and `basis` explaining the inference. New reference kinds
`chokepoint`, `sales_region`, `event_anchor` require the backbone layer;
they never become observed supplier outcomes.

<!-- BEGIN REAL EXPORT FIELD INVENTORY -->
## Complete real-export field inventory

Every emitted field is enumerated below, including nested evidence and assumption records. Types describe observed JSON values; the semantic rules above define allowed nulls and ranges. Variant-specific fields are optional. `[]` denotes array elements; `$` denotes the root. Integer is a subtype of number. Qualitative confidence is never a probability.

### Forecasts

| Field | Observed JSON types |
|---|---|
| `$` | object |
| `asOf` | string |
| `baselineIntervalDefinition` | string |
| `evaluationDefinition` | string |
| `intervalDefinition` | string |
| `limitations` | array |
| `limitations[]` | string |
| `model` | object |
| `model.device` | string |
| `model.id` | string |
| `model.quantileRearrangement` | string |
| `model.quantiles` | array |
| `model.quantiles[]` | number |
| `model.releasedOn` | string |
| `model.revision` | string |
| `model.title` | string |
| `model.torchVersion` | string |
| `model.url` | string |
| `model.weightsSha256` | string |
| `sampleData` | boolean |
| `series` | array |
| `series[]` | object |
| `series[].availabilityNote` | string |
| `series[].baseline` | array |
| `series[].baseline[]` | object |
| `series[].baseline[].date` | string |
| `series[].baseline[].value` | number |
| `series[].definitionSource` | object |
| `series[].definitionSource.basis` | string |
| `series[].definitionSource.title` | string |
| `series[].definitionSource.url` | string |
| `series[].forecast` | array |
| `series[].forecastStatus` | string |
| `series[].forecast[]` | object |
| `series[].forecast[].date` | string |
| `series[].forecast[].q10` | number |
| `series[].forecast[].q50` | number |
| `series[].forecast[].q90` | number |
| `series[].history` | array |
| `series[].historyThrough` | string |
| `series[].history[]` | object |
| `series[].history[].date` | string |
| `series[].history[].value` | number |
| `series[].history[].weeklyObservations` | integer |
| `series[].id` | string |
| `series[].label` | string |
| `series[].metrics` | object |
| `series[].metrics.afterPublicReleaseOneMonth` | object |
| `series[].metrics.afterPublicReleaseOneMonth.aggregation` | string |
| `series[].metrics.afterPublicReleaseOneMonth.baselineCoverage80` | number |
| `series[].metrics.afterPublicReleaseOneMonth.baselineMase` | number |
| `series[].metrics.afterPublicReleaseOneMonth.baselinePinballLoss` | number |
| `series[].metrics.afterPublicReleaseOneMonth.coverage80` | number |
| `series[].metrics.afterPublicReleaseOneMonth.firstTarget` | string |
| `series[].metrics.afterPublicReleaseOneMonth.horizonMonths` | integer |
| `series[].metrics.afterPublicReleaseOneMonth.lastTarget` | string |
| `series[].metrics.afterPublicReleaseOneMonth.mase` | number |
| `series[].metrics.afterPublicReleaseOneMonth.note` | string |
| `series[].metrics.afterPublicReleaseOneMonth.origins` | integer |
| `series[].metrics.afterPublicReleaseOneMonth.pinballLoss` | number |
| `series[].metrics.afterPublicReleaseOneMonth.scoredPredictions` | integer |
| `series[].metrics.aggregation` | string |
| `series[].metrics.baselineCoverage80` | number |
| `series[].metrics.baselineMase` | number |
| `series[].metrics.baselinePinballLoss` | number |
| `series[].metrics.coverage80` | number |
| `series[].metrics.firstTarget` | string |
| `series[].metrics.horizonMonths` | integer |
| `series[].metrics.lastTarget` | string |
| `series[].metrics.mase` | number |
| `series[].metrics.origins` | integer |
| `series[].metrics.pinballLoss` | number |
| `series[].metrics.scoredPredictions` | integer |
| `series[].source` | object |
| `series[].source.title` | string |
| `series[].source.url` | string |
| `series[].unit` | string |

### Metrics

| Field | Observed JSON types |
|---|---|
| `$` | object |
| `baselineDefinition` | string |
| `bootstrapEventDraws` | integer |
| `calibration` | array |
| `calibration[]` | object |
| `calibration[].binMid` | number |
| `calibration[].n` | integer |
| `calibration[].observed` | number |
| `calibration[].predicted` | number |
| `cohorts` | array |
| `cohorts[]` | object |
| `cohorts[].assumption` | boolean |
| `cohorts[].basis` | string |
| `cohorts[].companyOnlyExportApproved` | boolean |
| `cohorts[].eventId` | string |
| `cohorts[].eventYear` | integer |
| `cohorts[].locationCoverage` | string |
| `cohorts[].proxyApproved` | boolean |
| `cohorts[].publicationYear` | integer |
| `cohorts[].snapshotYear` | integer |
| `cohorts[].yearBasis` | string |
| `ensembleMembersPerFold` | integer |
| `evaluationDefinition` | string |
| `evaluationPolicy` | object |
| `evaluationPolicy.approvalDate` | string |
| `evaluationPolicy.approved` | boolean |
| `evaluationPolicy.limitation` | string |
| `evaluationPolicy.scope` | string |
| `evaluationPolicy.singleClassEvents` | string |
| `evaluationPolicy.trainingPolicySource` | string |
| `evaluationPolicy.userDecision` | string |
| `events` | integer |
| `excludedEvents` | array |
| `excludedEvents[]` | object |
| `excludedEvents[].eventId` | string |
| `excludedEvents[].reason` | string |
| `excludedEvents[].snapshotYear` | integer |
| `excludedEvents[].source` | object |
| `excludedEvents[].source.title` | string |
| `excludedEvents[].source.url` | string |
| `excludedFromMetrics` | array |
| `excludedFromMetrics[]` | object |
| `excludedFromMetrics[].eventId` | string |
| `excludedFromMetrics[].hits` | integer |
| `excludedFromMetrics[].reason` | string |
| `excludedFromMetrics[].rows` | integer |
| `limitations` | array |
| `limitations[]` | string |
| `loeo` | array |
| `loeo[]` | object |
| `loeo[].auc` | number |
| `loeo[].auc95` | object |
| `loeo[].auc95.auc` | array |
| `loeo[].auc95.auc[]` | number |
| `loeo[].auc95.baselineAuc` | array |
| `loeo[].auc95.baselineAuc[]` | number |
| `loeo[].auc95.distanceAuc` | array |
| `loeo[].auc95.distanceAuc[]` | number |
| `loeo[].baselineAuc` | number |
| `loeo[].brier` | number |
| `loeo[].distanceAuc` | number |
| `loeo[].distanceBrier` | number |
| `loeo[].eventId` | string |
| `loeo[].hits` | integer |
| `loeo[].logisticBrier` | number |
| `loeo[].rows` | integer |
| `lowConfidenceRule` | string |
| `model` | string |
| `modelReason` | string |
| `modelSelection` | object |
| `modelSelection.candidateOverall` | object |
| `modelSelection.candidateOverall.distance` | object |
| `modelSelection.candidateOverall.distance.auc` | number |
| `modelSelection.candidateOverall.distance.auc95` | array |
| `modelSelection.candidateOverall.distance.auc95[]` | number |
| `modelSelection.candidateOverall.distance.brier` | number |
| `modelSelection.candidateOverall.lightgbm` | object |
| `modelSelection.candidateOverall.lightgbm.auc` | number |
| `modelSelection.candidateOverall.lightgbm.auc95` | array |
| `modelSelection.candidateOverall.lightgbm.auc95[]` | number |
| `modelSelection.candidateOverall.lightgbm.brier` | number |
| `modelSelection.candidateOverall.logistic_regression` | object |
| `modelSelection.candidateOverall.logistic_regression.auc` | number |
| `modelSelection.candidateOverall.logistic_regression.auc95` | array |
| `modelSelection.candidateOverall.logistic_regression.auc95[]` | number |
| `modelSelection.candidateOverall.logistic_regression.brier` | number |
| `modelSelection.mainModel` | string |
| `modelSelection.mainModelPickCount` | integer |
| `modelSelection.mainModelReason` | string |
| `modelSelection.nestedAuc` | number |
| `modelSelection.nestedAuc95` | array |
| `modelSelection.nestedAuc95[]` | number |
| `modelSelection.outerFolds` | array |
| `modelSelection.outerFolds[]` | object |
| `modelSelection.outerFolds[].eventId` | string |
| `modelSelection.outerFolds[].innerFolds` | array |
| `modelSelection.outerFolds[].innerFolds[]` | object |
| `modelSelection.outerFolds[].innerFolds[].auc` | object |
| `modelSelection.outerFolds[].innerFolds[].auc.distance` | number |
| `modelSelection.outerFolds[].innerFolds[].auc.lightgbm` | number |
| `modelSelection.outerFolds[].innerFolds[].auc.logistic_regression` | number |
| `modelSelection.outerFolds[].innerFolds[].heldOutEvent` | string |
| `modelSelection.outerFolds[].innerFolds[].trainingEvents` | array |
| `modelSelection.outerFolds[].innerFolds[].trainingEvents[]` | string |
| `modelSelection.outerFolds[].innerMeanAuc` | object |
| `modelSelection.outerFolds[].innerMeanAuc.distance` | number |
| `modelSelection.outerFolds[].innerMeanAuc.lightgbm` | number |
| `modelSelection.outerFolds[].innerMeanAuc.logistic_regression` | number |
| `modelSelection.outerFolds[].lightgbmApparentTrainingAuc` | number |
| `modelSelection.outerFolds[].outerAuc` | number |
| `modelSelection.outerFolds[].outerAuc95` | array |
| `modelSelection.outerFolds[].outerAuc95[]` | number |
| `modelSelection.outerFolds[].selectedModel` | string |
| `modelSelection.outerFolds[].trainingEvents` | array |
| `modelSelection.outerFolds[].trainingEvents[]` | string |
| `modelSelection.protocolSha256` | string |
| `modelSelection.protocolVersion` | string |
| `modelSelection.scoreScope` | string |
| `modelSelection.selectionCounts` | object |
| `modelSelection.selectionCounts.distance` | integer |
| `modelSelection.selectionCounts.lightgbm` | integer |
| `modelSelection.selectionCounts.logistic_regression` | integer |
| `modelSelection.selectionMetric` | string |
| `modelSelection.uncertaintyDefinition` | string |
| `overall` | object |
| `overall.auc` | array |
| `overall.auc[]` | number |
| `overall.baselineAuc` | array |
| `overall.baselineAuc[]` | number |
| `overall.brier` | array |
| `overall.brier[]` | number |
| `overall.distanceAuc` | array |
| `overall.distanceAuc[]` | number |
| `overallPoint` | object |
| `overallPoint.auc` | number |
| `overallPoint.baselineAuc` | number |
| `overallPoint.brier` | number |
| `overallPoint.distanceAuc` | number |
| `predictionEvents` | integer |
| `predictionIntervalDefinition` | string |
| `probabilityDefinition` | string |
| `rows` | integer |
| `sampleData` | boolean |
| `shapDefinition` | string |

### Network

| Field | Observed JSON types |
|---|---|
| `$` | object |
| `asOfDate` | string |
| `backbone` | object |
| `backbone.approval` | object |
| `backbone.approval.approved` | boolean |
| `backbone.approval.decision` | string |
| `backbone.approval.nodeKinds` | array |
| `backbone.approval.nodeKinds[]` | string |
| `backbone.approval.nullableCarriesTier` | boolean |
| `backbone.approval.proposal` | string |
| `backbone.nearestGatewayDefinition` | string |
| `backbone.referenceAsOf` | string |
| `backbone.routeDefinition` | string |
| `backbone.scope` | string |
| `cohort` | object |
| `cohort.assumption` | boolean |
| `cohort.basis` | string |
| `cohort.companyOnlyExportApproved` | boolean |
| `cohort.eventYear` | integer |
| `cohort.locationCoverage` | string |
| `cohort.proxyApproved` | boolean |
| `cohort.publicationYear` | integer |
| `cohort.snapshotYear` | integer |
| `cohort.yearBasis` | string |
| `cohortBasis` | string |
| `coverage` | object |
| `coverage.backboneNodes` | integer |
| `coverage.backboneRoutes` | integer |
| `coverage.locationCoverage` | string |
| `coverage.manufacturingLocations` | integer |
| `coverage.matchedLocations` | integer |
| `coverage.modelEligibleSupplyLinks` | integer |
| `coverage.supplierAccessLinks` | integer |
| `coverage.supplyLinks` | integer |
| `coverage.tier2SupplyLinks` | integer |
| `coverage.unlocatedCompanies` | integer |
| `edges` | array |
| `edges[]` | object |
| `edges[].alternativeTo` | string |
| `edges[].assemblyProductEvidence` | object |
| `edges[].assemblyProductEvidence.availableOn` | string |
| `edges[].assemblyProductEvidence.basis` | string |
| `edges[].assemblyProductEvidence.products` | array |
| `edges[].assemblyProductEvidence.products[]` | string |
| `edges[].assemblyProductEvidence.source` | object |
| `edges[].assemblyProductEvidence.source.title` | string |
| `edges[].assemblyProductEvidence.source.url` | string |
| `edges[].availableOn` | string |
| `edges[].basis` | string |
| `edges[].carriesTier` | integer, null |
| `edges[].companyId` | string |
| `edges[].componentCategories` | array |
| `edges[].componentCategories[]` | string |
| `edges[].confidence` | string |
| `edges[].confidenceKind` | string |
| `edges[].corridor` | string |
| `edges[].destinationId` | string |
| `edges[].distanceDefinition` | string |
| `edges[].distanceKm` | number |
| `edges[].from` | string |
| `edges[].geometryBasis` | string |
| `edges[].geometrySources` | array |
| `edges[].geometrySources[]` | object |
| `edges[].geometrySources[].title` | string |
| `edges[].geometrySources[].url` | string |
| `edges[].id` | string |
| `edges[].laneId` | string |
| `edges[].laneName` | string |
| `edges[].layer` | string |
| `edges[].mode` | null, string |
| `edges[].modelEligible` | boolean |
| `edges[].narrowPassages` | array |
| `edges[].narrowPassages[]` | object |
| `edges[].narrowPassages[].nodeId` | string |
| `edges[].narrowPassages[].scope` | string |
| `edges[].originId` | string |
| `edges[].partType` | string |
| `edges[].productUseEvidence` | array |
| `edges[].productUseEvidence[]` | object |
| `edges[].productUseEvidence[].availableOn` | string |
| `edges[].productUseEvidence[].categories` | array |
| `edges[].productUseEvidence[].categories[]` | string |
| `edges[].productUseEvidence[].product` | string |
| `edges[].productUseEvidence[].source` | object |
| `edges[].productUseEvidence[].source.title` | string |
| `edges[].productUseEvidence[].source.url` | string |
| `edges[].products` | array |
| `edges[].products[]` | string |
| `edges[].purpose` | string |
| `edges[].referenceAsOf` | string |
| `edges[].relation` | string |
| `edges[].routingVerified` | boolean |
| `edges[].segmentCount` | integer |
| `edges[].segmentIndex` | integer |
| `edges[].sources` | array |
| `edges[].sources[]` | object |
| `edges[].sources[].title` | string |
| `edges[].sources[].url` | string |
| `edges[].status` | string |
| `edges[].supplierCategoryInferred` | boolean |
| `edges[].to` | string |
| `edges[].via` | array |
| `edges[].viaNodeIds` | array |
| `edges[].viaNodeIds[]` | string |
| `edges[].via[]` | array |
| `edges[].via[][]` | number |
| `eventId` | string |
| `nodes` | array |
| `nodes[]` | object |
| `nodes[].appleRevenueShare` | null, number |
| `nodes[].attributeSources` | object |
| `nodes[].attributeSources.appleRevenueShare` | object |
| `nodes[].attributeSources.appleRevenueShare.filedOn` | string |
| `nodes[].attributeSources.appleRevenueShare.source` | object |
| `nodes[].attributeSources.appleRevenueShare.source.title` | string |
| `nodes[].attributeSources.appleRevenueShare.source.url` | string |
| `nodes[].attributeSources.partType` | object |
| `nodes[].attributeSources.partType.filedOn` | string |
| `nodes[].attributeSources.partType.source` | object |
| `nodes[].attributeSources.partType.source.title` | string |
| `nodes[].attributeSources.partType.source.url` | string |
| `nodes[].attributeSources.size` | object |
| `nodes[].attributeSources.size.assetsUsd` | integer |
| `nodes[].attributeSources.size.filedOn` | string |
| `nodes[].attributeSources.size.periodEnd` | string |
| `nodes[].attributeSources.size.source` | object |
| `nodes[].attributeSources.size.source.title` | string |
| `nodes[].attributeSources.size.source.url` | string |
| `nodes[].canonicalCompany` | string |
| `nodes[].classification` | object |
| `nodes[].classification.basis` | string |
| `nodes[].classification.canonicalCompany` | string |
| `nodes[].classification.classifiedBy` | string |
| `nodes[].classification.company` | string |
| `nodes[].classification.confidence` | string |
| `nodes[].classification.correction` | object |
| `nodes[].classification.correction.basis` | string |
| `nodes[].classification.correction.reference` | string |
| `nodes[].classification.correction.source` | object |
| `nodes[].classification.correction.source.title` | string |
| `nodes[].classification.correction.source.url` | string |
| `nodes[].classification.partType` | null, string |
| `nodes[].classification.reference` | string |
| `nodes[].classification.status` | string |
| `nodes[].classification.tier` | integer, null |
| `nodes[].companyId` | string |
| `nodes[].confidence` | string |
| `nodes[].confidenceKind` | string |
| `nodes[].establishedOn` | string |
| `nodes[].eventId` | string |
| `nodes[].gatewaySelectionBasis` | string |
| `nodes[].historicalPresenceAsserted` | boolean |
| `nodes[].iata` | string |
| `nodes[].id` | string |
| `nodes[].kind` | string |
| `nodes[].lat` | number |
| `nodes[].layer` | string |
| `nodes[].locationRole` | string |
| `nodes[].lon` | integer, number |
| `nodes[].mrgid` | integer |
| `nodes[].name` | string |
| `nodes[].partType` | null, string |
| `nodes[].partTypeScope` | string |
| `nodes[].partTypeStatus` | string |
| `nodes[].positionBasis` | string |
| `nodes[].positionScope` | string |
| `nodes[].positionStatus` | string |
| `nodes[].precision` | string |
| `nodes[].productEvidence` | object |
| `nodes[].productEvidence.availableOn` | string |
| `nodes[].productEvidence.basis` | string |
| `nodes[].productEvidence.products` | array |
| `nodes[].productEvidence.products[]` | string |
| `nodes[].productEvidence.source` | object |
| `nodes[].productEvidence.source.title` | string |
| `nodes[].productEvidence.source.url` | string |
| `nodes[].products` | array |
| `nodes[].products[]` | string |
| `nodes[].publishedPosition` | object |
| `nodes[].publishedPosition.lat` | number |
| `nodes[].publishedPosition.lon` | number |
| `nodes[].referenceAsOf` | string |
| `nodes[].region` | string |
| `nodes[].regionDefinition` | string |
| `nodes[].salesRegion` | string |
| `nodes[].scope` | string |
| `nodes[].seamId` | string |
| `nodes[].sourceCompany` | string |
| `nodes[].sourcePrecisionMeters` | integer, null |
| `nodes[].sources` | array |
| `nodes[].sources[]` | object |
| `nodes[].sources[].title` | string |
| `nodes[].sources[].url` | string |
| `nodes[].status` | string |
| `nodes[].supplierAliases` | array |
| `nodes[].supplierAliases[]` | string |
| `nodes[].ticker` | null, string |
| `nodes[].tier` | integer, null |
| `nodes[].tierBasis` | string |
| `nodes[].tierStatus` | string |
| `nodes[].waypoint` | boolean |
| `nodes[].worldPortIndex` | integer |
| `sampleData` | boolean |
| `scope` | string |
| `snapshotYear` | integer |
| `supplyDefinition` | string |

### Scenario

| Field | Observed JSON types |
|---|---|
| `$` | object |
| `actual` | array |
| `actual[]` | object |
| `actual[].car` | number |
| `actual[].hit` | boolean |
| `actual[].nodeId` | string |
| `actual[].scope` | string |
| `affectedRoutes` | object |
| `affectedRoutes.blocked` | array |
| `affectedRoutes.blocked[]` | string |
| `affectedRoutes.detour` | array |
| `affectedRoutes.detour[]` | string |
| `affectedRoutes.expedited` | array |
| `affectedRoutes.expedited[]` | string |
| `affectedRoutesBasis` | string |
| `affectedRoutesScope` | string |
| `affectedRoutesSources` | array |
| `affectedRoutesSources[]` | object |
| `affectedRoutesSources[].title` | string |
| `affectedRoutesSources[].url` | string |
| `affectedRoutesStatus` | string |
| `cohort` | object |
| `cohort.assumption` | boolean |
| `cohort.basis` | string |
| `cohort.companyOnlyExportApproved` | boolean |
| `cohort.eventYear` | integer |
| `cohort.locationCoverage` | string |
| `cohort.proxyApproved` | boolean |
| `cohort.publicationYear` | integer |
| `cohort.snapshotYear` | integer |
| `cohort.yearBasis` | string |
| `companyPredictions` | array |
| `companyPredictions[]` | object |
| `companyPredictions[].actual` | null, object |
| `companyPredictions[].actual.car` | number |
| `companyPredictions[].actual.hit` | boolean |
| `companyPredictions[].ciHigh` | number |
| `companyPredictions[].ciLow` | number |
| `companyPredictions[].companyId` | string |
| `companyPredictions[].explanationMethod` | string |
| `companyPredictions[].lowConfidence` | boolean |
| `companyPredictions[].outcomeObservable` | boolean |
| `companyPredictions[].pHit` | number |
| `companyPredictions[].predictionModel` | string |
| `companyPredictions[].predictionScope` | string |
| `companyPredictions[].shap` | array |
| `companyPredictions[].shapBaseValue` | number |
| `companyPredictions[].shapMeanRawScore` | number |
| `companyPredictions[].shap[]` | object |
| `companyPredictions[].shap[].feature` | string |
| `companyPredictions[].shap[].value` | number |
| `companyPredictions[].sources` | array |
| `companyPredictions[].sources[]` | object |
| `companyPredictions[].sources[].title` | string |
| `companyPredictions[].sources[].url` | string |
| `companyPredictions[].supplier` | string |
| `companyPredictions[].ticker` | null, string |
| `dateBasis` | string |
| `end` | string |
| `endBasis` | string |
| `headline` | string |
| `id` | string |
| `money` | object |
| `money.assumption` | boolean |
| `money.coinUsd` | integer |
| `money.delayedShare` | null |
| `money.revenueAtRisk` | null |
| `networkPath` | string |
| `optimization` | object |
| `optimization.assumption` | boolean |
| `optimization.baseCapacityRange` | array |
| `optimization.baseCapacityRange[]` | array |
| `optimization.baseCapacityRange[][]` | number |
| `optimization.costDefinition` | string |
| `optimization.defaultExtraCostUsd` | array |
| `optimization.defaultExtraCostUsd[]` | number |
| `optimization.draws` | integer |
| `optimization.inputRanges` | object |
| `optimization.inputRanges.approval` | object |
| `optimization.inputRanges.approval.basis` | string |
| `optimization.inputRanges.approval.date` | string |
| `optimization.inputRanges.approval.decision` | string |
| `optimization.inputRanges.approved` | boolean |
| `optimization.inputRanges.assumption` | boolean |
| `optimization.inputRanges.baseRecoveryWeeks` | array |
| `optimization.inputRanges.baseRecoveryWeeks[]` | integer |
| `optimization.inputRanges.costPenaltyUnitsPerUsd` | array |
| `optimization.inputRanges.costPenaltyUnitsPerUsd[]` | number |
| `optimization.inputRanges.demandPerWeek` | array |
| `optimization.inputRanges.demandPerWeek[]` | integer |
| `optimization.inputRanges.distribution` | string |
| `optimization.inputRanges.draws` | integer |
| `optimization.inputRanges.initialCapacityFraction` | array |
| `optimization.inputRanges.initialCapacityFraction[]` | number |
| `optimization.inputRanges.options` | array |
| `optimization.inputRanges.options[]` | object |
| `optimization.inputRanges.options[].assumption` | boolean |
| `optimization.inputRanges.options[].capacityPerWeek` | array |
| `optimization.inputRanges.options[].capacityPerWeek[]` | integer |
| `optimization.inputRanges.options[].costUsdPerIndexUnit` | array |
| `optimization.inputRanges.options[].costUsdPerIndexUnit[]` | integer |
| `optimization.inputRanges.options[].defaultOn` | boolean |
| `optimization.inputRanges.options[].id` | string |
| `optimization.inputRanges.options[].label` | string |
| `optimization.inputRanges.options[].leadWeeks` | array |
| `optimization.inputRanges.options[].leadWeeks[]` | integer |
| `optimization.inputRanges.options[].rampWeeks` | array |
| `optimization.inputRanges.options[].rampWeeks[]` | integer |
| `optimization.inputRanges.scope` | string |
| `optimization.inputRanges.seed` | integer |
| `optimization.inputRanges.unit` | string |
| `optimization.inputRanges.weeks` | integer |
| `optimization.ortoolsVersion` | string |
| `optimization.pairedOptionCombinations` | integer |
| `optimization.rangeDefinition` | string |
| `optimization.scope` | string |
| `optimization.seed` | integer |
| `optimization.sensitivityDefinition` | string |
| `optimization.solver` | string |
| `options` | array |
| `options[]` | object |
| `options[].assumption` | boolean |
| `options[].daysToEffect` | number |
| `options[].daysToEffectRange` | array |
| `options[].daysToEffectRange[]` | number |
| `options[].defaultOn` | boolean |
| `options[].detail` | string |
| `options[].extraCostUsd` | array |
| `options[].extraCostUsd[]` | number |
| `options[].id` | string |
| `options[].inputRanges` | object |
| `options[].inputRanges.assumption` | boolean |
| `options[].inputRanges.capacityPerWeek` | array |
| `options[].inputRanges.capacityPerWeek[]` | integer |
| `options[].inputRanges.costUsdPerIndexUnit` | array |
| `options[].inputRanges.costUsdPerIndexUnit[]` | integer |
| `options[].inputRanges.defaultOn` | boolean |
| `options[].inputRanges.id` | string |
| `options[].inputRanges.label` | string |
| `options[].inputRanges.leadWeeks` | array |
| `options[].inputRanges.leadWeeks[]` | integer |
| `options[].inputRanges.rampWeeks` | array |
| `options[].inputRanges.rampWeeks[]` | integer |
| `options[].label` | string |
| `options[].unitsRecovered` | array |
| `options[].unitsRecovered[]` | number |
| `outcomeDefinition` | string |
| `predictions` | array |
| `predictions[]` | object |
| `predictions[].ciHigh` | number |
| `predictions[].ciLow` | number |
| `predictions[].explanationMethod` | string |
| `predictions[].lowConfidence` | boolean |
| `predictions[].nodeId` | string |
| `predictions[].outcomeObservable` | boolean |
| `predictions[].pHit` | number |
| `predictions[].predictionModel` | string |
| `predictions[].predictionScope` | string |
| `predictions[].shap` | array |
| `predictions[].shapBaseValue` | number |
| `predictions[].shapMeanRawScore` | number |
| `predictions[].shap[]` | object |
| `predictions[].shap[].feature` | string |
| `predictions[].shap[].value` | number |
| `quota` | object |
| `quota.assumption` | boolean |
| `quota.noAction` | array |
| `quota.noActionRange` | array |
| `quota.noActionRange[]` | array |
| `quota.noActionRange[][]` | number |
| `quota.noAction[]` | number |
| `quota.optionPlans` | array |
| `quota.optionPlans[]` | object |
| `quota.optionPlans[].extraCostUsd` | array |
| `quota.optionPlans[].extraCostUsd[]` | number |
| `quota.optionPlans[].optionIds` | array |
| `quota.optionPlans[].optionIds[]` | string |
| `quota.optionPlans[].withPlan` | array |
| `quota.optionPlans[].withPlanRange` | array |
| `quota.optionPlans[].withPlanRange[]` | array |
| `quota.optionPlans[].withPlanRange[][]` | number |
| `quota.optionPlans[].withPlan[]` | number |
| `quota.recoverySentence` | string |
| `quota.scope` | string |
| `quota.target` | array |
| `quota.target[]` | number |
| `quota.unit` | string |
| `quota.weeks` | array |
| `quota.weeks[]` | string |
| `quota.withPlan` | array |
| `quota.withPlanRange` | array |
| `quota.withPlanRange[]` | array |
| `quota.withPlanRange[][]` | number |
| `quota.withPlan[]` | number |
| `sampleData` | boolean |
| `sensitivity` | array |
| `sensitivity[]` | object |
| `sensitivity[].assumption` | string |
| `sensitivity[].label` | string |
| `sensitivity[].spearman` | number |
| `shock` | object |
| `shock.capacityLoss` | null |
| `shock.location` | object |
| `shock.location.basis` | string |
| `shock.location.lat` | number |
| `shock.location.lon` | number |
| `shock.location.precision` | string |
| `shock.location.sources` | array |
| `shock.location.sources[]` | object |
| `shock.location.sources[].title` | string |
| `shock.location.sources[].url` | string |
| `shock.nodeIds` | array |
| `shock.nodeIds[]` | string |
| `snapshotYear` | integer |
| `sources` | array |
| `sources[]` | object |
| `sources[].title` | string |
| `sources[].url` | string |
| `start` | string |
| `title` | string |
| `type` | string |
| `unknowns` | array |
| `unknowns[]` | string |

### Scenario index

| Field | Observed JSON types |
|---|---|
| `$` | array |
| `[]` | object |
| `[].id` | string |
| `[].start` | string |
| `[].title` | string |
| `[].type` | string |

<!-- END REAL EXPORT FIELD INVENTORY -->
