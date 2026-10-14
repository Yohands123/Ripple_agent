# M10: undefined per-event AUC

Status: resolved on 2026-10-14. The user chose "Exclude single-class events
from metrics". The nullable-AUC proposal was not approved. Human-owned
contracts are unchanged; the validator continues requiring numeric AUCs.

Both Japan 2011 and Thailand 2011 have 54 valid supplier CAR labels, all with
`hit: false` under the specified `t < -1.96` threshold. The Thailand event has
one peer hit, but peer outcomes are not supplier-model evaluation targets.
An ROC AUC requires positive and negative targets; no numeric AUC exists for
these supplier folds. Missing or delisted company outcomes remain unavailable.

The recorded policy is `data/sources/evaluation_policy.json`. Both 2011 events
are excluded from every reported metric: per-event AUC and Brier, pooled scores,
calibration, and metric-bootstrap resampling. `metrics.events` therefore counts
seven evaluated events and `metrics.rows` counts 820 observations. Explicit
`excludedFromMetrics` records retain the two reasons and sample sizes without
inventing scores. The metric population is conditional on both classes being
observed, which limits interpretation of this selected sample.

All nine prediction folds and their training cohorts remain intact. The
2011 held-out predictions, original labels, and company-only scenario exports
remain available. `metrics.predictionEvents` distinguishes the nine prediction
events from the seven metric events. The consumer should explain a missing
event-metric entry rather than assigning zero or 0.5 or implying all nine
events contributed to the reported pooled score.
