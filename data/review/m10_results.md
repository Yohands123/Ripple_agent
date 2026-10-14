# M10 nine-event evaluation

This is the completed M10 snapshot before the later supplier-classification
and canonical-identity request. See `company_merge_comparison.md` for the
subsequent retrain and its AUC changes.

Retraining and production re-export are complete. The user chose to exclude
single-class events from metrics, recorded in `evaluation_policy.json`.
All nine scenario exports remain available; seven events contribute to scores.

The approved set adds Japan 2011, Thailand 2011, and Russia 2022 to the previous
six events. Japan–Korea 2019, Taiwan 2024, and Helene 2024 stay excluded because
verified own-year Supplier Lists are unavailable. Neither FY2018 nor FY2023
is substituted for a missing year.

The January 2012 Apple roster supplies 156 names for each 2011 event, explicitly
as the approved retrospective approximation. It supplies no factory locations.
All manufacturing-geography predictors remain missing, and the
`companyPredictions` exports retain 156 companies per event without coordinates.
There are 54 valid supplier CAR labels per 2011 event; 96 mappings are unavailable,
two estimation windows have missing observations, three market calendars are
insufficient, and legacy Broadcom's distinct historical series is unverified.
The current listing universe underrepresents delisted firms.

The full dataset has 1,655 supplier/event feature rows, 928 observable supplier
labels and 4,823 matched location/event projections. Each outer fold excludes
its entire event. Nine folds each fit 200 whole-event bootstrap models, with
nested early stopping. Reported metrics use 820 observations from seven events
with both classes, omitting both 2011 events from per-event scores, pooled
scores, calibration, and bootstrap resampling. Overall intervals use 2,000
draws over these seven events. This outcome-based selection limits the
interpretation of the reported metric population.

| Evaluation | LightGBM | Logistic baseline | Distance baseline |
|---|---:|---:|---:|
| Pooled held-out AUC | 0.451 | 0.582 | 0.629 |
| Event-bootstrap 95% AUC interval | 0.396–0.562 | 0.486–0.682 | 0.532–0.742 |

LightGBM's pooled Brier score is 0.0532 (95% event-bootstrap interval
0.0336–0.0742). It does not outperform these baselines on pooled AUC. Both 2011 supplier
samples have zero hits under the specified `t < -1.96` rule, so per-event AUC
is undefined for all three predictors. The user chose exclusion from all
metrics, while their 312 company predictions and 108 company CARs remain
in scenario exports and saved held-out predictions. No AUC is invented or
changed to null in the published metric folds.
The Thailand peer hit is not silently turned into a supplier training target.
An absence of significant negative CARs is not evidence of no supply disruption.

Every prediction has an ordered bootstrap interval and SHAP contributions
reconstructing its ensemble mean raw score. Raw models, annual reports, price
histories and 1,000 paired optimizer draws per event remain ignored in
`data/raw/`. All nine indexed optimizer plans include the eight exact switch
combinations and retain the approved illustrative-assumption labels. Metal
and archived freight forecasts from M8 are unchanged.

The target is company market response, not causal disruption loss or factory
damage. Physical routes remain unknown and every prediction is marked low
confidence. Rule-based filing extraction, retrospective membership, coarse or
absent geography, and current-universe survivorship limit this case study.

Verification: `bash autopilot/checks/ml.sh` passes all 92 tests and validates
both `contracts/fixtures` and `web/public/data/real`. The export audit checks
the nine/seven-event scope, company-only coverage, calibration row counts,
all 1,800 saved model hashes, held-out-event exclusion, and input hashes.
