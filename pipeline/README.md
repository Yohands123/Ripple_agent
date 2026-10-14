# Public-data pipeline

Use WSL from the project root. The project environment is `.venv/`; install
dependencies and run the required checks with `bash autopilot/checks/ml.sh`.

## M1: Supplier Lists

```bash
.venv/bin/python -m pipeline.supplier_lists
.venv/bin/python -m pipeline.supplier_lists --offline
```

The source registry is `data/sources/supplier_lists.json`. Raw Apple-authored
PDFs are cached in `data/raw/supplier_lists/` and must not be committed. Mirrors
and the Internet Archive preserve older Apple documents whose original URLs
are no longer available. Each cover is checked against its requested fiscal
year before caching or extracting it.

`data/interim/suppliers_<fiscal_year>.csv` has exactly the columns `supplier`,
`location`, and `country`. Street addresses stay intact. Explicit comma- or
semicolon-separated region lists become separate rows. Country names are
normalized, and duplicate supplier/location/country/role rows are removed.

`supplier_list_manifest.json` records source titles and URLs, PDF/CSV SHA-256
hashes, supplier and row counts, and missing fiscal years. The 2019 publication
covers FY2018. The user approved including verified editions and recording
gaps explicitly; FY2019 and FY2024–25 are not filled from a different year.

`supplier_locations_provenance.csv` maps each CSV row (starting at 1 after the
header) to its source page and location role. The FY2018 and FY2020 documents
explicitly list headquarters for some suppliers without internal Apple-related
manufacturing facilities. These rows must retain the `headquarters` role.

The parser uses printed supplier-cell boundaries rather than filling names
down by text line: FY2020 centers names vertically across several country
rows. It also handles the missing final table border in FY2021. Download and
parse failures are reported in the manifest and produce a nonzero CLI exit.

## M2: Geographic matching

```bash
.venv/bin/python -m pipeline.geocode
.venv/bin/python -m pipeline.geocode --offline
```

Natural Earth 5.1.2 admin-1 polygons, populated-place points, and admin-0
polygons are pinned by SHA-256 in `data/sources/natural_earth.json`. Downloads
stay in `data/raw/natural_earth/`. Province and country coordinates are
area-weighted centroids computed in EPSG:6933 and transformed back to WGS84.
City coordinates are the dataset's populated-place points. These are geographic
approximations, and none are labeled as an exact factory location.

Standalone province names retain province precision even when a city has the
same name. Addresses can resolve to cities, with the stated province used to
disambiguate names. Province matches provide a fallback; country precision is
used only when the source itself specifies just a country. Remaining unknown
or ambiguous names go to `data/review/unmatched.csv` without coordinates.

Outputs are `data/interim/geocoded_<year>.csv` and `geocode_summary.json`.
The CSV keeps every original row, its location role, explicit match status,
and both Apple and geographic sources. Supplier CSV hashes are checked before
matching. The same version of contemporary geography is used for every
snapshot; changing historical administrative boundaries are not reconstructed.

## M3: Supplier attributes from filings

```bash
.venv/bin/python -m pipeline.extract_profiles
.venv/bin/python -m pipeline.extract_profiles --offline
python -m pipeline.download_filings --direct-only
python -m pipeline.sec_filings
```

The rule-based registry is `data/sources/filings.json`. Company-authored annual
reports are downloaded from public archives into `data/raw/filings/`, with
source URLs and SHA-256 hashes. PDFs and extracted full text are not committed.
Direct issuer URLs are in `data/sources/filing_urls.json`. The standard-library
downloaders also run on Windows. EDGAR downloads require `SEC_USER_AGENT`
and run sequentially at no more than five requests per second. They retain
publication and report dates without saving the request-header identity.
Document issuer and year are checked before extracting values. PDFium text
extraction runs sequentially because its native library is not thread-safe.

`data/processed/supplier_profiles.json` includes every supplier/year, sourced
company product categories, and explicitly named Apple revenue percentages.
The latter must identify matching, ordered fiscal years and percentages. An
anonymous large customer, a receivable percentage, a bound, a combined-customer
share, or conflicting evidence leaves the scalar share null. Product categories
describe the company's business; Apple-specific part assignments remain
inferred. Unavailable reports and missing values stay null.

`data/review/hand_check.csv` contains exactly 30 reproducibly sampled links for
the human's I1 review. `filing_download_gaps.json` lists unavailable or
unverifiable reports. No LLM key was available, so extraction uses rules.
The user supplied the SEC request-header identity for direct EDGAR retrieval.
Calendar report dates and the issuer's fiscal-year focus are separate fields;
source titles use the issuer's fiscal-year focus when present. Publication
dates must be checked before using attributes in a historical prediction.

## M4: Listings and prices

```bash
python -m pipeline.sec_filings --exchange-registry  # SEC_USER_AGENT required
python -m pipeline.tpex_index                     # exchange's public reports
.venv/bin/python -m pipeline.prices
.venv/bin/python -m pipeline.prices --offline
```

The listing resolver uses the SEC issuer/exchange registry and Yahoo Finance
equity search. It removes legal suffixes for name matching while preserving
holding-company and subsidiary names. Unsupported OTC results, fuzzy matches,
and related public parents do not establish a supplier listing. Accepted
tickers carry their listing source. Search responses and yfinance's own caches
stay under `data/raw/`. Listings are checked as of the date in
`data/sources/markets.json`; this is not a reconstruction of delisted firms.

`data/processed/ticker_map.json` records mapped, verified unlisted, and unresolved
names separately, with counts. `data/review/unlisted_suppliers.csv` contains only
companies with public evidence of private ownership. Failed searches remain in
`unresolved_tickers.csv`, and must not be interpreted as evidence of being
unlisted. Supplier-name variants can map to the same unique ticker.

Daily unadjusted and adjusted prices from 2010 onward, where available, are in
`data/raw/prices/`. Each exchange uses the explicitly named broad market index
in the source registry. No missing prices are interpolated; IPO dates and gaps
are retained. `price_manifest.json` records the actual coverage, source URLs,
SHA-256 hashes, and any failures. A missing ticker or benchmark download makes
the command fail. Historical analysis must require sufficient pre-event
observations rather than treating a new listing as a long price history.

The provider does not supply usable `^TWOII` history, so the TPEx index comes
directly from the exchange's public monthly reports, which contain daily OHLC
observations from April 2012. Each monthly response is cached. Index closes are
published price-index levels; the shared price reader's adjusted-close column
contains that same observed level, without any synthetic adjustment. Oslo uses
`OSEBX.OL` and Helsinki uses `^OMXH25`; their available histories begin in 2013.
The TPEx downloader keeps TLS chain and hostname verification enabled while
allowing its trusted legacy CA certificate's missing Subject Key Identifier.

## M5: Events and market-model labels

```bash
.venv/bin/python -m pipeline.supplier_lists --offline
.venv/bin/python -m pipeline.geocode --offline
.venv/bin/python -m pipeline.events
python -m pipeline.peer_controls --download-metadata  # SEC_USER_AGENT required
python -m pipeline.industry_history                  # SEC_USER_AGENT required
.venv/bin/python -m pipeline.peer_controls --prices
.venv/bin/python -m pipeline.event_study
```

The 2017 Apple publication explicitly covers procurement in 2016, without
calling that a fiscal year. It adds 769 address rows and 201 distinct printed
supplier names, with 8 headquarters-only rows. The legacy parser retains
address cells on the cover, separated header underlines, and unbordered final
rows, and excludes the final publication notes. This provides Kumamoto's own
coverage-year cohort; no newer supplier population is substituted for it.

`data/sources/events.json` records verified dates, their interpretation, and
geographic sources. Earthquakes use local calendar dates and published USGS
epicenters. City anchors use Natural Earth; the Red Sea anchor is the published
Marine Regions area reference point, rather than an invented ship position.
An onset/announcement observation or a report cutoff is distinguished from
the end of a disruption. `data/events.csv` preserves those distinctions.

The event study uses adjusted equity closes and matching exchange benchmarks.
Day zero is the first exchange session on or after the local event date.
For exact USGS timestamps, NYSE/NASDAQ sessions instead use the event's Eastern
time and the regular 4 p.m. close. Kumamoto occurred during the US April 15
session, despite Japan's local April 16 date. Current exact-timestamp cases
avoid US early-close days. Financial disclosures exclude the earliest event
calendar date, preventing an unknown same-day release time from looking ahead.
Estimation days -250 through -30 contain exactly 221 returns; event days 0
through +10 contain 11. The market model has an OLS intercept and slope.
For L event returns, CAR variance is the fitted residual variance multiplied
by `L + g' (X'X)^-1 g`, where g sums event-window design rows. This includes
uncertainty in the fitted parameters and assumes independent, constant-variance
residuals. A hit means `t < -1.96`. It is a stock-market label, without a causal
claim about disruption damage or a measurement of factory output.

Stock closes are reindexed to the benchmark calendar before returns are
calculated; missing sessions are never filled or treated as a single-day
multiday return. Unavailable histories, incomplete windows, and singular fits
receive explicit statuses and empty outcomes. `labels.csv` has one row for
each normalized supplier identity in each available cohort, including these
unavailable rows, plus comparison companies. `label_summary.json` reports
coverage and missing event-year snapshots. A missing own-year cohort makes
the event-study command return nonzero, even when other events were computed.
FY2024 remains unavailable. Under the user's verified-editions-and-explicit-gaps
instruction, the six events with own-year snapshots are included; Taiwan 2024
is retained in the source registry and `data/review/event_gaps.json`. This meets
M5's six-to-eight-event range. Substituting FY2023 for it requires a further
explicit decision; the current pipeline never makes that substitution.

Pre-event SEC annual filings provide SIC and exchange evidence for comparison
companies. Public filing prefixes stay in `data/raw/industry_headers/` and are
not complete filing archives. A match requires the same verified pre-event
exchange and four-digit SIC. The first three alphabetical eligible candidates
are selected without using event returns. Historical issuer aliases prevent a
renamed supplier from becoming its own comparison company. Not-listed controls
have no observed link in that event-year top Supplier List; absence does not
prove the absence of all Apple relationships. The current candidate universe
also introduces a survivorship limitation. Unverified matches remain in the
review fields of `peer_matches.json`.

The contemporaneous cover's exchange overrides the current listing when it
can be verified. Other supplier rows explicitly mark historical exchange
verification as unavailable. Known II-VI/Coherent ticker and exchange changes
are documented in `listing_history.json`; legacy Coherent Inc. is not assigned
its acquirer's historical stock series. Supplier membership comes from each
event's own-year list, which was published retrospectively, so the cohorts are
not described as information that was available in real time.

## Export and validation (M7)

Run `.venv/bin/python pipeline/export.py`, then
`.venv/bin/python pipeline/validate.py contracts/fixtures` and
`.venv/bin/python pipeline/validate.py web/public/data/real`.
The exporter uses processed inputs without downloads, validates a complete
candidate before writing app files, and emits deterministic compact JSON.
Only this exporter writes `web/public/data/real/`.

The user approved the extensions recorded in
`data/review/export_contract_proposal.md`: per-event `networkPath`, unknown
tiers and operational quantities represented by null, sourced event anchors,
and explanatory scope/provenance. Human-owned contracts remain untouched.
The validator includes these extensions by default; `--frozen` can audit
against the original contract. Fixtures still pass. A sample forecast may
have an empty citation URL; real nodes, edges, and forecasts require sources.

Each exported event has its own dated network. The default `network.json`
is Suez 2021. Geocoded supplier locations are shown with their declared
precision and location role; unmatched locations remain in the review CSV.
Product categories describe the company rather than an Apple-specific part.
Unknown production tiers are null. The current evidence establishes no
physical transport links, so route arrays are empty. Predictions and CAR
observations describe company stock responses and are shared across that
company's disclosed locations. Production loss, quota, and revenue loss stay
unknown; neither zero values nor invented internal operations are exported.
The app consumer must load the scenario's network and handle these nulls.

`pipeline/export.py --review` writes an ignored local review copy in
`data/review/export_preview/` instead of the app folder.

M10 adds the user-approved Japan/Thailand 2011 and Russia 2022 scenarios for
nine exports. The January 2012 names-only Apple Suppliers 2011 roster is the
approved approximation for 2011; those networks have no factory nodes and use
scenario `companyPredictions` instead. FY2019/FY2024 gaps remain explicit.
The user chose to exclude the two single-class 2011 events from all reported
metrics. Seven metric events and nine prediction events are separately
counted; `excludedFromMetrics` records the reasons without nullable AUCs.
See `data/review/m10_integration_notes.md` for the consumer handoff.
