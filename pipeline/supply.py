"""Conservative product compatibility edges, separate from physical transport.

A component type and a public assembly-product observation justify a possible
link only. Nearest-site selection is a declared inference, never a claim that
Apple or the supplier uses that plant. Unknown/unverified categories stay out.
"""

from collections import defaultdict
import re

from pipeline.sea_routes import distance_km

PATTERNS = {
    "semiconductor": r"semiconduct|processors?|microcontrollers?|secure elements?",
    "memory": r"\bmemory\b|storage devices",
    "sensor": r"sensors?|sensing",
    "display": r"displays?|touch panels?",
    "connector": r"connectors?|interconnects?",
    "optical": r"\boptical\b|camera (?:lenses|modules)",
    "acoustic": r"acoustic|audio",
    "pcb": r"printed (?:circuit|circuits)|\bIC substrates\b|flexible printed",
    "battery": r"batter(?:y|ies)",
    "antenna": r"antennas?",
    "cable": r"cables?",
    "fastener": r"fasteners?",
    "enclosure": r"enclosures?",
    "switch": r"switches",
    "haptic": r"haptics?",
    "backlight": r"backlights?",
    "keyboard": r"keyboards?",
    "hinge": r"hinges?",
    "thermal": r"thermal components|\bfans\b",
}


def categories(part_type):
    if not part_type or "unverified" in part_type.casefold():
        return set()
    return {category for category, pattern in PATTERNS.items() if re.search(pattern, part_type, re.I)}


def compatibility(part_type, assembly, rules):
    matches = []
    for product in assembly.get("products", []):
        evidence = rules["products"].get(product)
        if evidence:
            common = categories(part_type) & set(evidence["categories"])
            if common:
                matches.append({"product": product, "categories": sorted(common), **evidence})
    return matches


def build_supply_edges(sites, assemblies, event_date, rules):
    grouped = defaultdict(list)
    for site in sites:
        if site.get("locationRole") == "manufacturing" and site.get("tier") == 3 and categories(site.get("partType")):
            grouped[site["companyId"]].append(site)
    output = []
    for company_id, locations in sorted(grouped.items()):
        candidates = []
        for assembly in assemblies:
            eligible = [(site, compatibility(site["partType"], assembly, rules)) for site in locations]
            eligible = [(site, products) for site, products in eligible if products]
            if not eligible:
                continue
            site, products = min(eligible, key=lambda pair: (distance_km((pair[0]["lon"], pair[0]["lat"]), (assembly["lon"], assembly["lat"])), pair[0]["id"]))
            distance = distance_km((site["lon"], site["lat"]), (assembly["lon"], assembly["lat"]))
            candidates.append((distance, assembly["id"], site, assembly, products))
        for distance, _, site, assembly, products in sorted(candidates, key=lambda row: (row[0], row[1]))[:3]:
            product = min(products, key=lambda p: (p["availableOn"], p["product"]))
            supplier_evidence = site.get("attributeSources", {}).get("partType", {})
            dated_category = site.get("partTypeStatus") == "sourced" and bool(supplier_evidence.get("filedOn"))
            dates = [assembly["productEvidence"]["availableOn"], product["availableOn"]]
            if dated_category:
                dates.append(supplier_evidence["filedOn"])
            available = max(dates)
            sources = site["sources"] + assembly["sources"] + [product["source"]]
            sources = list({(s["title"], s["url"]): {"title": s["title"], "url": s["url"]} for s in sources}.values())
            output.append({"id": "supply-" + company_id + "-" + assembly["id"], "from": site["id"], "to": assembly["id"],
                           "relation": "supply", "mode": None, "carriesTier": 3, "status": "inferred", "confidence": "low",
                           "confidenceKind": "Qualitative compatibility inference, not a calibrated probability",
                           "layer": "supply", "companyId": company_id, "partType": site["partType"],
                           "products": [p["product"] for p in products], "componentCategories": sorted({c for p in products for c in p["categories"]}),
                           "sources": sources, "productUseEvidence": [product], "assemblyProductEvidence": assembly["productEvidence"],
                           "availableOn": available, "supplierCategoryInferred": not dated_category,
                           "modelEligible": dated_category and available <= event_date,
                           "distanceKm": round(distance, 3), "distanceDefinition": "Minimum reference distance among the company's compatible manufacturing sites; not shipment length",
                           "basis": "Possible supplier-to-assembly relationship: the part category occurs in a sourced product family assembled at this regional hub. Select at most three nearest qualifying hubs per canonical company and one nearest representative site per hub. No purchase order, actual plant allocation or transport mode is observed.",
                           "routingVerified": False})
    # Tier 2 links need named public buyer evidence. No geographic or broad
    # product-family fallback invents a material supplier's customer.
    if rules.get("supportedTier2Links"):
        raise ValueError("Tier-2 evidence entries require an explicit implementation and buyer/metal check; never silently infer them")
    return output
