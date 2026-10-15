# Company-level AUC and distance leakage audit

This audit reads saved model results and does not change features, labels, or predictions.

| Event | Companies | Hits | Model AUC | Distance AUC | Logistic AUC |
|---|---:|---:|---:|---:|---:|
| covid-china-2020 | 124 | 8 | 0.4445 | 0.4445 | 0.5269 |
| kumamoto-2016 | 100 | 4 | 0.6589 | 0.6589 | 0.6667 |
| red-sea-2023 | 120 | 3 | 0.6296 | 0.6296 | 0.3604 |
| russia-2022 | 123 | 7 | 0.5333 | 0.5333 | 0.4778 |
| shanghai-2022 | 123 | 14 | 0.7041 | 0.7041 | 0.5056 |
| suez-2021 | 126 | 3 | 0.8808 | 0.8808 | 0.8726 |
| zhengzhou-2022 | 127 | 6 | 0.5510 | 0.5510 | 0.3994 |

Pooled AUC: model 0.6392; distance 0.6392; logistic 0.5276.

`baselineAuc` means logistic regression; `distanceAuc` is the separate distance rule. Both 2011 events remain excluded from metrics under the user's decision.

- No direct held-out-label leakage detected: evaluation has one row per company/event and one valid supplier per ticker/event.
- Sites share company labels only in display projections; these repeated site rows do not enter metrics or training. Site-weighted AUC is a diagnostic of the distortion that would occur if they did.
- All saved evaluated distances reconstruct from disclosed manufacturing locations and independently sourced event anchors, without hit labels or a fitted hit-cluster center. Headquarters are excluded.
- Saved distance probabilities reproduce using other events' labeled companies only: median known training distance and training prevalence. No held-out labels select the scale or calibration.
- The same issuer appears in other events during training. Leave-one-event-out tests a new event, not a new company; company dependence and within-event market correlation remain.
- Minimum distance favors firms with more disclosed sites; varying disclosure coverage and coarse centroids may confound it. Straight-line distance to Suez or the Red Sea is not observed route exposure.
- Public shock anchors and retrospective supplier cohorts were analyst-defined, not prospectively preregistered. Code/data checks cannot prove that no analyst selection was influenced by later knowledge.
- The approved removal of single-class events conditions pooled metrics on observed outcomes. Few hits, current-universe survivorship, and repeated companies limit inference.
- baselineAuc is logistic regression; distanceAuc is the separate distance rule. The report names them separately.

Distance replay maximum absolute probability error: 9.89e-17. Reconstructed minimum-distance error: 1.82e-12 km.

Audit inputs and their SHA-256 hashes are in `auc_after_selection.json`. `auc_after_selection.csv` also records missing distances, site projection multiplicity, and hypothetical site-weighted distance AUCs.

Evidence: `ml/features.py` builds distances before outcomes are joined; `ml/train.py` joins one-to-one company/event labels, excludes the outer event before fitting, and calibrates the distance rule on training data. `data/events.csv` retains the source and location basis for each shock.
