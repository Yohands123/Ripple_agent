import copy
import json
from pathlib import Path

import pytest

from pipeline import export as exporter
from pipeline.validate import validate_folder

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def candidate():
    return exporter.build_bundle()


def test_frozen_fixtures_validate_including_explicit_sample_forecasts():
    assert validate_folder(ROOT / "contracts/fixtures") == []


def test_approved_candidate_validates_and_original_contract_still_detects_changes(candidate, tmp_path):
    exporter.write_bundle(candidate, tmp_path)
    assert validate_folder(tmp_path) == []
    errors = validate_folder(tmp_path, extensions=False)
    assert any("original frozen contract" in e for e in errors)
    assert any("tier must be" in e for e in errors)
    assert any("shock.capacityLoss" in e for e in errors)


@pytest.mark.parametrize("change,expected", [
    ("source", "require a source"),
    ("year", "different Supplier List year"),
    ("prediction", "invalid/duplicate prediction reference"),
    ("interval", "invalid prediction interval"),
    ("path", "unsafe networkPath"),
    ("forecast", "absolute public HTTP(S)"),
])
def test_invalid_evidence_and_cross_file_references_are_rejected(candidate, tmp_path, change, expected):
    bundle = copy.deepcopy(candidate)
    network = bundle["networks/suez-2021.json"]
    scenario = bundle["scenarios/suez-2021.json"]
    if change == "source":
        network["nodes"][0]["sources"] = []
    elif change == "year":
        network["snapshotYear"] = 2022
    elif change == "prediction":
        scenario["predictions"][0]["nodeId"] = "absent-site"
    elif change == "interval":
        scenario["predictions"][0]["ciLow"] = 1.0
    elif change == "path":
        scenario["networkPath"] = "networks/../../outside.json"
    elif change == "forecast":
        document = json.loads((ROOT / "contracts/fixtures/forecasts.json").read_text())
        document["sampleData"] = False
        bundle["forecasts.json"] = document
    exporter.write_bundle(bundle, tmp_path)
    assert any(expected in e for e in validate_folder(tmp_path))


def test_invalid_production_export_is_withheld_before_creating_app_folder(candidate, tmp_path, monkeypatch):
    invalid = copy.deepcopy(candidate)
    invalid["scenarios/suez-2021.json"]["predictions"][0]["nodeId"] = "absent-site"
    monkeypatch.setattr(exporter, "build_bundle", lambda root: invalid)
    with pytest.raises(ValueError, match="Export withheld"):
        exporter.export(root=tmp_path)
    assert not (tmp_path / "web/public/data/real").exists()


def test_nonfinite_json_is_rejected_before_schema_validation(tmp_path):
    (tmp_path / "network.json").write_text('{"snapshotYear": NaN}')
    errors = validate_folder(tmp_path)
    assert any("Non-JSON number" in e for e in errors)


def test_malformed_wire_types_report_errors_instead_of_crashing(candidate, tmp_path):
    bundle = copy.deepcopy(candidate)
    bundle["scenarios/suez-2021.json"]["predictions"] = [None]
    exporter.write_bundle(bundle, tmp_path)
    assert any("Malformed export structure" in e for e in validate_folder(tmp_path))


def test_site_outcomes_preserve_company_scope_and_label_inferred_routes(candidate):
    for path, network in candidate.items():
        if not path.startswith("networks/"):
            continue
        event_id = network["eventId"]
        scenario = candidate[f"scenarios/{event_id}.json"]
        assert network["snapshotYear"] == scenario["snapshotYear"]
        assert all(e["status"] == "inferred" and e["routingVerified"] is False for e in network["edges"])
        if scenario["quota"] is not None:
            assert scenario["quota"]["assumption"] is True
            assert scenario["optimization"]["inputRanges"]["approved"] is True
        assert scenario["money"]["revenueAtRisk"] is None
        assert all(n["sources"] for n in network["nodes"])
        assert all(n["tier"] is None for n in network["nodes"] if n["partType"] is None)
        assert all(n["tierStatus"] == "inferred" and n["tierBasis"] in {"mapped from part type", "model classification, see data/reference/supplier_classes.csv"} for n in network["nodes"] if n["partType"] is not None)
        assert all("Company" in p["predictionScope"] for p in scenario["predictions"])
        ids = {n["id"] for n in network["nodes"]}
        assert {a["nodeId"] for a in scenario["actual"]} <= ids


def test_expansion_keeps_company_only_scenarios_and_reports_only_selected_metric_events(candidate):
    metrics = candidate["metrics.json"]
    index = candidate["scenarios/index.json"]
    assert len(index) == metrics["predictionEvents"] == 9
    assert len(metrics["loeo"]) == metrics["events"] == 7
    assert sum(r["rows"] for r in metrics["loeo"]) == metrics["rows"]
    assert sum(r["n"] for r in metrics["calibration"]) == metrics["rows"]
    omitted = {r["eventId"] for r in metrics["excludedFromMetrics"]}
    assert omitted == {"japan-2011", "thailand-2011"}
    assert not omitted & {r["eventId"] for r in metrics["loeo"]}
    assert {r["eventId"] for r in metrics["excludedEvents"]} == {"japan-korea-2019", "taiwan-2024", "helene-2024"}
    for identifier in omitted:
        scenario = candidate[f"scenarios/{identifier}.json"]
        network = candidate[scenario["networkPath"]]
        assert not any(n["layer"] == "supplier" for n in network["nodes"])
        assert all(n["layer"] == "backbone" and "companyId" not in n for n in network["nodes"])
        assert scenario["predictions"] == scenario["actual"] == []
        companies = scenario["companyPredictions"]
        assert len(companies) == network["coverage"]["unlocatedCompanies"] == 156
        assert sum(r["outcomeObservable"] for r in companies) == next(r["rows"] for r in metrics["excludedFromMetrics"] if r["eventId"] == identifier)
        assert all(not {"nodeId", "lon", "lat"} & r.keys() for r in companies)
        assert scenario["cohort"]["assumption"] is True
        assert scenario["cohort"]["publicationYear"] == 2012


def test_reference_classification_preserves_filing_part_types_and_shared_dated_company_ids(candidate):
    import csv
    from pipeline.company_registry import CLASS_BASIS, registry
    attributes = {(r["eventId"], r["companyId"]): r for r in csv.DictReader((ROOT / "data/processed/features.csv").open(encoding="utf-8"))}
    classes = registry()
    for entry in candidate["scenarios/index.json"]:
        scenario = candidate[f"scenarios/{entry['id']}.json"]
        network = candidate[scenario["networkPath"]]
        for node in network["nodes"]:
            if "sourceCompany" not in node:
                continue
            assert node["companyId"] == classes.identifier(node["sourceCompany"], scenario["start"])
            feature = attributes[(entry["id"], node["companyId"])]
            if feature["part_type"] != "unknown":
                assert node["partType"] == feature["part_type"] and node["partTypeStatus"] == "sourced"
            row = classes.rows[node["sourceCompany"]]
            assert node["tierBasis"] == CLASS_BASIS and node["confidence"] == row["confidence"]
            if row["tierValue"] is None:
                assert node["tier"] is None
