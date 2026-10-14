# Canonical-company retrain versus the original AUC audit

Values below are before → after. Distance and logistic baselines are separately named.

| Event | Companies | Hits | Model AUC | Distance AUC | Logistic AUC |
|---|---:|---:|---:|---:|---:|
| covid-china-2020 | 121 → 124 | 8 → 8 | 0.6781 → 0.6514 | 0.4397 → 0.4445 | 0.6361 → 0.6336 |
| kumamoto-2016 | 86 → 100 | 3 → 4 | 0.7992 → 0.6875 | 0.6406 → 0.6589 | 0.8554 → 0.6693 |
| red-sea-2023 | 119 → 120 | 3 → 3 | 0.7830 → 0.7821 | 0.6293 → 0.6296 | 0.3779 → 0.3718 |
| russia-2022 | 122 → 123 | 7 → 7 | 0.3957 → 0.3898 | 0.5335 → 0.5333 | 0.5130 → 0.4926 |
| shanghai-2022 | 122 → 123 | 14 → 14 | 0.5179 → 0.5095 | 0.7047 → 0.7041 | 0.6303 → 0.6196 |
| suez-2021 | 124 → 126 | 3 → 3 | 0.4160 → 0.4268 | 0.8871 → 0.8808 | 0.8678 → 0.8780 |
| zhengzhou-2022 | 126 → 127 | 6 → 6 | 0.5535 → 0.5448 | 0.5521 → 0.5510 | 0.4000 → 0.3981 |

The supplied 550 names become 349 current canonical groups: 201 spelling/name variants are combined, including 52 additional identities beyond prior normalization.

Historical model identities go from 401 to 350; dated Mitsumi/Minebea separation is retained. Company/event rows remain 1655, so 0 same-event company rows were removed. The original audit already found no repeated ticker/event labels.

All 928 original observed CARs and hit flags are unchanged. 32 previously unresolved company/event labels become observable through explicit aliases. Model classes fill display values only; financial/product features still require dated public reports.

Model pooled AUC: 0.4508 → 0.4471.
Distance pooled AUC: 0.6287 → 0.6390.
Logistic pooled AUC: 0.5823 → 0.5691.

Both 2011 events remain excluded from metrics because they have no supplier hits. Their company predictions and CARs are still exported.

- AUC changes include increased observation coverage and updated dated filing selection through inferred aliases, not just spelling cleanup.
- No old company/event duplicate ticker labels were present; inferred aliases primarily align company identities across years.
- Model-provided display classifications are not used as pre-event model product features.
- The approved Unimicron correction and pre-2017 Mitsumi/Minebea separation prevent false issuer merges.
- No hyperparameters or metric exclusions were tuned using the comparison. Small hit counts and retrospective inferred identities limit conclusions.

The original check is `auc_audit.md`; the new leakage/replay check is `auc_after_merge.md`. Full numeric changes and counts are in the corresponding CSV/JSON artifacts.
