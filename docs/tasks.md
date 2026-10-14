# Task board

Agents update the **Status** of their own tasks only (`todo`, `doing`,
`done`, `blocked`). Questions go under the task. MVP target: October 20, 2026.

## S0. Human: before either agent starts

| ID | Task | Done when | Status |
|---|---|---|---|
| S0 | Commit this kit to `main`, run `scripts/setup-worktrees.sh` | Both worktrees exist on branches `ml` and `web` | todo |

## Codex: data and ML (`pipeline/`, `ml/`, `data/`)

| ID | Task | Depends on | Done when | Status |
|---|---|---|---|---|
| M1 | Download Apple Supplier List PDFs (2019 onward) and parse them to `data/interim/suppliers_<year>.csv` (supplier, location, country) | S0 | One CSV per year, row counts logged, spot-check of 10 rows printed | todo |
| M2 | Place each supplier location at its province or city centroid using Natural Earth admin-1 data | M1 | Every row has lon, lat, precision; unmatched locations listed in a report | todo |
| M3 | LLM extraction of part type and Apple revenue share from filings; write `data/review/hand_check.csv` with 30 random links for the human to verify | M2 | Extraction file plus the 30-row review sheet | todo |
| M4 | Map suppliers to stock tickers; download daily prices with yfinance | M2 | Price files per ticker; list of unlisted suppliers with count | todo |
| M5 | Build the event list (6 to 8 events) and compute abnormal returns with a market model (estimation days −250 to −30, event window 0 to +10), plus matched unlinked peers | M4 | `data/processed/labels.csv` with one row per company per event | todo |
| M6 | Build features; train LightGBM with leave-one-event-out testing; compare with logistic regression and a distance-only rule; bootstrap 95% intervals; SHAP values | M5, M3 | `metrics.json` and per-event predictions written | todo |
| M7 | Export `network.json`, `scenarios/*.json`, and `metrics.json` to `web/public/data/` via `python pipeline/export.py`; write `pipeline/validate.py` that checks them against `docs/contracts.md` | M6 | Validation passes on real exports and on `contracts/fixtures/` | todo |

Note on M7: exporting into `web/public/data/` is the one write Codex makes
outside its folders, and only through `export.py`.

## Claude Code: interface (`web/`)

| ID | Task | Depends on | Done when | Status |
|---|---|---|---|---|
| W1 | Scaffold Next.js + TypeScript in `web/`; load Archivo and Pixelify Sans; put every value from `docs/design-spec.md` into `web/styles/tokens.css`; copy `contracts/fixtures/` to `web/public/data/` | S0 | `npm run build` passes; tokens file covers every spec value | todo |
| W2 | World map from Natural Earth with d3-geo (equirectangular), ocean, land, and highlight colors from the spec | W1 | Screenshot matches the reference map colors and framing | todo |
| W3 | Node symbols, label pills, Apple Park card, and the free-flow side panel (status, quota bar, money key, map key, tier key, button) | W2 | Free-flow screenshot matches `design/reference/free-flow.html` | todo |
| W4 | Routes from `network.json`: sea with ticks, air arcs, money and spend lines; ships and coins travel along them; reduced motion respected | W3 | Ships and coins move; reduced-motion mode shows them fixed | todo |
| W5 | Disruption state from `scenarios/suez-2021.json`: shock zone, blocked ship, queued ships, greyed routes, detour, thicker air arcs, delayed and lost coins | W4 | Screenshot matches `design/reference/suez-blocked.html` | todo |
| W6 | Four-section dashboard panel bound to the scenario file, including the quota chart | W5 | Toggling options changes the with-plan line using the file's data | todo |
| W7 | Backtest replay: timeline scrubber; predicted vs actual markers; model results from `metrics.json` | W6 | Scrubbing the Suez event updates the map and panel | todo |
| W8 | Visual parity pass: screenshots of both states side by side with the references; fix differences; deploy to Vercel | W7 | Side-by-side images saved in `web/parity/`; live URL works | todo |

## Integration: human

| ID | Task | Depends on | Done when | Status |
|---|---|---|---|---|
| I1 | Hand-check the 30 links in `data/review/hand_check.csv` | M3 | Precision recorded in the write-up | todo |
| I2 | Merge `ml` and `web` into `main`; swap fixtures for real exports; confirm the "Sample data" tag disappears | M7, W8 | Live site runs on real data | todo |

## After the deadline

Event study write-up, Chronos forecasting, OR-Tools rerouting, mines and land
routes, revenue layer, user study, model view. Add them here as new tasks
once the MVP is merged.
