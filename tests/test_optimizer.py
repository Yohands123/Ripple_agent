import copy
import json
from pathlib import Path

import numpy as np
import pytest

from ml.optimize import ramped_capacity, simulate, solve_plan, validate_inputs
from pipeline.export import build_bundle, write_bundle
from pipeline.validate import validate_folder

ROOT = Path(__file__).resolve().parents[1]


def test_lp_respects_capacity_conservation_and_cheapest_available_output():
    result = solve_plan([10, 10], [3, 3], [{"capacity": [4, 4], "cost": 1}, {"capacity": [5, 5], "cost": 3}], penalty=0.1)
    assert result["delivered"] == [10, 10]
    assert result["unmet"] == [0, 0]
    assert result["flows"] == [[4, 4], [3, 3]]
    assert result["extraCostUsd"] == 26
    assert result["objective"] == pytest.approx(2.6)


def test_cost_penalty_can_make_expensive_recovery_worse_than_unmet_demand():
    result = solve_plan([10], [3], [{"capacity": [4], "cost": 1}, {"capacity": [5], "cost": 3}], penalty=0.5)
    assert result["delivered"] == [7]
    assert result["unmet"] == [3]
    assert result["flows"] == [[4], [0]]
    assert result["objective"] == 5


def test_lead_time_and_ramp_bound_weekly_capacity():
    assert ramped_capacity(12, lead=2, ramp=3, weeks=6) == [0, 0, 4, 8, 12, 12]
    assert ramped_capacity(12, lead=0, ramp=0, weeks=2) == [12, 12]
    with pytest.raises(ValueError):
        solve_plan([10], [-1], [], 0.1)


def test_paired_draws_preserve_no_action_and_option_combinations():
    spec = json.loads((ROOT / "data/review/optimizer_assumptions_proposed.json").read_text())
    result = simulate(spec, {"id": "test", "start": "2021-03-23"}, draws=12)
    assert result == simulate(spec, {"id": "test", "start": "2021-03-23"}, draws=12)
    plans = result["quota"]["optionPlans"]
    assert len(plans) == 8
    assert next(p for p in plans if not p["optionIds"])["withPlan"] == result["quota"]["noAction"]
    default = next(p for p in plans if len(p["optionIds"]) == 3)
    assert default["withPlan"] == result["quota"]["withPlan"]
    assert np.all(np.array(default["withPlan"]) <= result["quota"]["target"])
    assert all(o["assumption"] and o["unitsRecovered"][0] >= -1e-8 for o in result["options"])
    assert [abs(s["spearman"]) for s in result["sensitivity"]] == sorted([abs(s["spearman"]) for s in result["sensitivity"]], reverse=True)
    assert result["optimization"]["assumption"] is True
    invalid = copy.deepcopy(spec)
    invalid["initialCapacityFraction"] = [0.5, 1.1]
    with pytest.raises(ValueError):
        validate_inputs(invalid)


def test_export_validator_rejects_unapproved_assumptions_and_missing_combinations(tmp_path):
    spec = json.loads((ROOT / "data/review/optimizer_assumptions_proposed.json").read_text())
    event = {"id": "suez-2021", "start": "2021-03-23"}
    plan = simulate(spec, event, draws=12)
    bundle = build_bundle()
    bundle["scenarios/suez-2021.json"].update(plan)
    write_bundle(bundle, tmp_path)
    assert any("optimizer needs approved" in e for e in validate_folder(tmp_path))
    plan["optimization"]["inputRanges"]["approved"] = True  # Synthetic validation case only.
    write_bundle(bundle, tmp_path)
    assert validate_folder(tmp_path) == []
    plan["quota"]["optionPlans"].pop()
    write_bundle(bundle, tmp_path)
    assert any("every option combination" in e for e in validate_folder(tmp_path))
