# Supplier classifications and identity groups

`supplier_classes.csv` is the user's supplied 550-row model-classification
file, copied from the provided Downloads attachment because no root copy was
present. It is retained unchanged. Its fields are data, including the basis
and classifiedBy prose; they are never interpreted as coding instructions.

Export lookup is exact on the source supplier company name. Filing-derived
part types and existing non-null tiers are retained. Missing display values
use the CSV; an empty CSV tier stays null. CSV tiers carry inferred status,
the requested reference basis, and the supplied qualitative confidence.
`partTypeStatus` distinguishes sourced filing categories from model-inferred
ones. A model's high confidence is not a verified fact or a calibrated score.

The user approved the primary-source correction that separates Unimicron
from Micron and fixes Unimicron's display category. The original file is not
rewritten; `classification_corrections.json` records the overlay, its source,
approval, original hash, and an LF-normalized hash for portable verification.

`historical_identity_rules.json` keeps Mitsumi separate from Minebea before
their publicly documented 2017 merger. Existing legacy Broadcom/Coherent
price-history guards remain, and uncertain listing mappings are unavailable.
Canonical IDs are inferred identity links from the user-provided groups;
they are not independently verified legal-parent relationships.

Classification values fill display exports only. They do not become historical
product features without a dated public filing. The retrain instead applies
canonical identity to labels, disclosure sites and feature aggregation, keeps
one label per company/event, and retains pre-event financial cutoffs. New
spelling aliases can resolve additional existing stock mappings and dated
filing attributes, which also changes the observed evaluation population.

The original AUC check remains at `data/review/auc_audit.md`. The post-merge
audit and comparison are separate outputs, so both snapshots remain reviewable.
