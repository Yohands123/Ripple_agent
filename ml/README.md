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
training events. There are 200 models per outer fold, so the six-event run fits
1,200 bootstrap models. Neither categorical encoding nor logistic imputation
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
