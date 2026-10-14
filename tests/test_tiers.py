import pytest

from pipeline.tiers import inferred_tier


@pytest.mark.parametrize("part_type,tier", [
    ("materials and adhesives", 2), ("glass and optical materials", 2), ("chemicals", 2),
    ("memory semiconductors", 3), ("image sensors", 3), ("display panels", 3),
    ("connectors and interconnects", 3), ("optical products", 3), ("acoustic components", 3),
    ("other parts", 3), ("electronics manufacturing services", 4), ("final assembly", 4),
])
def test_user_tier_mapping_preserves_inferred_status_and_material_priority(part_type, tier):
    assert inferred_tier(part_type) == {"tier": tier, "tierStatus": "inferred", "tierBasis": "mapped from part type"}


def test_missing_part_type_retains_unknown_tier():
    assert inferred_tier(None)["tier"] is None
    assert inferred_tier(None)["tierStatus"] == "unknown"
