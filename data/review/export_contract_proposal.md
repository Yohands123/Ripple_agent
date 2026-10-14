# M7: approved contract extensions

Status: the user explicitly approved this format on 2026-10-14, answering
"Approve proposed M7 format". The exporter and validator implement this
approval. Human-owned contract files remain untouched; the human and Claude
still own documentation and consumer updates respectively.

## Approved changes

1. Add optional scenario `networkPath`, a relative path such as
   `networks/suez-2021.json`. Each scenario selects its own Supplier List year
   and pre-event financial attributes. Keep `network.json` as the Suez default.
   A single static network cannot represent 2016, 2020, 2021, 2022, and 2023.
   Shanghai and Zhengzhou also need different financial cutoffs within 2022.
2. Allow unknown `network.nodes[].tier`, `scenario.shock.capacityLoss`,
   `scenario.quota`, `scenario.money.revenueAtRisk`, and
   `scenario.money.delayedShare` to be `null`. Unknown is distinct from zero.
   The Supplier List does not disclose production tiers. Available public
   evidence does not quantify Apple production quotas, lost capacity, or
   lost/delayed revenue. Market abnormal returns cannot supply those values.
3. Add optional `scenario.shock.location` with `lon`, `lat`, `precision`,
   `basis`, and `sources`. Precision adds `sea-area` for the Red Sea reference
   point. This shows a sourced event anchor without inventing damaged factory
   IDs. `shock.nodeIds` remains an empty array where damage is not confirmed.
4. Preserve explanatory provenance fields, including `outcomeDefinition`,
   `predictionScope`, `locationRole`, `attributeSources`, and `tierBasis`.
   Probabilities and actual CARs are company outcomes repeated across that
   company's disclosed sites, not independent factory observations. TreeSHAP
   contributions explain mean model log odds, not the median probability.

Example (abridged):

```json
{
  "id": "suez-2021",
  "snapshotYear": 2021,
  "networkPath": "networks/suez-2021.json",
  "shock": {
    "nodeIds": [],
    "capacityLoss": null,
    "location": {
      "lon": 32.549941,
      "lat": 30.004976,
      "precision": "city",
      "basis": "Suez city reference point, not the grounding coordinate",
      "sources": [{
        "title": "Natural Earth 1:10m populated places, v5.1.2",
        "url": "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_populated_places_simple.geojson"
      }]
    }
  },
  "quota": null,
  "money": {
    "coinUsd": 500000000,
    "revenueAtRisk": null,
    "delayedShare": null,
    "assumption": false
  }
}
```

`coinUsd` is the existing visual denomination from the contract; it is not
an estimate of revenue loss. Empty `edges`, `options`, `sensitivity`, and
affected-route arrays are already permitted. No physical routes, transport
modes, alternate capacity, or optimization results have been invented.
Unknown operational quantities remain unavailable until evidence or explicit
assumption ranges are approved. M9 needs such ranges and a definition of demand
units; there is no methods document in the supplied kit.

## Concrete review files

- `data/review/export_preview/network.json`: Suez default network.
- `data/review/export_preview/networks/<eventId>.json`: six dated networks.
- `data/review/export_preview/scenarios/index.json`: six events.
- `data/review/export_preview/scenarios/<eventId>.json`: predictions, company
  market outcomes, event anchors, sources, and explicitly unknown operations.
- `data/review/export_preview/metrics.json`: actual M6 backtest results.

All exports are `sampleData: false`. Headquarters rows retain their disclosed
role and are not presented as manufacturing plants or as Apple's headquarters.
Unmatched coordinates stay in the existing review file rather than receiving
invented coordinates. Financial attributes use filings published before the
event cutoff. Supplier cohorts are retrospective, as documented in M6.

## Required consumer changes

The human owns `docs/contracts.md` and `contracts/`; only the human can edit
those paths. Claude owns the app changes: load the scenario's network, handle
unknown tiers and operational values, use a sourced shock location where
present, and describe the outcome as a company market response. Unknown quota
and money values must not render as zero losses or zero production.

## Reproduce and validate

```sh
.venv/bin/python pipeline/export.py --review
.venv/bin/python pipeline/validate.py contracts/fixtures
.venv/bin/python pipeline/validate.py web/public/data/real
```

Default validation includes the user-approved extensions. `--frozen` checks
the original format and deliberately rejects the new nullable fields and
network references. `pipeline/export.py` validates a complete staged bundle
before writing any real export. `--review` remains available to write a copy
under data/review/ instead of the app folder.
