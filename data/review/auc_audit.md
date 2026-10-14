# Company-level AUC and distance leakage audit

Saved model, features, labels, and predictions were not changed.

| Event | Companies | Hits | Model AUC | Distance AUC | Logistic AUC |
|---|---:|---:|---:|---:|---:|
| covid-china-2020 | 121 | 8 | 0.6781 | 0.4397 | 0.6361 |
| kumamoto-2016 | 86 | 3 | 0.7992 | 0.6406 | 0.8554 |
| red-sea-2023 | 119 | 3 | 0.7830 | 0.6293 | 0.3779 |
| russia-2022 | 122 | 7 | 0.3957 | 0.5335 | 0.5130 |
| shanghai-2022 | 122 | 14 | 0.5179 | 0.7047 | 0.6303 |
| suez-2021 | 124 | 3 | 0.4160 | 0.8871 | 0.8678 |
| zhengzhou-2022 | 126 | 6 | 0.5535 | 0.5521 | 0.4000 |

Pooled AUC: model 0.4508; distance 0.6287; logistic 0.5823.

`baselineAuc` means logistic regression; `distanceAuc` is the separate distance rule. Both 2011 events remain excluded from metrics under the user's decision.

- No direct held-out-label leakage detected: evaluation has one row per company/event and one valid supplier per ticker/event.
- Sites share company labels only in display projections; these repeated site rows do not enter metrics or training. Site-weighted AUC is a diagnostic of the distortion that would occur if they did.
- All saved evaluated distances reconstruct from disclosed manufacturing locations and independently sourced event anchors, without hit labels or a fitted hit-cluster center. Headquarters are excluded.
- Saved distance probabilities reproduce using other events' labeled companies only: median known training distance and training prevalence. No held-out labels select the scale or calibration.
- The same issuer appears in other events during training. Leave-one-event-out tests a new event, not a new company; company dependence and within-event market correlation remain.
- Minimum distance favors firms with more disclosed sites; varying disclosure coverage and coarse centroids may confound it. Straight-line distance to Suez or the Red Sea is not observed route exposure.
- Public shock anchors and retrospective supplier cohorts were analyst-defined, not prospectively preregistered. Code/data checks cannot prove that no analyst selection was influenced by later knowledge.
- The approved removal of single-class events conditions pooled metrics on observed outcomes. Few hits, current-universe survivorship, and repeated companies limit inference.
- ReplaySection.tsx currently labels baselineAuc as distance alone, but baselineAuc is logistic regression. This is a display-label error, not leakage in the saved distance predictions. Web code was not changed.

Distance replay maximum absolute probability error: 9.97e-17. Reconstructed minimum-distance error: 1.82e-12 km.

Audit inputs and their SHA-256 hashes are in `auc_audit.json`. `auc_audit.csv` also records missing distances, site projection multiplicity, and hypothetical site-weighted distance AUCs.

Evidence: `ml/features.py` builds distances before outcomes are joined; `ml/train.py` joins one-to-one company/event labels, excludes the outer event before fitting, and calibrates the distance rule on training data. `data/events.csv` retains the source and location basis for each shock.
