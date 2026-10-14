"""Exact user-provided classifications and inferred canonical identity groups."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from pipeline.prices import company_key

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "data/reference/supplier_classes.csv"
CLASS_BASIS = "model classification, see data/reference/supplier_classes.csv"


class CompanyRegistry:
    def __init__(self, rows=(), temporal_rules=()):
        self.rows, self.groups = {}, defaultdict(list)
        self.temporal_rules = list(temporal_rules)
        for source in rows:
            row = dict(source)
            name, canonical = row["company"], row["canonicalCompany"]
            if not name or not canonical or name in self.rows:
                raise ValueError("Classification names must be nonempty and unique")
            if row["tier"] not in {"", "2", "3", "4"} or row["confidence"] not in {"high", "medium", "low", "unknown"}:
                raise ValueError("Unexpected classification tier or confidence")
            row["tierValue"] = int(row["tier"]) if row["tier"] else None
            self.rows[name] = row
            self.groups[canonical].append(name)

    def canonical(self, name, event_date=None):
        row = self.rows.get(name)  # Deliberately exact, with no fuzzy or case matching.
        canonical = row["canonicalCompany"] if row else name
        for rule in self.temporal_rules:
            if event_date and event_date < rule["before"] and canonical == rule["canonicalCompany"] and name.casefold().startswith(rule["sourceNamePrefix"].casefold()):
                return rule["historicalCanonicalCompany"]
        return canonical

    def aliases(self, name, event_date=None):
        current = self.canonical(name)
        canonical = self.canonical(name, event_date)
        aliases = self.groups.get(current, [])
        for rule in self.temporal_rules:
            if event_date and event_date < rule["before"] and current == rule["canonicalCompany"]:
                legacy = name.casefold().startswith(rule["sourceNamePrefix"].casefold())
                aliases = [a for a in aliases if a.casefold().startswith(rule["sourceNamePrefix"].casefold()) == legacy]
        return list(dict.fromkeys([name, canonical] + aliases))

    def identifier(self, name, event_date=None):
        return "supplier-" + hashlib.sha256(company_key(self.canonical(name, event_date)).encode()).hexdigest()[:16]

    def classify(self, name, part_type, tier_fields):
        row = self.rows.get(name)
        if row is None:
            return {"partType": part_type, **tier_fields}
        result = {"partType": part_type or row["partType"] or None,
                  "tier": None if row["tierValue"] is None else tier_fields["tier"] if tier_fields["tier"] is not None else row["tierValue"],
                  "tierStatus": "inferred", "tierBasis": CLASS_BASIS, "confidence": row["confidence"],
                  "partTypeStatus": "sourced" if part_type else "inferred" if row["partType"] else "unknown",
                  "classification": {"company": name, "canonicalCompany": row["canonicalCompany"],
                                     "tier": row["tierValue"], "partType": row["partType"] or None,
                                     "confidence": row["confidence"], "status": "inferred",
                                     "basis": row.get("basis", ""), "classifiedBy": row.get("classifiedBy", ""),
                                     "reference": "data/reference/supplier_classes.csv"}}
        if row.get("correction"):
            result["classification"]["correction"] = row["correction"]
        result["confidenceKind"] = "Model-provided qualitative confidence; not a calibrated probability"
        return result


@lru_cache(maxsize=4)
def registry(path=REFERENCE):
    """One immutable reference snapshot per pipeline process."""
    path = Path(path)
    if not path.exists():
        return CompanyRegistry()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    corrections_path = path.with_name("classification_corrections.json")
    if corrections_path.exists():
        corrections = json.loads(corrections_path.read_text(encoding="utf-8"))
        if corrections.get("approved") is not True or hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest() != corrections["normalizedCsvSha256"]:
            raise ValueError("Classification corrections require approval and the unchanged original CSV")
        for correction in corrections["corrections"]:
            for row in rows:
                if row["company"] in correction["companies"]:
                    row.update({k: correction[k] for k in ["canonicalCompany", "partType", "tier"]})
                    row["correction"] = {"basis": correction["basis"], "source": correction["source"], "reference": "data/reference/classification_corrections.json"}
    history_path = path.with_name("historical_identity_rules.json")
    rules = json.loads(history_path.read_text(encoding="utf-8"))["rules"] if history_path.exists() else []
    return CompanyRegistry(rows, rules)


def company_id(name, event_date=None):
    return registry().identifier(name, event_date)


def company_groups(names, event_date=None):
    result = defaultdict(list)
    for name in sorted(set(names)):
        result[company_id(name, event_date)].append(name)
    return dict(result)


def resolve_listing(names, mapping, event_date):
    from pipeline.event_study import listing_for_event
    candidates, rejected = {}, []
    classes = registry()
    for actual_name in names:
        raw = defaultdict(list)
        for alias in classes.aliases(actual_name, event_date):
            for record in mapping.get(company_key(alias), []):
                raw[record["ticker"]].append(record)
        for records in raw.values():
            combined = dict(records[0])
            combined["sources"] = list({(s["title"], s["url"]): s for r in records for s in r.get("sources", [])}.values())
            # Apply historical identity guards to the actual cohort name,
            # even when a CSV spelling alias supplied the mapping.
            dated = listing_for_event(combined, actual_name, event_date)
            if dated.get("ticker"):
                candidates.setdefault(dated["ticker"], []).append(dated)
            elif dated.get("mappingUnavailableReason"):
                rejected.append(dated)
    if len(candidates) == 1:
        records = next(iter(candidates.values()))
        chosen = dict(records[0])
        chosen["sources"] = list({(s["title"], s["url"]): s for r in records for s in r.get("sources", [])}.values())
        return chosen
    if len(candidates) > 1:
        return {"ticker": "", "cik": None, "mappingUnavailableReason": "canonical_listing_ambiguous", "candidateTickers": sorted(candidates)}
    return rejected[0] if rejected else {}


def deduplicate_locations(rows, event_date=None):
    """Collapse repeated disclosure rows while preserving source-name aliases."""
    result = {}
    for source in rows:
        row = dict(source)
        key = (company_id(row["supplier"], event_date), row["location"].casefold(), row["country"], row["locationRole"])
        if key not in result:
            row["supplierAliases"] = [row["supplier"]]
            result[key] = row
        else:
            previous = result[key]
            previous["supplierAliases"] = sorted(set(previous["supplierAliases"] + [row["supplier"]]))
            citations = json.loads(previous["sources"]) + json.loads(row["sources"])
            previous["sources"] = json.dumps(list({(s["title"], s["url"]): s for s in citations}.values()), ensure_ascii=False)
    return list(result.values())
