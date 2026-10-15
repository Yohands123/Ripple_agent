# Ripple

**An interactive map of Apple's publicly known supply chain, and of what happens to it when something breaks.**

Ripple takes the suppliers Apple discloses each year, places them on a world map, connects them to factories, ports, sea lanes, and sales regions, and replays real disruptions: the Suez Canal blockage, the Shanghai lockdown, the Kumamoto earthquake, and six more. For each event it shows which suppliers a model expected to be hit, then shows what actually happened to them.

It is built only from public data. It is a resilience case study, not a description of Apple's internal operations, and it does not recommend what Apple should do.

**Demo video:** [watch the walkthrough](VIDEO_LINK_TODO)

![Ripple's default view: Asia-to-Europe sea lane, supplier clusters, air freight, and money flowing back to Apple Park](web/parity/real/free-flow.app.png)

## What you can do

- **Explore the network.** Pan and zoom across every continent. At world zoom, the 704 disclosed supplier sites gather into clusters colored by their production tier. Zoom into a country and the clusters split into individual sites.
- **Trace a factory.** Click the Zhengzhou assembly hub to see its suppliers upstream and its path downstream: the ports and airports it ships through, the sea and air routes, the sales regions, and the money back to Apple Park. The panel summarizes it as a chain ("99 suppliers → this factory → 2 ports and airports → 5 sales regions → Apple Park"), and each step is clickable.
- **Drop a disruption.** Pick a past event and watch it ripple out. Closed routes turn red, then the wave reaches suppliers hop by hop, and each supplier fills with its predicted risk.
- **Replay predicted against actual.** Step through the event day by day. The panel ranks suppliers by predicted risk, marks the ones that were actually hit, and shows how the model scored on that event.

![Tracing the Zhengzhou assembly hub](web/parity/real/trace-zhengzhou.png)

## How to run it

You need Node.js 20 or later.

```bash
cd web
npm ci
npm run build   # also runs the default-view checks
npm start       # http://localhost:3000
```

The interface reads `web/public/data/real/` when it exists and falls back to the sample data in `web/public/data/fixtures/`. To rebuild the real data, see `pipeline/README.md`. The pipeline is Python and runs from the project's `.venv`.

## Data sources

Every node and edge carries its own source title and link. The main sources:

| What | Source |
|---|---|
| Suppliers and their sites, by year | Apple Supplier Lists, matched to each event's own year (2011 uses the company-only January 2012 roster) |
| Site coordinates | Natural Earth 5.1.2 (province centroids and city points); no site is placed at an exact factory |
| Company facts, part types, Apple revenue share | SEC EDGAR filings and company facts, and company annual reports |
| Stock prices for the outcome labels | Yahoo Finance listings, plus exchange index reports |
| Ports, airports, straits, sea lanes | World Port Index, Natural Earth, and public corridor geography |
| Event dates and locations | USGS, WHO, Reuters, and Apple newsroom posts, cited per event |
| Input cost history | World Bank Pink Sheet (copper, aluminium, tin); SCFI Shanghai–Europe container freight |

## Methods

- **Outcome.** A supplier counts as "hit" when its stock had a significantly negative cumulative abnormal return (market model, trading days 0 to +10, t < −1.96). This measures how the market reacted to the company. It does not measure factory damage.
- **Model.** LightGBM, scored leave-one-event-out: every prediction for an event comes from models that never saw that event. Intervals come from bootstrapping over events, and SHAP values explain each prediction.
- **Baselines.** The model is compared with a distance-only rule (the closer a supplier is to the shock, the riskier) and with a logistic regression.
- **Routes.** A dated reference backbone: assembly hubs, gateways, sea lanes through the real straits, air corridors, and Apple's five sales regions. All routes are marked as inferred, and each supplier connects to its nearest gateway. The routes are illustrative and do not enter the model.
- **Tiers.** A supplier's production tier is mapped from its part type and marked as inferred, with a qualitative confidence. Where the part type is unknown, the tier stays unknown and the site is drawn grey.
- **Recovery plan.** An illustrative linear program (OR-Tools) on an indexed weekly quota, run with Monte Carlo draws over assumed ranges. Its units are an index, not devices.
- **Cost forecasts.** Chronos-Bolt (a pretrained time-series model), compared with a seasonal-naive baseline over rolling origins.

## Results, honestly

The model does **not** beat the simple baselines overall. Every prediction for an event comes from models that never saw that event (leave-one-event-out, with early stopping tuned on a different event inside each training fold). Pooled across the seven scored events (843 supplier-event rows), with 95% intervals from 2,000 bootstrap draws over events:

| | AUC (point) | 95% interval |
|---|---:|---|
| LightGBM model | 0.44 | 0.38 to 0.53 |
| Logistic regression | 0.53 | 0.46 to 0.62 |
| Distance only | 0.64 | 0.54 to 0.75 |

An AUC of 0.5 is no better than chance. Distance alone did best overall. By event:

| Event | Companies | Hits | Model | Logistic | Distance |
|---|---:|---:|---:|---:|---:|
| Kumamoto earthquake, 2016 | 100 | 4 | 0.65 | 0.67 | 0.66 |
| COVID containment in China, 2020 | 124 | 8 | 0.60 | 0.53 | 0.44 |
| Suez Canal blocked, 2021 | 126 | 3 | 0.43 | 0.87 | 0.88 |
| Russia technology export restrictions, 2022 | 123 | 7 | 0.39 | 0.48 | 0.53 |
| Shanghai lockdown, 2022 | 123 | 14 | 0.50 | 0.50 | 0.70 |
| Zhengzhou assembly restrictions, 2022 | 127 | 6 | 0.52 | 0.40 | 0.55 |
| Red Sea shipping attacks, 2023 | 120 | 3 | 0.68 | 0.36 | 0.63 |

The model did better than distance alone on two events (COVID and the Red Sea) and worse on five, most clearly Suez (0.43 against 0.88). With 3 to 14 hits per event, each AUC is very uncertain. The 2011 Tohoku and Thailand events are left out of the scores because no supplier in them was hit, so an AUC cannot be computed. The interface says all of this in its replay panel, next to each event. The full evaluation, including a check that the distance baseline does not leak held-out labels, is in [data/review/evaluation_report.md](data/review/evaluation_report.md).

The cost forecasts did better: Chronos-Bolt had a lower error than the seasonal-naive baseline on all four series (MASE 0.77 to 1.54, against 1.59 to 3.39).

## Limitations

- **Stock reactions stand in for disruption.** A share price falling is not a factory stopping, and many suppliers are large conglomerates whose Apple business is a small part.
- **Locations are approximate.** Most sites are placed at a province centre, and Apple's lists do not say what each site makes for Apple.
- **Links are inferred.** Who supplies which factory, and which route goods take, comes from part-type compatibility and geography, not from disclosed shipments. Each link says so and carries a confidence.
- **Few events, few hits.** Seven scored events and 3 to 14 hits each cannot support strong claims. Some years have no verified Supplier List (FY2019, FY2024), so events in those years are left out, not filled in from another year.
- **Survivorship.** The company universe is today's listings, so delisted suppliers are underrepresented.
- **Illustrative planning.** Quotas, recovery options, and costs are assumptions shown as ranges. Apple's real production numbers are not public.
- **Unknowns stay unknown.** Revenue at risk and production losses are not public, and the interface says so instead of inventing them.

## How it was built

Two coding agents built it in parallel under an autopilot. Codex wrote the Python data and ML pipeline, Claude Code wrote the TypeScript interface (Next.js, React, d3-geo), and a human owned the shared data contract (`docs/contracts.md`). The agent setup is described in [docs/agent-setup.md](docs/agent-setup.md).
