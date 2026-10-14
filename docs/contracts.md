# Data contract

The pipeline writes these files to `web/public/data/`. The interface reads
only these files. Sample versions live in `contracts/fixtures/`.
Only the human edits this contract.

## `network.json`: the supply chain for one Supplier List year

```json
{
  "snapshotYear": 2022,
  "sampleData": false,
  "nodes": [
    {
      "id": "foxconn-zhengzhou",
      "name": "Foxconn Zhengzhou",
      "kind": "assembly",
      "tier": 4,
      "lon": 113.6,
      "lat": 34.7,
      "precision": "city",
      "region": "Henan, China",
      "ticker": "2317.TW",
      "partType": "final assembly",
      "appleRevenueShare": null,
      "sources": [{ "title": "Apple Supplier List FY2022", "url": "https://..." }]
    }
  ],
  "edges": [
    {
      "id": "e-0001",
      "from": "tsmc-hsinchu",
      "to": "foxconn-zhengzhou",
      "mode": "air",
      "carriesTier": 3,
      "status": "inferred",
      "sources": []
    }
  ]
}
```

- `kind`: `mine`, `refinery`, `supplier_major`, `supplier_minor`, `assembly`,
  `port`, `airport`, `canal`, `border`, `apple_store`, `carrier`, `retailer`,
  `repair`, `hq`
- `tier`: 1 to 7, matching the tier colors in `design-spec.md`
- `precision`: `exact`, `city`, `province`, `country`
- `mode`: `sea`, `air`, `road`, `rail`
- `status`: `known` or `inferred`
- `via` (optional): waypoints as `[[lon, lat], ...]` between `from` and `to`,
  so sea routes follow real lanes instead of straight lines. Air routes omit it
  and are drawn as arcs.
- `ticker` and `appleRevenueShare` may be `null`

## `scenarios/<id>.json`: one past or hypothetical disruption

```json
{
  "id": "suez-2021",
  "title": "Suez Canal blocked",
  "type": "sea",
  "start": "2021-03-23",
  "end": "2021-03-29",
  "snapshotYear": 2021,
  "sampleData": false,
  "shock": { "nodeIds": ["suez-canal"], "capacityLoss": 1.0 },
  "headline": "Suez Canal blocked. Asia to Europe sea freight has stopped.",
  "predictions": [
    {
      "nodeId": "example-supplier",
      "pHit": 0.81,
      "ciLow": 0.70,
      "ciHigh": 0.90,
      "lowConfidence": false,
      "shap": [{ "feature": "hops_from_shock", "value": 0.31 }]
    }
  ],
  "actual": [{ "nodeId": "example-supplier", "hit": true, "car": -0.034 }],
  "options": [
    {
      "id": "detour-cape",
      "label": "Detour around Africa",
      "detail": "+10 to 14 days",
      "unitsRecovered": [0, 0],
      "extraCostUsd": [0, 0],
      "daysToEffect": 0,
      "defaultOn": true,
      "assumption": true
    }
  ],
  "quota": {
    "weeks": ["2021-03-22"],
    "target": [0],
    "noAction": [0],
    "withPlan": [0],
    "recoverySentence": "Back on target in weeks 3 to 4"
  },
  "money": {
    "coinUsd": 500000000,
    "revenueAtRisk": [0, 0],
    "delayedShare": 0.6,
    "assumption": true
  },
  "affectedRoutes": { "blocked": ["e-0042"], "detour": ["e-0099"], "expedited": ["e-0007"] }
}
```

- `type`: `sea`, `sky`, `land`, `policy`, `demand`
- `actual` is empty for hypothetical scenarios
- Ranges are always `[low, high]`

## `scenarios/index.json`

```json
[{ "id": "suez-2021", "title": "Suez Canal blocked", "type": "sea", "start": "2021-03-23" }]
```

## `metrics.json`: model results for the backtest panel

```json
{
  "model": "lightgbm",
  "events": 8,
  "rows": 950,
  "loeo": [{ "eventId": "suez-2021", "auc": 0.0, "brier": 0.0, "baselineAuc": 0.0 }],
  "overall": { "auc": [0.0, 0.0], "brier": [0.0, 0.0], "baselineAuc": [0.0, 0.0] },
  "calibration": [{ "binMid": 0.1, "observed": 0.0, "n": 0 }]
}
```

`overall` values are `[low, high]` 95% bootstrap intervals.
