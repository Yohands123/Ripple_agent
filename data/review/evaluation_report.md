# Evaluation of the fixed model before nested model selection

This report records the existing LightGBM model before the new model-selection procedure. No predictions, settings or exclusions were changed for this audit. Companies and hits are observed counts; AUCs below include 95% bootstrap intervals.

| Event | Companies | Hits | Model AUC (95%) | Logistic AUC (95%) | Distance AUC (95%) |
|---|---:|---:|---:|---:|---:|
| covid-china-2020 | 124 | 8 | 0.6008 [0.3297, 0.8545] | 0.5259 [0.2586, 0.8006] | 0.4445 [0.2651, 0.6185] |
| kumamoto-2016 | 100 | 4 | 0.6549 [0.3229, 0.8854] | 0.6745 [0.2630, 0.9635] | 0.6589 [0.3724, 0.9141] |
| red-sea-2023 | 120 | 3 | 0.6823 [0.3675, 0.9615] | 0.3604 [0.0000, 0.6254] | 0.6296 [0.2607, 0.9487] |
| russia-2022 | 123 | 7 | 0.3941 [0.1872, 0.6232] | 0.4791 [0.2715, 0.6687] | 0.5333 [0.3048, 0.7506] |
| shanghai-2022 | 123 | 14 | 0.4951 [0.3172, 0.6733] | 0.5043 [0.3113, 0.7025] | 0.7041 [0.5718, 0.8231] |
| suez-2021 | 126 | 3 | 0.4268 [0.0894, 0.7073] | 0.8726 [0.7588, 1.0000] | 0.8808 [0.8103, 0.9417] |
| zhengzhou-2022 | 127 | 6 | 0.5152 [0.3017, 0.7294] | 0.4008 [0.1997, 0.6047] | 0.5510 [0.2707, 0.8278] |

Within-event intervals resample companies separately among hits and non-hits, with the same 10,000 draws for all three models. This conditions on observed class counts. With only one event, an event-cluster bootstrap would produce a meaningless zero-width interval. These intervals do not refit models or account for correlated company returns, cohort uncertainty or analyst choices; three-hit events have especially limited information.

Pooled AUCs and 95% event-bootstrap intervals:

- LightGBM: 0.4353 [0.3819, 0.5265].
- Logistic regression: 0.5306 [0.4552, 0.6246].
- Distance: 0.6390 [0.5381, 0.7479].

## Distance-baseline leak check

- No direct held-out-label leakage detected: evaluation has one row per company/event and one valid supplier per ticker/event.
- Sites share company labels only in display projections; these repeated site rows do not enter metrics or training. Site-weighted AUC is a diagnostic of the distortion that would occur if they did.
- All saved evaluated distances reconstruct from disclosed manufacturing locations and independently sourced event anchors, without hit labels or a fitted hit-cluster center. Headquarters are excluded.
- Saved distance probabilities reproduce using other events' labeled companies only: median known training distance and training prevalence. No held-out labels select the scale or calibration.
- The same issuer appears in other events during training. Leave-one-event-out tests a new event, not a new company; company dependence and within-event market correlation remain.
- Minimum distance favors firms with more disclosed sites; varying disclosure coverage and coarse centroids may confound it. Straight-line distance to Suez or the Red Sea is not observed route exposure.
- Public shock anchors and retrospective supplier cohorts were analyst-defined, not prospectively preregistered. Code/data checks cannot prove that no analyst selection was influenced by later knowledge.
- The approved removal of single-class events conditions pooled metrics on observed outcomes. Few hits, current-universe survivorship, and repeated companies limit inference.
- baselineAuc is logistic regression; distanceAuc is the separate distance rule. The report names them separately.

Duplicate company/event rows: 0; duplicate ticker/event labels: 0. Maximum distance-rule replay error: 9.93e-17; maximum reconstructed distance error: 1.82e-12 km.

Company labels do repeat on the map, but training and evaluation contain one row per company/event. For example, Suez's correct company-level distance AUC is 0.8808; incorrectly weighting those companies by their display sites would give 0.7583. This diagnostic demonstrates the distortion that duplicate-site evaluation would cause; it is not the method used.

## Why pooled model AUC is below 0.5

The seven-event pooled score is 0.4353; its event-bootstrap interval includes 0.5. The result does not establish that the model reliably predicts the opposite outcome. Few positives increase uncertainty but do not mathematically force AUC below 0.5. Site-shared labels cannot explain the result because they are deduplicated before fitting and scoring.

A concrete source of the low pooled score is ranking across different held-out event folds. 85.8% of all hit/non-hit pairs come from different events; their AUC is 0.4211. Pairs within the same event have a pair-weighted AUC of 0.5211. Pooling compares probabilities from separately fitted models facing events with different hit rates and predicted levels; it is not the mean of per-event AUCs. This decomposition exactly reconstructs the pooled score.

| Event | Observed hit rate | Mean held-out probability |
|---|---:|---:|
| covid-china-2020 | 0.0645 | 0.0421 |
| kumamoto-2016 | 0.0400 | 0.0488 |
| red-sea-2023 | 0.0250 | 0.0496 |
| russia-2022 | 0.0569 | 0.0446 |
| shanghai-2022 | 0.1138 | 0.0388 |
| suez-2021 | 0.0238 | 0.0478 |
| zhengzhou-2022 | 0.0472 | 0.0601 |

The table shows the between-event prevalence/calibration shift. It is an observed explanation of cross-event ranking, not proof of a unique causal mechanism. The features describe public geographic and company attributes, while the labels are broad stock-market abnormal returns rather than measured operational disruption.

The saved-ensemble training replay provides an overfitting diagnostic:

| Held-out event | Apparent training AUC | Held-out AUC | Boosting rounds |
|---|---:|---:|---:|
| covid-china-2020 | 0.8564 | 0.6008 | 1 |
| japan-2011 | 0.8224 | excluded: single class | 1 |
| kumamoto-2016 | 0.8584 | 0.6549 | 5 |
| red-sea-2023 | 0.8391 | 0.6823 | 1 |
| russia-2022 | 0.8834 | 0.3941 | 1 |
| shanghai-2022 | 0.8433 | 0.4951 | 4 |
| suez-2021 | 0.8466 | 0.4268 | 1 |
| thailand-2011 | 0.8325 | excluded: single class | 1 |
| zhengzhou-2022 | 0.9790 | 0.5152 | 400 |

Apparent AUC of the actual saved ensemble on its full outer-training pool. Some members omit events, but the ensemble as a whole was fitted to this pool; this is not independent validation.

A gap between apparent training and held-out performance is consistent with overfitting and event-distribution shift; these observations cannot separate their causal contributions. Shallow trees and early stopping do not guarantee transfer to a new event. The evidence does not justify reversing probabilities or tuning to the outer test results.

The two zero-hit 2011 events remain excluded from every metric under the recorded user decision; their company predictions and observations remain exported. The evaluation has 843 company/event observations and 45 hits across seven events. Identity merging combined 201 supplied name variants (52 additional merges beyond earlier normalization); it did not remove duplicate same-event stock labels because none existed. See company_merge_comparison.md for that separate before/after comparison.

The next step fixes a nested training-only choice among distance, logistic regression and LightGBM before running that new procedure. Existing outer scores have already been observed; they cannot be called prospectively unseen. The new selection rule must be frozen and mechanically exclude each outer event from all inner choices. No adjustment will be made based on its new outer results.

Full intervals, replay checks, pair counts, model hashes and diagnostics are in evaluation_report.json. The original per-event audit remains in auc_audit.md and the canonical-merge audit in auc_after_merge.md.
