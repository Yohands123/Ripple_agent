"""Validate an export folder against Ripple's contract and cross-file references."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

KINDS = {"mine", "refinery", "supplier_major", "supplier_minor", "assembly", "port", "airport", "canal", "border", "apple_store", "carrier", "retailer", "repair", "hq"}
BACKBONE_KINDS = {"chokepoint", "sales_region", "event_anchor"}  # User-approved October 14, 2026.
PRECISIONS = {"exact", "city", "province", "country"}
MODES = {"sea", "air", "road", "rail"}
TYPES = {"sea", "sky", "land", "policy", "demand"}


class Validator:
    def __init__(self, folder: Path, extensions=True):
        self.folder = folder.resolve()
        self.proposed = extensions  # User-approved M7 extensions; --frozen disables them.
        self.errors = []

    def check(self, condition, message):
        if not condition:
            self.errors.append(message)
        return bool(condition)

    def load(self, relative):
        target = (self.folder / relative).resolve()
        if not self.check(target.is_relative_to(self.folder), f"Unsafe export reference: {relative}"):
            return {}
        try:
            return json.loads(target.read_text(encoding="utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Non-JSON number: {value}")))
        except (OSError, ValueError) as exc:
            self.errors.append(f"{relative}: {type(exc).__name__}: {str(exc)[:160]}")
            return {}

    def number(self, value, name, low=None, high=None):
        valid = type(value) in {int, float} and math.isfinite(value)
        return self.check(valid and (low is None or value >= low) and (high is None or value <= high), f"{name}: invalid numeric value {value!r}")

    def text(self, value, name):
        return self.check(isinstance(value, str) and bool(value.strip()), f"{name}: nonempty text required")

    def day(self, value, name):
        try:
            return self.check(isinstance(value, str) and date.fromisoformat(value).isoformat() == value, f"{name}: ISO date required")
        except (ValueError, TypeError):
            return self.check(False, f"{name}: ISO date required")

    def citation(self, value, name, sample=False):
        if not self.check(isinstance(value, dict), f"{name}: source object required"):
            return
        self.text(value.get("title"), name + ".title")
        url = value.get("url", "")
        parsed = urlsplit(url) if isinstance(url, str) else None
        self.check((sample and url == "") or (parsed is not None and parsed.scheme in {"http", "https"} and bool(parsed.netloc)), name + ": absolute public HTTP(S) source URL required")

    def sources(self, value, name, sample):
        if not self.check(isinstance(value, list), f"{name}: sources array required"):
            return
        self.check(sample or bool(value), f"{name}: real nodes/edges require a source")
        for source in value:
            self.citation(source, name, sample)

    def interval(self, value, name, low=None, high=None, nullable=False):
        if value is None and nullable and self.proposed:
            return
        if not self.check(isinstance(value, list) and len(value) == 2, f"{name}: [low, high] required"):
            return
        first = self.number(value[0], name + "[0]", low, high)
        last = self.number(value[1], name + "[1]", low, high)
        if first and last:
            self.check(value[0] <= value[1], name + ": range is reversed")

    def network(self, document, label):
        if not self.check(isinstance(document, dict), label + ": network object required"):
            return set(), set()
        self.check(type(document.get("snapshotYear")) is int, label + ": snapshotYear integer required")
        self.check(type(document.get("sampleData")) is bool, label + ": sampleData boolean required")
        nodes, edges = document.get("nodes"), document.get("edges")
        if not self.check(isinstance(nodes, list) and isinstance(edges, list), label + ": nodes/edges arrays required"):
            return set(), set()
        ids, edge_ids = set(), set()
        for node in nodes:
            if not self.check(isinstance(node, dict), label + ": node object required"):
                continue
            name = f"{label}/node/{node.get('id')}"
            identifier = node.get("id")
            self.text(identifier, name + ".id")
            self.check(isinstance(identifier, str) and identifier not in ids, name + ": duplicate/invalid node ID")
            if isinstance(identifier, str):
                ids.add(identifier)
            self.text(node.get("name"), name + ".name")
            self.check(node.get("kind") in KINDS or (self.proposed and node.get("kind") in BACKBONE_KINDS), name + ": invalid kind")
            if node.get("kind") in BACKBONE_KINDS:
                self.check(node.get("layer") == "backbone", name + ": reference kind requires backbone layer")
            if node.get("layer") == "backbone":
                self.check(not node.get("companyId"), name + ": backbone cannot claim a historical supplier identity")
            if node.get("tier") is not None or not self.proposed:
                self.check(type(node.get("tier")) is int and 1 <= node["tier"] <= 7, name + ": tier must be 1 through 7 (null requires a contract decision)")
            for key in ["tier", "ticker", "partType", "appleRevenueShare"]:
                self.check(key in node, name + ": missing " + key)
            self.number(node.get("lon"), name + ".lon", -180, 180)
            self.number(node.get("lat"), name + ".lat", -90, 90)
            self.check(node.get("precision") in PRECISIONS, name + ": invalid precision")
            self.text(node.get("region"), name + ".region")
            self.check(node.get("ticker") is None or isinstance(node["ticker"], str), name + ": ticker must be text or null")
            self.check(node.get("partType") is None or isinstance(node["partType"], str), name + ": partType must be text or null")
            if "classification" in node:
                from pipeline.company_registry import CLASS_BASIS
                classification = node["classification"]
                self.check(node.get("tierStatus") == "inferred" and node.get("tierBasis") == CLASS_BASIS, name + ": model-classified tier needs inferred provenance")
                self.check(node.get("confidence") == classification.get("confidence") and node.get("confidence") in {"high", "medium", "low", "unknown"}, name + ": classification confidence required")
                if classification.get("tier") is None:
                    self.check(node.get("tier") is None, name + ": empty CSV tier must stay null")
                self.check(classification.get("reference") == "data/reference/supplier_classes.csv", name + ": classification reference required")
            elif "tierStatus" in node:
                from pipeline.tiers import inferred_tier
                expected = inferred_tier(node.get("partType"))
                self.check(all(node.get(k) == v for k, v in expected.items()), name + ": inferred tier must follow the approved part-type mapping")
            if node.get("appleRevenueShare") is not None:
                self.number(node["appleRevenueShare"], name + ".appleRevenueShare", 0, 1)
            self.sources(node.get("sources"), name, document.get("sampleData") is True)
        for edge in edges:
            if not self.check(isinstance(edge, dict), label + ": edge object required"):
                continue
            name = f"{label}/edge/{edge.get('id')}"
            identifier = edge.get("id")
            self.text(identifier, name + ".id")
            self.check(isinstance(identifier, str) and identifier not in edge_ids, name + ": duplicate/invalid edge ID")
            if isinstance(identifier, str):
                edge_ids.add(identifier)
            self.check(edge.get("from") in ids and edge.get("to") in ids, name + ": dangling edge endpoint")
            self.check(edge.get("mode") in MODES or (self.proposed and edge.get("relation") == "supply" and edge.get("mode") is None), name + ": invalid mode")
            if "relation" in edge:
                self.check(edge.get("relation") in {"route", "supply"}, name + ": relation must be route or supply")
                if edge.get("status") == "inferred":
                    self.check(edge.get("confidence") in {"high", "medium", "low", "unknown"}, name + ": inferred edge confidence required")
                    self.text(edge.get("basis"), name + ".basis")
                if edge.get("relation") == "supply":
                    self.check(edge.get("mode") is None, name + ": supply inference must not invent a movement mode")
                if edge.get("mode") == "sea":
                    self.text(edge.get("laneName"), name + ".laneName")
            self.check((self.proposed and "carriesTier" in edge and edge["carriesTier"] is None) or (type(edge.get("carriesTier")) is int and 1 <= edge["carriesTier"] <= 7), name + ": invalid carriesTier")
            self.check(edge.get("status") in {"known", "inferred"}, name + ": invalid link status")
            self.sources(edge.get("sources"), name, document.get("sampleData") is True)
            if edge.get("layer") in {"backbone", "supplier_access"}:
                self.check(edge.get("status") == "inferred" and edge.get("routingVerified") is False, name + ": unverified backbone route must be inferred")
                self.text(edge.get("basis"), name + ".basis")
                self.check(all(n in ids for n in edge.get("viaNodeIds", [])), name + ": dangling route transit node")
                if edge.get("alternativeTo"):
                    self.check(any(e.get("id") == edge["alternativeTo"] for e in edges), name + ": dangling alternative route")
            if "via" in edge:
                self.check(isinstance(edge["via"], list), name + ": via must be an array")
                for pair in edge["via"] if isinstance(edge["via"], list) else []:
                    if self.check(isinstance(pair, list) and len(pair) == 2, name + ": invalid waypoint"):
                        self.number(pair[0], name + ".via.lon", -180, 180)
                        self.number(pair[1], name + ".via.lat", -90, 90)
        # Validate every sea edge, including sample fixtures. The independent
        # pinned mask has no edge-controlled exemption mechanism.
        by_id = {n.get("id"): n for n in nodes if isinstance(n, dict)}
        for edge in edges:
            if not isinstance(edge, dict) or edge.get("mode") != "sea" or edge.get("from") not in by_id or edge.get("to") not in by_id:
                continue
            try:
                from pipeline.sea_geometry import sea_route_errors
                for error in sea_route_errors(edge, by_id):
                    self.check(False, f"{label}/edge/{edge.get('id')}: {error}")
            except (ValueError, TypeError, KeyError, OSError) as exc:
                self.check(False, f"{label}/edge/{edge.get('id')}: cannot validate sea geometry: {exc}")
        return ids, edge_ids

    def scenario(self, scenario, network, node_ids, edge_ids, label):
        if not self.check(isinstance(scenario, dict), label + ": scenario object required"):
            return
        for key in ["id", "title", "headline"]:
            self.text(scenario.get(key), label + "." + key)
        self.check(scenario.get("type") in TYPES, label + ": invalid scenario type")
        start = self.day(scenario.get("start"), label + ".start")
        end = self.day(scenario.get("end"), label + ".end")
        if start and end:
            self.check(scenario["start"] <= scenario["end"], label + ": reversed event dates")
        self.check(scenario.get("snapshotYear") == network.get("snapshotYear"), label + ": event network uses a different Supplier List year")
        self.check(type(scenario.get("sampleData")) is bool, label + ": sampleData boolean required")
        if "cohort" in scenario:
            cohort = scenario["cohort"]
            self.check(cohort.get("snapshotYear") == scenario["snapshotYear"], label + ": cohort source year differs from scenario")
            if cohort.get("snapshotYear") != cohort.get("eventYear"):
                self.check(cohort.get("assumption") is True and cohort.get("proxyApproved") is True, label + ": nearby-year cohort needs explicit approval and assumption flag")
        if "companyPredictions" in scenario:
            supplier_ids = {n["id"] for n in network.get("nodes", []) if n.get("layer") != "backbone"}
            self.company_predictions(scenario, supplier_ids, label)
        shock = scenario.get("shock", {})
        if not self.check(isinstance(shock, dict), label + ": shock object required"):
            shock = {}
        self.check("capacityLoss" in shock, label + ": missing shock.capacityLoss")
        self.check(isinstance(shock.get("nodeIds"), list) and all(n in node_ids for n in shock.get("nodeIds", [])), label + ": invalid shock node reference")
        if shock.get("capacityLoss") is not None or not self.proposed:
            self.number(shock.get("capacityLoss"), label + ".shock.capacityLoss", 0, 1)
        if self.proposed and "location" in shock:
            point = shock["location"]
            self.number(point.get("lon"), label + ".shock.location.lon", -180, 180)
            self.number(point.get("lat"), label + ".shock.location.lat", -90, 90)
            self.check(point.get("precision") in PRECISIONS | {"sea-area"}, label + ": invalid shock precision")
            self.sources(point.get("sources"), label + ".shock.location", scenario.get("sampleData") is True)
        for key in ["predictions", "actual", "options"]:
            if not self.check(isinstance(scenario.get(key), list), label + "." + key + ": array required"):
                return
        predicted = set()
        for prediction in scenario.get("predictions", []):
            node = prediction.get("nodeId")
            self.check(node in node_ids and node not in predicted, label + ": invalid/duplicate prediction reference")
            predicted.add(node)
            self.check(not any(n.get("id") == node and n.get("layer") == "backbone" for n in network.get("nodes", [])), label + ": supplier prediction cannot attach to backbone context")
            valid = all(self.number(prediction.get(key), f"{label}/{node}.{key}", 0, 1) for key in ["pHit", "ciLow", "ciHigh"])
            if valid:
                self.check(prediction["ciLow"] <= prediction["pHit"] <= prediction["ciHigh"], label + ": invalid prediction interval")
            self.check(type(prediction.get("lowConfidence")) is bool, label + ": lowConfidence boolean required")
            self.check(isinstance(prediction.get("shap"), list), label + ": SHAP array required")
            for contribution in prediction.get("shap", []):
                self.text(contribution.get("feature"), label + ".shap.feature")
                self.number(contribution.get("value"), label + ".shap.value")
        actual_ids = set()
        for actual in scenario.get("actual", []):
            self.check(actual.get("nodeId") in node_ids and actual.get("nodeId") not in actual_ids, label + ": invalid/duplicate actual reference")
            actual_ids.add(actual.get("nodeId"))
            self.check(type(actual.get("hit")) is bool, label + ": actual.hit boolean required")
            self.number(actual.get("car"), label + ".actual.car")
        for option in scenario.get("options", []):
            for key in ["id", "label", "detail"]:
                self.text(option.get(key), label + ".option." + key)
            for key in ["unitsRecovered", "extraCostUsd"]:
                self.interval(option.get(key), label + ".option." + key, 0)
            self.number(option.get("daysToEffect"), label + ".option.daysToEffect", 0)
            self.check(type(option.get("defaultOn")) is bool and type(option.get("assumption")) is bool, label + ": option flags must be booleans")
        quota = scenario.get("quota")
        self.check("quota" in scenario, label + ": missing quota")
        if quota is not None or not self.proposed:
            if self.check(isinstance(quota, dict), label + ": quota object required (null requires a contract decision)"):
                weeks = quota.get("weeks", [])
                self.check(isinstance(weeks, list), label + ": weeks array required")
                for day in weeks:
                    self.day(day, label + ".quota.weeks")
                self.check(len(weeks) == len(set(weeks)) and weeks == sorted(weeks), label + ": weeks must be unique and chronological")
                for key in ["target", "noAction", "withPlan"]:
                    values = quota.get(key)
                    if self.check(isinstance(values, list) and len(values) == len(weeks), label + ".quota." + key + ": array must match weeks"):
                        for value in values:
                            self.number(value, label + ".quota." + key, 0)
                self.text(quota.get("recoverySentence"), label + ".quota.recoverySentence")
        money = scenario.get("money", {})
        if not self.check(isinstance(money, dict), label + ": money object required"):
            money = {}
        for key in ["revenueAtRisk", "delayedShare"]:
            self.check(key in money, label + ": missing money." + key)
        self.number(money.get("coinUsd"), label + ".money.coinUsd", 0.000001)
        self.interval(money.get("revenueAtRisk"), label + ".money.revenueAtRisk", 0, nullable=True)
        if money.get("delayedShare") is not None or not self.proposed:
            self.number(money.get("delayedShare"), label + ".money.delayedShare", 0, 1)
        self.check(type(money.get("assumption")) is bool, label + ": money.assumption boolean required")
        routes = scenario.get("affectedRoutes", {})
        edge_by_id = {e["id"]: e for e in network.get("edges", [])}
        for key in ["blocked", "detour", "expedited"]:
            self.check(isinstance(routes.get(key), list) and all(e in edge_ids for e in routes.get(key, [])), label + ": invalid affected-route reference")
            self.check(all(edge_by_id.get(e, {}).get("relation", "route") == "route" for e in routes.get(key, [])), label + ": affectedRoutes must reference physical route edges, not supply relationships")
        if "backbone" in network:
            self.check(network["backbone"].get("approval", {}).get("approved") is True, label + ": backbone format needs explicit approval")
            self.check(scenario.get("affectedRoutesStatus") == "inferred", label + ": inferred exposure status required")
            self.text(scenario.get("affectedRoutesBasis"), label + ".affectedRoutesBasis")
            blocked = set(routes.get("blocked", []))
            self.check(not blocked & (set(routes.get("detour", [])) | set(routes.get("expedited", []))), label + ": blocked route cannot be an available alternative")
        sensitivity = scenario.get("sensitivity", [])
        self.check(isinstance(sensitivity, list), label + ": sensitivity array required")
        for item in sensitivity:
            self.text(item.get("assumption"), label + ".sensitivity.assumption")
            self.text(item.get("label"), label + ".sensitivity.label")
            self.number(item.get("spearman"), label + ".sensitivity.spearman", -1, 1)
        if all(type(v.get("spearman")) in {int, float} for v in sensitivity):
            self.check([abs(v["spearman"]) for v in sensitivity] == sorted((abs(v["spearman"]) for v in sensitivity), reverse=True), label + ": sensitivity must be ranked by absolute correlation")
        if "optimization" in scenario:
            optimization = scenario["optimization"]
            self.check(optimization.get("assumption") is True and optimization.get("inputRanges", {}).get("approved") is True, label + ": optimizer needs approved, explicit assumptions")
            self.check(isinstance(quota, dict) and quota.get("assumption") is True, label + ": modeled quota must be marked as assumed")
            if not isinstance(quota, dict):
                return
            self.text(quota.get("unit"), label + ".quota.unit")
            self.text(quota.get("scope"), label + ".quota.scope")
            self.check(type(optimization.get("draws")) is int and optimization["draws"] > 0, label + ": positive Monte Carlo draw count required")
            ids = {o["id"] for o in scenario["options"]}
            for key in ["noActionRange", "withPlanRange"]:
                bands = quota.get(key)
                if self.check(isinstance(bands, list) and len(bands) == len(quota["weeks"]), label + ": weekly uncertainty bands required"):
                    for point, band in zip(quota[key.removesuffix("Range")], bands):
                        self.interval(band, label + ".quota." + key, 0)
                        if isinstance(band, list) and len(band) == 2:
                            self.check(band[0] <= point <= band[1], label + ": weekly median outside band")
            plans = quota.get("optionPlans", [])
            seen = set()
            for plan in plans:
                selected = plan.get("optionIds", [])
                mask = frozenset(selected)
                self.check(mask <= ids and len(selected) == len(mask) and mask not in seen, label + ": invalid option combination")
                seen.add(mask)
                values = plan.get("withPlan")
                if self.check(isinstance(values, list) and len(values) == len(quota["weeks"]), label + ": option plan must match weeks"):
                    for value in values:
                        self.number(value, label + ".quota.optionPlans.withPlan", 0)
                self.interval(plan.get("extraCostUsd"), label + ".quota.optionPlans.extraCostUsd", 0)
            self.check(len(seen) == 2 ** len(ids), label + ": every option combination must have a paired plan")
            default_ids = frozenset(o["id"] for o in scenario["options"] if o["defaultOn"])
            for plan in plans:
                if frozenset(plan["optionIds"]) == default_ids:
                    self.check(plan["withPlan"] == quota["withPlan"], label + ": default combination disagrees with quota.withPlan")

    def company_predictions(self, scenario, node_ids, label):
        cohort = scenario.get("cohort", {})
        self.check(cohort.get("locationCoverage") == "company-only" and cohort.get("companyOnlyExportApproved") is True and cohort.get("assumption") is True and not node_ids, label + ": company-only export needs explicit approval, an assumption flag, and no invented sites")
        records = scenario["companyPredictions"]
        if not self.check(isinstance(records, list) and bool(records), label + ": company predictions array required"):
            return
        seen = set()
        for record in records:
            self.check(not {"lon", "lat", "nodeId"} & record.keys(), label + ": unlocated company prediction cannot assert site coordinates or node IDs")
            identifier = record.get("companyId")
            self.text(identifier, label + ".companyId")
            self.check(identifier not in seen, label + ": duplicate company prediction")
            seen.add(identifier)
            self.text(record.get("supplier"), label + ".supplier")
            valid = all(self.number(record.get(k), label + ".company." + k, 0, 1) for k in ["pHit", "ciLow", "ciHigh"])
            if valid:
                self.check(record["ciLow"] <= record["pHit"] <= record["ciHigh"], label + ": invalid company prediction interval")
            self.check(type(record.get("lowConfidence")) is bool and type(record.get("outcomeObservable")) is bool, label + ": company outcome flags required")
            self.sources(record.get("sources"), label + ".company", sample=False)
            self.text(record.get("predictionScope"), label + ".company.predictionScope")
            for key in ["shapBaseValue", "shapMeanRawScore"]:
                self.number(record.get(key), label + ".company." + key)
            for contribution in record.get("shap", []):
                self.text(contribution.get("feature"), label + ".company.shap.feature")
                self.number(contribution.get("value"), label + ".company.shap.value")
            actual = record.get("actual")
            self.check(record.get("outcomeObservable") == (actual is not None), label + ": inconsistent company outcome availability")
            if actual is not None:
                self.check(type(actual.get("hit")) is bool, label + ": company actual.hit boolean required")
                self.number(actual.get("car"), label + ".company.actual.car")

    def metrics(self, document):
        self.text(document.get("model"), "metrics.model")
        for key in ["events", "rows"]:
            self.check(type(document.get(key)) is int and document[key] >= 0, "metrics." + key + ": nonnegative integer required")
        self.check(isinstance(document.get("loeo"), list), "metrics.loeo: array required")
        for fold in document.get("loeo", []):
            self.text(fold.get("eventId"), "metrics.loeo.eventId")
            keys = ["auc", "baselineAuc"] + (["distanceAuc"] if "distanceAuc" in fold else [])
            for key in keys:
                self.number(fold.get(key), "metrics.loeo." + key, 0, 1)
            if "rows" in fold and "hits" in fold:
                self.check(type(fold["rows"]) is int and type(fold["hits"]) is int and 0 < fold["hits"] < fold["rows"], "metrics.loeo: reported event must have both supplier outcome classes")
            self.number(fold.get("brier"), "metrics.loeo.brier", 0, 1)
            for key, interval in fold.get("auc95", {}).items():
                self.interval(interval, "metrics.loeo.auc95." + key, 0, 1)
        if "modelSelection" in document:
            selection = document["modelSelection"]
            candidates = {"distance", "logistic_regression", "lightgbm"}
            folds = selection.get("outerFolds", [])
            counts = selection.get("selectionCounts", {})
            self.check(len(folds) == 7 and set(counts) == candidates, "metrics.modelSelection: seven folds and all candidate counts required")
            self.check(all(type(v) is int and v >= 0 for v in counts.values()) and sum(counts.values()) == 7, "metrics.modelSelection: pick counts must total seven")
            main = selection.get("mainModel")
            self.check(main == document.get("model") and main in candidates, "metrics.modelSelection: main model mismatch")
            if main in counts and counts:
                self.check(counts[main] == max(counts.values()) == selection.get("mainModelPickCount"), "metrics.modelSelection: main model must have the most picks")
            self.number(selection.get("nestedAuc"), "metrics.modelSelection.nestedAuc", 0, 1)
            self.interval(selection.get("nestedAuc95"), "metrics.modelSelection.nestedAuc95", 0, 1)
            observed = {kind: 0 for kind in candidates}
            for fold in folds:
                event = fold.get("eventId")
                training = set(fold.get("trainingEvents", []))
                self.check(len(training) == 6 and event not in training, "metrics.modelSelection: outer event leakage or wrong training count")
                inner = fold.get("innerFolds", [])
                self.check(len(inner) == 6 and {i.get("heldOutEvent") for i in inner} == training, "metrics.modelSelection: six distinct inner held-out events required")
                means = fold.get("innerMeanAuc", {})
                chosen = fold.get("selectedModel")
                if chosen in observed:
                    observed[chosen] += 1
                self.check(set(means) == candidates and chosen in means, "metrics.modelSelection: all three inner candidates required")
                if chosen in means and all(type(v) in {int, float} for v in means.values()):
                    self.check(means[chosen] >= max(means.values()) - 1e-12, "metrics.modelSelection: selected model did not maximize mean inner AUC")
                for item in inner:
                    self.check(set(item.get("trainingEvents", [])) == training - {item.get("heldOutEvent")}, "metrics.modelSelection: inner event leakage or wrong training set")
                for kind, value in means.items():
                    self.number(value, "metrics.modelSelection.innerMeanAuc." + kind, 0, 1)
            self.check(observed == counts, "metrics.modelSelection: recorded counts disagree with fold choices")
        for key in ["auc", "brier", "baselineAuc"]:
            self.interval(document.get("overall", {}).get(key), "metrics.overall." + key, 0, 1)
        self.check(isinstance(document.get("calibration"), list), "metrics.calibration: array required")
        for item in document.get("calibration", []):
            self.number(item.get("binMid"), "metrics.calibration.binMid", 0, 1)
            self.number(item.get("observed"), "metrics.calibration.observed", 0, 1)
            self.check(type(item.get("n")) is int and item["n"] >= 0, "metrics.calibration.n: nonnegative integer required")

    def forecasts(self, document):
        self.check(type(document.get("sampleData")) is bool, "forecasts.sampleData: boolean required")
        self.check(isinstance(document.get("series"), list), "forecasts.series: array required")
        ids = set()
        for series in document.get("series", []):
            self.text(series.get("id"), "forecasts.id")
            self.check(series.get("id") not in ids, "forecasts: duplicate series ID")
            ids.add(series.get("id"))
            for key in ["label", "unit"]:
                self.text(series.get(key), "forecasts." + key)
            self.citation(series.get("source"), "forecasts.source", document.get("sampleData") is True)
            dates = {}
            for key in ["history", "forecast", "baseline"]:
                entries = series.get(key, [])
                self.check(isinstance(entries, list), "forecasts." + key + ": array required")
                dates[key] = [r.get("date") for r in entries]
                for entry in entries:
                    self.day(entry.get("date"), "forecasts." + key + ".date")
                    fields = ["q10", "q50", "q90"] if key == "forecast" else ["value"]
                    valid = all(self.number(entry.get(field), "forecasts." + key + "." + field) for field in fields)
                    if valid and key == "forecast":
                        self.check(entry["q10"] <= entry["q50"] <= entry["q90"], "forecasts: crossed quantiles")
                if all(isinstance(v, str) for v in dates[key]):
                    self.check(dates[key] == sorted(set(dates[key])), "forecasts: dates must be unique and chronological")
            self.check(dates["forecast"] == dates["baseline"], "forecasts: baseline and forecast dates differ")
            if dates["history"] and dates["forecast"]:
                self.check(dates["history"][-1] < dates["forecast"][0], "forecasts: forecast overlaps history")
            for key in ["mase", "baselineMase"]:
                self.number(series.get("metrics", {}).get(key), "forecasts.metrics." + key, 0)
            self.number(series.get("metrics", {}).get("coverage80"), "forecasts.metrics.coverage80", 0, 1)

    def run(self):
        root_network = self.load("network.json")
        node_ids, edge_ids = self.network(root_network, "network.json")
        index = self.load("scenarios/index.json")
        self.check(isinstance(index, list), "scenarios/index.json: array required")
        seen = set()
        for entry in index if isinstance(index, list) else []:
            identifier = entry.get("id")
            if not self.check(isinstance(identifier, str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", identifier) is not None, "scenarios/index.json: unsafe ID"):
                continue
            self.check(identifier not in seen, "scenarios/index.json: duplicate ID")
            seen.add(identifier)
            scenario = self.load(f"scenarios/{identifier}.json")
            for key in ["id", "title", "type", "start"]:
                self.check(scenario.get(key) == entry.get(key), f"{identifier}: index metadata differs from scenario")
            network, nodes, edges = root_network, node_ids, edge_ids
            if "networkPath" in scenario:
                self.check(self.proposed, f"{identifier}: networkPath is absent from the original frozen contract")
                path = scenario["networkPath"]
                if self.check(isinstance(path, str) and path.startswith("networks/") and path.endswith(".json") and ".." not in Path(path).parts, f"{identifier}: unsafe networkPath"):
                    network = self.load(path)
                    nodes, edges = self.network(network, path)
            self.scenario(scenario, network, nodes, edges, identifier)
        self.metrics(self.load("metrics.json"))
        if (self.folder / "forecasts.json").exists():
            self.forecasts(self.load("forecasts.json"))
        return self.errors


def validate_folder(folder: Path, extensions=True):
    validator = Validator(folder, extensions)
    try:
        return validator.run()
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        validator.errors.append(f"Malformed export structure: {type(exc).__name__}: {str(exc)[:160]}")
        return validator.errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--frozen", action="store_true", help="Check the original contract without the user-approved M7 extensions")
    args = parser.parse_args()
    errors = validate_folder(args.folder, extensions=not args.frozen)
    for error in errors:
        print("ERROR:", error)
    if not errors:
        print(f"Validated {args.folder}" + (" against the original frozen contract" if args.frozen else " with the user-approved M7 extensions"))
    raise SystemExit(bool(errors))
