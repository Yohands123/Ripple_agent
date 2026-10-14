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
