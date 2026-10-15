# Sourced backbone audit

Reference dated 2026-10-14: 57 nodes and 104 inferred corridors; 30 sea paths.

Land-crossing failures: 0. Both polylines and smoothed ship paths are checked against pinned Natural Earth physical-land polygons; port tolerance is 3 km and independently sourced canal centerline tolerance is 1 km. Route metadata cannot exempt a crossing.

| Event | Supplier sites / access links | Reference nodes | Blocked exposure | Detour | Expedited |
|---|---:|---:|---:|---:|---:|
| kumamoto-2016 | 734 / 734 | 58 | 1 | 1 | 1 |
| covid-china-2020 | 582 / 582 | 58 | 1 | 1 | 1 |
| suez-2021 | 704 / 704 | 57 | 5 | 5 | 8 |
| shanghai-2022 | 690 / 690 | 57 | 153 | 3 | 2 |
| zhengzhou-2022 | 690 / 690 | 57 | 2 | 4 | 3 |
| red-sea-2023 | 733 / 733 | 57 | 5 | 5 | 8 |
| japan-2011 | 0 / 0 | 58 | 1 | 1 | 1 |
| thailand-2011 | 0 / 0 | 58 | 1 | 1 | 1 |
| russia-2022 | 690 / 690 | 58 | 1 | 0 | 0 |

Every supplier access link selects the nearest of the curated ports/airports by great-circle reference distance and preserves the site's nullable tier. These are inferred access connectors, not verified continuous roads; actual modal transfers and border crossings are unknown.

Both 2011 rosters retain 156 unlocated company predictions each and zero supplier site pins. Backbone context is contemporary and explicitly does not assert historical facility presence (Apple Park, for example, opened in 2017).

Suez and Red Sea overlays identify the five inferred Suez corridors, their five Cape alternatives, and eight illustrative air alternatives. Russia has no proposed detour or expedition around export restrictions. All exposure classifications and alternatives are inferred, and no complete gateway closure is inferred from a regional event.

Features, company/site predictions, CAR labels, evaluation, forecasts and indexed optimizer outputs are byte-identical after line-ending normalization to classification commit `90caca9`. The backbone is not added to the model or optimizer graph.

Pacific corridors split at paired date-line waypoints so no displayed segment crosses Eurasia/Africa. WPI port references are retained in publishedPosition; offshore display approaches are explicitly inferred. Geometry uses pinned physical-land polygons, fine coastal meshes and published Suez/Panama river/lake centerlines. Dataset hashes and tolerances are in data/processed/sea_geometry.json. These are schematic corridors, not navigation data.

Consumer integration notes are in `backbone_integration_notes.md`. Full geometry, source pins, coverage and protected-file hashes are in `backbone_audit.json` and `data/processed/backbone.json`.
