"""User-requested inferred display tiers; not observed production relationships."""

import re


def inferred_tier(part_type):
    if part_type is None:
        return {"tier": None, "tierStatus": "unknown", "tierBasis": "part type unavailable"}
    text = part_type.casefold()
    if "electronics manufacturing services" in text or re.search(r"\bassembly\b", text):
        tier = 4
    elif re.search(r"\b(materials?|adhesives?|glass|chemicals?)\b", text):
        tier = 2
    else:
        tier = 3
    return {"tier": tier, "tierStatus": "inferred", "tierBasis": "mapped from part type"}
