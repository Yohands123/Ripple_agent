# Minimal tier 7 layer

Nine `kind: "repair"` nodes represent four publicly documented operations
and five example Apple Trade In collection points. All nine have inferred
status, tier 7, low confidence, public sources and approximate city positions.
The tier is a display convention, not Apple's published production taxonomy.

The [2026 Apple Environmental Progress Report](https://www.apple.com/environment/pdf/Apple_Environmental_Progress_Report_2026.pdf)
documents the Austin Material Recovery Lab/Daisy and Santa Clara Valley
Advanced Recovery Center/Cora. A Santa Clara city reference represents the
reported valley; the facility address remains undisclosed. The
[Brabant Development Agency](https://www.bom.nl/upload/pdf/whitepaper_Robotics_in_Brabant.pdf)
documents Daisy's partner-operated Breda location. The
[City of Elk Grove's 2023 proclamation](https://elkgrove.gov/sites/default/files/city-files/City%20Government/City%20Clerk/City%20Council%202023/Attachments/02-08-23_4-1.pdf)
documents refurbishment at Apple's local campus. The dated disclosure does
not establish its current throughput or which trade-in devices it handles.

[Apple Trade In](https://www.apple.com/shop/trade-in) is represented through
actual public collection stores: Union Square, Regent Street, Pudong, Ginza
and Orchard Road, with local Apple store and program sources. These are
examples for the five sales regions, not regional processing factories or
the complete service footprint. City coordinates come from pinned Natural
Earth, US Census or Dutch PDOK references; precise facility locations are
not invented.

Twenty-one inferred physical edges use `relation: "route"` and
`purpose: "return"`. Five connect regional markers to the collection points;
eleven illustrate collection-to-recycling/refurbishment movement; five connect
recyclers to same-metal tier-2 refinery references. Nearest approximate
positions select minimal representative recycling/refining links; they do not
identify actual buyers. Apple's
[Daisy material-recovery disclosure](https://www.apple.com/newsroom/2019/04/apple-expands-global-recycling-programs/)
supports cobalt and tin recovery, while its 2026 report supports tungsten
recovery at Cora. No metal flow is assigned to the refurbishment campus.

All routes have low confidence, sources, a basis, `routingVerified: false`
and `modelEligible: false`. Road/air choices are illustrative; actual carriers,
modes, intermediate treatments, cross-border permissions, recycler acceptance
and recovered volumes are unknown. A compatibility edge does not imply that
international waste shipment is authorized. These links and reference nodes
do not enter historical company identities, labels, features, predictions,
evaluation or the optimizer.

Build with `python -m pipeline.returns --offline` using the pinned source
cache, then publish only through `python -m pipeline.export`. Source pins,
curated operations and regional collection evidence are recorded in
`data/sources/returns.json`.
