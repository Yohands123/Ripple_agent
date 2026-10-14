# Incorrect Unimicron/Micron canonical merge

The supplied CSV assigns all three Unimicron source-name variants to
`canonicalCompany: "Micron Technology"` and memory semiconductors. The verified
ticker map identifies Micron as NASDAQ MU and Unimicron as Taiwan 3037.TW.
Every active cohort includes both companies. This is not a spelling variation.
The initial rebuild flags all nine combined labels as ambiguous and does not
select either price series. Retraining on that mixed identity is held back.

Primary sources:

- TWSE issuer profile: https://www.twse.com.tw/pdf/en/3037_en.pdf identifies
  Unimicron Technology Corp. and its PCB/IC-substrate business.
- Micron SEC filing: https://www.sec.gov/Archives/edgar/data/723125/000072312526000015/mu-20260528.htm
  identifies Micron's separate NASDAQ MU listing.

Proposed correction: retain the supplied CSV unchanged, and apply an explicit
approved override in `data/reference/classification_corrections.json` for
Unimicron Corporation, Unimicron Technology Corp., and Unimicron Technology
Corporation. Set their canonical company to "Unimicron Technology" and display
part type to "printed circuit boards and IC substrates". Keep tier 3 inferred.
Record the primary source and approval alongside the override; the original
confidence is preserved as a model-provided value, not a verified probability.
Micron's canonical group and memory category are unchanged. Display corrections
do not introduce a current classification into pre-event model features.

Status: the user approved the sourced correction on 2026-10-14. The original
CSV is retained byte-for-byte; the approved override and primary citation are
in `data/reference/classification_corrections.json`.

This yields 349 current canonical groups for 550 source names: 201 name variants
are combined, including 52 identities beyond existing normalization. A dated
identity rule also retains separate Mitsumi/Minebea issuers before their
January 27, 2017 merger, confirmed by the company at
https://www.minebeamitsumi.com/english/news/press/2017/1192715_8993.html .
Current model-generated group names cannot replace distinct historical stocks.
The historical rule is in `data/reference/historical_identity_rules.json`.
The final before/after counts and AUCs are reported in
`data/review/company_merge_comparison.md` after the rebuild.
