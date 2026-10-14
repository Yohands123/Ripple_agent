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
