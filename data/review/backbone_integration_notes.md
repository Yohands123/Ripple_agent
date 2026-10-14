# Backbone consumer notes

The user approved the format additions in `backbone_format_proposal.md`.
The export now includes `chokepoint`, `sales_region`, and `event_anchor` kinds,
and nullable edge `carriesTier`. Human-owned contracts and Claude-owned web
code were left untouched.

- Read each scenario's `networkPath`. The default remains Suez, FY2021.
- Nodes with `layer: "supplier"` are the own-year disclosed cohort. Nodes
  with `layer: "backbone"` are separately dated reference geography. Render
  the reference date/scope; do not imply the current India/Vietnam hubs or
  Apple Park existed in the 2011 cohort. Assembly hub positions are city or
  province references, not additional exact supplier factory pins.
- The 2011 networks contain reference nodes but **zero supplier locations**.
  Their 156 `companyPredictions` remain unlocated; never assign those values
  to the reference assembly hubs.
- Region markers represent Apple's five reporting regions, not individual
  stores. Europe includes India, Africa and the Middle East; Rest of Asia
  Pacific excludes India. Representative city positions are display anchors.
- All routes are `inferred`, with public citations and an explicit basis.
  Port/airport tiers stay null when `partType` is null. Supplier access roads
  carry the site's nullable tier. They connect the nearest **curated**
  gateway by great-circle reference distance; they do not establish continuous
  roads, shipment modes, border permissions, cargo volumes or actual routing.
- Sea `via` points use an offshore water grid with finer coastal/strait paths.
  Explicit canal passages and inland port reference connectors are schematic.
  Preserve short dateline crossings when drawing Asia-Americas paths.
- `shock.nodeIds` names reference chokepoints, regional gateways, assembly
  hubs, or sourced event anchors. `affectedRoutes` identifies inferred
  exposure and hypothetical alternatives. Its `affectedRoutesBasis` explains
  that a blocked exposure is not proof of a complete gateway closure or a
  stopped Apple shipment. Russia has no detour around export restrictions.
- Keep these routes separate from the market-response model and the indexed
  planning exercise. The optimizer's reserves do not estimate these edges'
  capacity. Its paired `quota.optionPlans` remain the source of switch results.
- CSV classifications stay model-inferred and retain qualitative confidence;
  financial filing part types remain sourced. Unknown values remain unknown.
- In the backtest, `baselineAuc` means **logistic regression**; `distanceAuc`
  means the distance-only rule. The original audit identified a web label
  mismatch. The post-merge comparison is in `company_merge_comparison.md`.

Coverage, geometric checks, and unchanged model/forecast/planning hashes are
recorded in `backbone_audit.md` and `backbone_audit.json`.
