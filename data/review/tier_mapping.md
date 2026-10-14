# Inferred tiers from sourced part types

The user's requested display mapping is implemented in `pipeline/tiers.py`
and applied only by `pipeline/export.py`. It does not change the model,
features, predictions, or observed company labels.

- Tier 2: materials, adhesives, glass, and chemicals. A mixed category such
  as "glass and optical materials" uses this material tier.
- Tier 3: semiconductors, sensors, displays, memory, connectors, optical,
  acoustic, and other sourced part categories.
- Tier 4: electronics manufacturing services and assembly.

Mapped values have `tierStatus: "inferred"` and
`tierBasis: "mapped from part type"`. A null part type retains a null tier,
unknown status, and an unavailable-part-type basis. Production relationships
and an Apple-specific bill of materials are not asserted by these colors.
Existing filing citations remain on each node. The validator checks that
exported tier/status/basis values agree with the mapping.

`supplier_names.txt` lists source names from all active cohorts, including
legal-name variants. A name alone is not evidence of part type; missing sourced
categories continue to appear as unknown rather than receiving guessed colors.
