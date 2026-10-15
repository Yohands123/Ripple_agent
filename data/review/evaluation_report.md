# Company-level AUC and distance leakage audit

This audit reads saved model results and does not change features, labels, or predictions.

| Event | Companies | Hits | Model AUC | Distance AUC | Logistic AUC |
|---|---:|---:|---:|---:|---:|
| covid-china-2020 | 124 | 8 | 0.6008 | 0.4445 | 0.5259 |
| kumamoto-2016 | 100 | 4 | 0.6549 | 0.6589 | 0.6745 |
| red-sea-2023 | 120 | 3 | 0.6823 | 0.6296 | 0.3604 |
| russia-2022 | 123 | 7 | 0.3941 | 0.5333 | 0.4791 |
| shanghai-2022 | 123 | 14 | 0.4951 | 0.7041 | 0.5043 |
| suez-2021 | 126 | 3 | 0.4268 | 0.8808 | 0.8726 |
| zhengzhou-2022 | 127 | 6 | 0.5152 | 0.5510 | 0.4008 |

Pooled AUC: model 0.4353; distance 0.6390; logistic 0.5306.

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

Distance replay maximum absolute probability error: 9.93e-17. Reconstructed minimum-distance error: 1.82e-12 km.

Audit inputs and their SHA-256 hashes are in `evaluation_report.json`. `evaluation_report.csv` also records missing distances, site projection multiplicity, and hypothetical site-weighted distance AUCs.

Evidence: `ml/features.py` builds distances before outcomes are joined; `ml/train.py` joins one-to-one company/event labels, excludes the outer event before fitting, and calibrates the distance rule on training data. `data/events.csv` retains the source and location basis for each shock.

## Rerun and company-identity comparison

Labels were rerun from cached prices using the merged identities and are unchanged from the previous merged run. The model and logistic regression were refit after replacing disclosure-graph hops with supply-edge hops. Tree hyperparameters, seeds, 200 ensemble members per fold, 2,000 metric bootstrap draws, and the exclusion policy were retained. No settings were tuned to beat the distance baseline.

550 supplied company spellings resolve to 349 current canonical companies: 201 name variants combined, including 52 additional merges beyond prior normalization. Historical identities resolve to 350 (51 fewer), preserving Mitsumi/Minebea before their merger. The original evaluation already had one company/ticker per event: zero same-event duplicates were removed. Alias matching recovered 32 previously unavailable company-event labels; see company_merge_comparison.md for the earlier counts and baselines.

Model AUC at each stage (the distance rule is unchanged by replacing hops):

| Event | Original audit | After canonical merge | After supply hops |
|---|---:|---:|---:|
| covid-china-2020 | 0.6781 | 0.6514 | 0.6008 |
| kumamoto-2016 | 0.7992 | 0.6875 | 0.6549 |
| red-sea-2023 | 0.7830 | 0.7821 | 0.6823 |
| russia-2022 | 0.3957 | 0.3898 | 0.3941 |
| shanghai-2022 | 0.5179 | 0.5095 | 0.4951 |
| suez-2021 | 0.4160 | 0.4268 | 0.4268 |
| zhengzhou-2022 | 0.5535 | 0.5448 | 0.5152 |

## Supply topology and limitations

Minimum undirected supply-edge count from geographically exposed disclosed manufacturing sites or the explicitly shocked assembly hub. Seeds have zero hops; unreachable companies remain null. Only dated product-compatible tier-3 to assembly links enter; physical transport/access/customer-disclosure edges never enter. Evidence dated after the event is filtered before nearest-hub selection.

CSV canonicalCompany groups identities. Unsourced current part categories are excluded from predictive features and supply hops. Supply hops use the exported tier policy (including empty CSV tiers left null), dated filing categories, and assembly/product evidence available by the event. Contemporary city/province reference positions and retrospective classifications limit historical reconstruction.

| Event | Dated inferred supply links | Geographic/assembly seeds | Companies with known hops |
|---|---:|---:|---:|
| kumamoto-2016 | 17 | 0 | 0 |
| covid-china-2020 | 46 | 253 | 162 |
| suez-2021 | 58 | 0 | 0 |
| shanghai-2022 | 56 | 33 | 51 |
| zhengzhou-2022 | 84 | 1 | 28 |
| red-sea-2023 | 81 | 0 | 0 |
| japan-2011 | 0 | 0 | 0 |
| thailand-2011 | 0 | 0 | 0 |
| russia-2022 | 56 | 0 | 0 |

The supply links are compatibility inferences, not verified purchase orders. Undirected traversal allows possible upstream or downstream association; it does not estimate causal propagation. No geographic access road, airline, sea lane or shared Apple customer node creates a model hop. Public supplier rosters are retrospective, city/province locations are coarse, and the evidence cutoff cannot remove all analyst or survivorship bias.

In plain words: the model is not established as a reliable predictor of production disruption. Each evaluated event has only a few company stock-response hits. A strong AUC on one event can rest on very few positives, and pooled ranking can differ from individual-event ranking. These are stock-market proxy outcomes, not factory damage, shipment delays, or Apple revenue loss.
