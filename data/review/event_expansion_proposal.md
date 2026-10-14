# M10: snapshot and location decision

Status: the user approved the nine-event plan on 2026-10-14:
"Approve nine events; preserve year gaps and use company-only 2011 exports".
The machine-readable decision is `data/sources/event_expansion.json`.

The requested expansion plus Taiwan 2024 would produce twelve events.
Two source limits require an explicit choice under the user's instruction
to ask rather than guess.

## Reviewed candidates (the three nearby-year proxies were declined)

| Event | Proposed supplier evidence | Qualification |
|---|---|---|
| Japan earthquake, 2011 | Apple Suppliers 2011, published January 2012 | M10 authorizes the 2012 publication as a retrospective approximation; names only |
| Thailand industrial floods, 2011 | Same January 2012 roster | Names only; no factory coordinates disclosed |
| Japan–Korea export controls, 2019 | Verified FY2018 list, published 2019 | Explicit nearby-year approximation; FY2019 unavailable |
| Russia export restrictions, 2022 | Verified FY2022 list | Own-year cohort; financial inputs still strictly pre-event |
| Taiwan earthquake, 2024 | Verified FY2023 list, published 2024 | Explicit nearby-year approximation; FY2024 unavailable |
| Helene / Spruce Pine, 2024 | Same verified FY2023 list | Explicit nearby-year approximation |

Keep the existing six events. Snapshot years retain their actual source
meaning; FY2018 and FY2023 must never be relabeled as FY2019 or FY2024.
Each approximation will carry its reason, source year, publication year,
event year, and `assumption: true`. This is a retrospective case study rather
than a reconstruction of contemporaneously available knowledge.

## The 2012 publication contains no factory locations

The verified Apple-authored PDF is available at:
https://web.archive.org/web/20120120000000id_/http://images.apple.com/supplierresponsibility/pdf/Apple_Supplier_List_2011.pdf

It is headed **Apple Suppliers 2011**, dated January 2012, and names 156
production suppliers. It does not disclose their factory addresses or
countries. It therefore supports company membership and company stock-return
labels, but not a historical map of manufacturing sites. Supplier headquarters
or later factory locations cannot fill this gap without another assumption.

Proposed handling: compute company-level predictions and CARs for 2011, leave
unavailable geographic features missing, and export empty physical node arrays
with explicit coverage notes. Add `companyPredictions` to those scenarios for
the unlocated companies, including IDs, sources, intervals, SHAP, and observable
company CARs. Existing node-based arrays remain empty where no coordinates
are disclosed. The map can show the sourced event anchor, while the backtest
panel includes the company outcomes. No unverified factory coordinates are
created. This additional scenario field and empty-location behavior require
matching consumer handling by Claude.

## Alternative preserving the year gaps

Use the same company-only 2011 handling and add Russia 2022, but keep 2019
and both 2024 scenarios excluded with explicit gaps. This yields nine active
events instead of the requested roughly twelve. It follows the prior verified
editions policy without introducing extra nearby-year proxies.

The approved set retains the existing six events, adds both company-only 2011
events and Russia 2022, and leaves Japan–Korea 2019, Taiwan 2024, and Helene
2024 in the source registry and explicit gap report. There are no approved
nearby-year proxies. The user approved `companyPredictions` and empty physical
networks for 2011; consumer handling remains in Claude's ownership.
