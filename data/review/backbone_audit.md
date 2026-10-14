# Sourced backbone audit

Reference dated 2026-10-14: 55 nodes and 98 inferred corridors; 24 sea paths.

Unexpected open-water land crossings: 0. Explicit canal passages and connectors from published port references to the water mesh are separately recorded.

| Event | Supplier sites / access links | Reference nodes | Blocked exposure | Detour | Expedited |
|---|---:|---:|---:|---:|---:|
| kumamoto-2016 | 734 / 734 | 56 | 1 | 1 | 1 |
| covid-china-2020 | 582 / 582 | 56 | 1 | 1 | 1 |
| suez-2021 | 704 / 704 | 55 | 5 | 5 | 8 |
| shanghai-2022 | 690 / 690 | 55 | 151 | 2 | 2 |
| zhengzhou-2022 | 690 / 690 | 55 | 2 | 4 | 3 |
| red-sea-2023 | 733 / 733 | 55 | 5 | 5 | 8 |
| japan-2011 | 0 / 0 | 56 | 1 | 1 | 1 |
| thailand-2011 | 0 / 0 | 56 | 1 | 1 | 1 |
| russia-2022 | 690 / 690 | 56 | 2 | 0 | 0 |

Every supplier access link selects the nearest of the curated ports/airports by great-circle reference distance and preserves the site's nullable tier. These are inferred access connectors, not verified continuous roads; actual modal transfers and border crossings are unknown.

Both 2011 rosters retain 156 unlocated company predictions each and zero supplier site pins. Backbone context is contemporary and explicitly does not assert historical facility presence (Apple Park, for example, opened in 2017).

Suez and Red Sea overlays identify the five inferred Suez corridors, their five Cape alternatives, and eight illustrative air alternatives. Russia has no proposed detour or expedition around export restrictions. All exposure classifications and alternatives are inferred, and no complete gateway closure is inferred from a regional event.

Features, company/site predictions, CAR labels, evaluation, forecasts and indexed optimizer outputs are byte-identical after line-ending normalization to classification commit `90caca9`. The backbone is not added to the model or optimizer graph.

Geometry uses a 0.5-degree offshore grid and a 0.05-degree port/strait refinement of pinned Natural Earth polygons. Narrow canal connections are schematic published-reference passages; these paths cannot be used for navigation. Dataset pins and every node/edge's public citations are in the committed catalog and source registry.

Consumer integration notes are in `backbone_integration_notes.md`. Full geometry, source pins, coverage and protected-file hashes are in `backbone_audit.json` and `data/processed/backbone.json`.
