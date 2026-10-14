# Retrospective market-response model

Run in the project's WSL `.venv`. The SEC downloaders run with standard-library
Python on Windows and require `SEC_USER_AGENT` in that process's environment.

```bash
python -m pipeline.size_facts
python -m pipeline.historical_profiles --download
.venv/bin/python -m pipeline.historical_profiles
.venv/bin/python -m ml.features
.venv/bin/python -m ml.train
bash autopilot/checks/ml.sh
```

`features.csv` contains one company/event row, including companies without an
observable market label. Financial attributes use annual reports and company
facts published before the event cutoff; no unknown publication date or
same-day release enters the model. Fiscal-year identifiers come from DEI or
accession-matched SEC facts, rather than assuming a calendar period-end year.
The extra rule-based extraction has its own `pre_event_attributes.csv` audit
sheet and leaves M3's 30-row human review sheet intact.

Distance uses disclosed manufacturing-location centroids; headquarters do not
substitute for factories. Country HHI measures disclosed location-row counts,
which differ in granularity across Supplier List editions. It does not measure
actual sourcing shares. City exposure is unknown when only an overlapping
province or country is given; lower/upper geographic bounds are retained.

Hops describe an undirected disclosure graph: supplier locations, supplier
companies, Apple as the customer, and inferred geographic exposure. Every graph
node and edge has sources. This is not a transport or material-flow graph.
Without a verified geographic attachment, shock hops are missing. Route
dependence comes only from dated evidence in `chokepoint_evidence.json`, and
stays null when evidence is absent. A bank name containing “Suez” and a risk
discussion published after an event do not establish pre-event route dependence.

Leave-one-event-out fitting excludes the entire target event. An additional
training event supplies early stopping for shallow LightGBM trees; the selected
tree count is fixed while 200 models refit bootstrap samples of the remaining
training events. There are 200 models per outer fold, so the approved nine-event
run fits 1,800 bootstrap models. Neither categorical encoding nor logistic imputation
and scaling uses the held-out event. The logistic baseline uses all features;
the distance-only rule uses an exponential distance score calibrated on the
training sample and a training-prevalence fallback for unavailable distances.

Company probabilities are bootstrap medians and node intervals are the
2.5/97.5 percentiles. TreeSHAP is averaged across models in raw log-odds units;
categorical dummy effects are summed. Its base plus contributions reconstruct
the mean raw score, which differs from the logit of the median probability.
Overall metric intervals resample whole events in 2,000 draws. Calibration bins
contain actual held-out observations; empty bins are omitted.

Outputs are `metrics.json`, `held_out_predictions.csv`, company/site prediction
JSONs, `feature_metadata.json`, and `ml/model_manifest.json`. Models, source
reports, disclosure graphs, and downloaded native libraries stay in `data/raw/`.
The OpenMP fallback loads a SHA-256-pinned Ubuntu library from the project cache
on Linux amd64. It does not install an OS package.

The target is a statistically negative company stock return, without a causal
claim about disruptions or a measurement of factory damage. Site projections
share their company's prediction and market outcome. Unlisted-company
projections are extrapolations, without an observed stock-market outcome.
All projections carry `lowConfidence` while important public route information
is unavailable. Intervals describe conditional model variability, without
claiming to cover unreported routing or geographic measurement error. Supplier
membership is retrospective and the current listing universe has survivorship
limits. Model results must be reported even when a baseline performs better.
# Monthly cost forecasts (M8)

`pipeline/costs.py --download` verifies the pinned World Bank October 2026
workbook and the openly published Chen, Feng and Tang (2026) research
supplement. It preserves complete monthly metal prices in USD per tonne.
The freight series averages the supplement's weekly SCFI Shanghai–Europe
rates in USD per TEU; it is not the global composite index. Incomplete boundary
months are discarded and missing months are rejected. Source URLs and hashes
are recorded in `data/sources/costs.json`.

The metal history runs through September 2026. Public freight history ends
April 2025, and its clearly labeled archived forecast starts May 2025.
`data/review/cost_gaps.json` records the gap. No current rates or Apple
contract prices are inferred from this regional archive.

Download the pinned 48M-parameter Amazon Chronos-Bolt small model with
`python pipeline/download_forecast_model.py`, then run
`.venv/bin/python -m ml.forecast`. Weights stay in ignored `data/raw/` and are
checksum-verified before CPU inference. No fine-tuning or API key is used.
The pinned CPU PyTorch wheel comes from the official PyTorch wheel index;
all Python packages are installed in the project `.venv`.

The rolling evaluation uses 24 expanding-window origins and a six-month
horizon. Each forecast, seasonal baseline, and MASE denominator uses only its
origin's history. Seasonal naive repeats the last 12 months; its reference
band uses training seasonal residual quantiles. Metrics include mean absolute
scaled error, mean pinball loss at 0.1/0.5/0.9, and empirical central 80% coverage
for both methods. Pinball loss retains each series' units. Quantiles are
rearranged monotonically per step before scoring and export. Overlapping
targets are dependent; scores do not claim independent-sample intervals.

The backtest uses the downloaded data vintage rather than historical release
vintages. Unknown overlap with foundation-model training data limits older
scores. A separate one-month rolling check starts after the reported November
2024 model release; the freight check has only five targets and remains weak
evidence. No model or hyperparameter was chosen using these test outcomes.

`data/processed/forecast_backtest.csv` retains every scored target and its
origin, training-only scale, baseline, and quantiles. `forecasts.json` retains
the full history, source, units, six future steps, baseline, model revision,
scores, and limitations. Run `.venv/bin/python pipeline/export.py` to publish
it through the owned exporter and validate the result with
`.venv/bin/python pipeline/validate.py web/public/data/real`.

## Indexed planning model (M9; approved)

The kit has no referenced methods document or operational capacity/cost
inputs. `data/review/optimizer_method_proposal.md` and its proposed input JSON
record the method and exact ranges explicitly approved by the user on
2026-10-14. Approved inputs are in `data/sources/optimizer_assumptions.json`.
`ml.optimize` implements a parameterized OR-Tools GLOP LP, tested on small
examples. `.venv/bin/python -m ml.optimize --review` runs 1,000 paired Monte
Carlo draws per event for all eight switch combinations and writes only
`data/review/optimizer_preview.json`. Draws stay in ignored `data/raw/optimizer/`.

The objective minimizes unmet indexed demand plus an incremental cost penalty,
subject to weekly capacity, lead time, and linear ramp bounds. All operational
inputs are explicit assumption ranges. Quota curves are pointwise medians,
bands are 2.5th/97.5th percentiles, and sensitivity correlates inputs with
default-plan unmet demand. Individual option recoveries overlap and must not
be added; exact paired combination plans are supplied. Illustrative planning
outputs use `sampleData: true` in addition to assumption and unit labels.

Normal runs require `data/sources/optimizer_assumptions.json` with explicit
approval, save `data/processed/optimizer_plans.json`, and publish only through
`pipeline/export.py`. The exporter refuses review-only or unapproved plans;
the validator checks the approval, scope, weekly bands, complete option
combinations, and default-plan consistency. Actual Apple output and revenue
losses remain unknown. No inferred physical routes are created from this LP.

## Event expansion (M10; approved nine-event set)

The user approved nine events and preservation of the missing-year gaps on
2026-10-14, recorded in `data/sources/event_expansion.json`. Japan's 2011
earthquake, Thailand's 2011 industrial floods, and Russia's 2022 export
restrictions join the original six. Japan–Korea 2019, Taiwan 2024, and Helene
2024 remain sourced but excluded because verified FY2019/FY2024 lists are
unavailable. No nearby-year proxies are authorized.

Both 2011 cohorts use the January 2012 Apple publication headed "Apple
Suppliers 2011", as explicitly authorized by M10. Its 156 company names
contain no manufacturing locations or countries. Those geographic predictors
stay missing. The two scenario exports have empty physical networks and
`companyPredictions` with company probabilities, intervals, SHAP, citations,
and observable company CARs. Consumer support for this approved field belongs
to Claude. The earthquake uses the USGS epicenter and timestamp; Thailand uses
the Rojana first-inundation date and an explicitly coarse province centroid.
Russia's policy reference point is a country centroid, without inferred
factory exposure. These are event anchors, not invented supplier locations.

Historical identity guards keep legacy Broadcom Corporation from borrowing
Avago's pre-acquisition stock or financial history, and legacy Coherent Inc.
from borrowing II-VI's. Unverified legacy series remain unavailable. The
pre-event SIC, exchange, annual-report, and price caches include earlier years;
current-universe survivorship limits remain explicit. Extraction is rule based.

Both 2011 supplier samples contain 54 valid labels and zero hits. Under the
user's recorded `evaluation_policy.json` decision, single-class events are
excluded from every reported metric, including pooled scores, calibration,
and metric-bootstrap resampling. Nine prediction folds still use the full
training cohorts, and all company predictions, CAR labels, and nine scenario
exports remain available. `metrics.events` counts seven evaluated events;
`predictionEvents` counts nine. `excludedFromMetrics` documents the omitted
events. Metrics condition on observed classes and do not summarize all nine
scenarios. Numeric AUC requirements remain unchanged.

Rebuild with `pipeline.supplier_lists --offline`, `pipeline.geocode --offline`,
`pipeline.events`, `pipeline.peer_controls --prices`, `pipeline.event_study`,
`ml.features`, `ml.train`, `ml.optimize`, and `pipeline.export` as Python
modules, then run the required ML checks. Metrics and model manifests retain
the per-event cohort qualifications and excluded-year gaps.
