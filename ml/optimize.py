"""Parameterized OR-Tools planning LP and paired Monte Carlo option plans.

--review uses unapproved proposed inputs and writes only a review summary.
Normal runs require an approved input file and save processed outputs for export.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def solve_plan(demand, base_capacity, options, penalty):
    """options contain explicit weekly capacity vectors and incremental unit cost."""
    from ortools.linear_solver import pywraplp
    if len(demand) != len(base_capacity) or not demand:
        raise ValueError("Demand and base capacity must have equal nonzero length")
    values = [*demand, *base_capacity, penalty]
    for option in options:
        if len(option["capacity"]) != len(demand):
            raise ValueError("Option capacity must match the planning horizon")
        values.extend([*option["capacity"], option["cost"]])
    if any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("LP inputs must be finite and nonnegative")
    solver = pywraplp.Solver.CreateSolver("GLOP")
    if solver is None:
        raise RuntimeError("OR-Tools GLOP solver unavailable")
    base, unmet, flows = [], [], [[] for _ in options]
    for t, target in enumerate(demand):
        base.append(solver.NumVar(0, base_capacity[t], f"base_{t}"))
        unmet.append(solver.NumVar(0, target, f"unmet_{t}"))
        for j, option in enumerate(options):
            flows[j].append(solver.NumVar(0, option["capacity"][t], f"flow_{j}_{t}"))
        solver.Add(base[t] + sum(flow[t] for flow in flows) + unmet[t] == target)
    costs = sum(option["cost"] * sum(flow) for option, flow in zip(options, flows))
    solver.Minimize(sum(unmet) + penalty * costs)
    status = solver.Solve()
    if status != pywraplp.Solver.OPTIMAL or not solver.VerifySolution(1e-7, False):
        raise RuntimeError("LP failed to return a verified optimal solution")
    flows = [[max(0.0, v.solution_value()) for v in flow] for flow in flows]
    shortfall = [max(0.0, v.solution_value()) for v in unmet]
    return {"delivered": [target - missing for target, missing in zip(demand, shortfall)], "unmet": shortfall,
            "flows": flows, "extraCostUsd": sum(o["cost"] * sum(flow) for o, flow in zip(options, flows)),
            "objective": solver.Objective().Value()}


def ramped_capacity(capacity, lead, ramp, weeks):
    if any(not math.isfinite(v) or v < 0 for v in [capacity, lead, ramp]):
        raise ValueError("Invalid capacity, lead time, or ramp time")
    return [0.0 if t < lead else capacity * min(1.0, (t - lead + 1) / max(1.0, ramp)) for t in range(weeks)]


def checked_range(value, label, low=0, high=None):
    if not isinstance(value, list) or len(value) != 2 or any(type(v) not in {int, float} or not math.isfinite(v) for v in value):
        raise ValueError(label + ": finite [low, high] required")
    if value[0] < low or value[1] < value[0] or (high is not None and value[1] > high):
        raise ValueError(label + ": invalid range")
    return value


def validate_inputs(spec):
    if spec.get("assumption") is not True or not spec.get("scope") or not spec.get("unit"):
        raise ValueError("Scope, units, and explicit assumption flag are required")
    if type(spec.get("weeks")) is not int or spec["weeks"] < 1:
        raise ValueError("Positive planning horizon required")
    for key in ["demandPerWeek", "baseRecoveryWeeks"]:
        checked_range(spec[key], key, low=1e-9)
    checked_range(spec["initialCapacityFraction"], "initialCapacityFraction", high=1)
    checked_range(spec["costPenaltyUnitsPerUsd"], "costPenaltyUnitsPerUsd")
    ids = [o["id"] for o in spec["options"]]
    if not 1 <= len(ids) <= 8 or len(ids) != len(set(ids)):
        raise ValueError("One to eight uniquely identified options required")
    for option in spec["options"]:
        if option.get("assumption") is not True or type(option.get("defaultOn")) is not bool:
            raise ValueError("Each option needs assumption/defaultOn flags")
        for key in ["capacityPerWeek", "leadWeeks", "rampWeeks", "costUsdPerIndexUnit"]:
            checked_range(option[key], option["id"] + "." + key)


def interval(values):
    return np.quantile(values, [0.025, 0.975], axis=0).T.tolist()


def sensitivity_label(key, spec):
    general = {"demandPerWeek": "Weekly demand", "initialCapacityFraction": "Starting capacity",
               "baseRecoveryWeeks": "Time for regular capacity to recover", "costPenaltyUnitsPerUsd": "Weight given to extra cost"}
    if key in general:
        return general[key]
    option_id, field = key.split(".", 1)
    option = next(o for o in spec["options"] if o["id"] == option_id)
    field_label = {"capacityPerWeek": "weekly capacity", "leadWeeks": "time to start",
                   "rampWeeks": "time to reach full capacity", "costUsdPerIndexUnit": "cost per indexed unit"}[field]
    return option["label"] + ": " + field_label


def simulate(spec, event, draws=None, raw_dir=None):
    """Use the same draw for every switch combination; no independent averaging."""
    from scipy.stats import spearmanr
    import ortools
    validate_inputs(spec)
    draws = spec["draws"] if draws is None else draws
    if type(draws) is not int or draws < 2:
        raise ValueError("At least two Monte Carlo draws required")
    seed = int(spec["seed"]) ^ int(hashlib.sha256(event["id"].encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    count, weeks = len(spec["options"]), spec["weeks"]
    masks = list(itertools.product([False, True], repeat=count))
    default_mask = tuple(o["defaultOn"] for o in spec["options"])
    samples, capacities, demands = [], [], []
    plans = {mask: {"delivered": [], "cost": [], "unmet": []} for mask in masks}
    ranges = {key: spec[key] for key in ["demandPerWeek", "initialCapacityFraction", "baseRecoveryWeeks", "costPenaltyUnitsPerUsd"]}
    ranges.update({f"{o['id']}.{key}": o[key] for o in spec["options"] for key in ["capacityPerWeek", "leadWeeks", "rampWeeks", "costUsdPerIndexUnit"]})
    for _ in range(draws):
        sample = {key: float(rng.uniform(*value)) for key, value in ranges.items()}
        demand = [sample["demandPerWeek"]] * weeks
        base = [demand[t] * (sample["initialCapacityFraction"] + (1 - sample["initialCapacityFraction"]) * min(1, t / sample["baseRecoveryWeeks"])) for t in range(weeks)]
        alternatives = [{"capacity": ramped_capacity(sample[f"{o['id']}.capacityPerWeek"], sample[f"{o['id']}.leadWeeks"], sample[f"{o['id']}.rampWeeks"], weeks),
                         "cost": sample[f"{o['id']}.costUsdPerIndexUnit"]} for o in spec["options"]]
        samples.append(sample)
        capacities.append(base)
        demands.append(demand)
        for mask in masks:
            result = solve_plan(demand, base, [option for j, option in enumerate(alternatives) if mask[j]], sample["costPenaltyUnitsPerUsd"])
            plans[mask]["delivered"].append(result["delivered"])
            plans[mask]["cost"].append(result["extraCostUsd"])
            plans[mask]["unmet"].append(sum(result["unmet"]))
    baseline = plans[tuple(False for _ in range(count))]
    default = plans[default_mask]
    options = []
    for j, option in enumerate(spec["options"]):
        mask = tuple(k == j for k in range(count))
        recovered = np.sum(np.array(plans[mask]["delivered"]) - np.array(baseline["delivered"]), axis=1)
        days = [math.ceil(s[f"{option['id']}.leadWeeks"]) * 7 for s in samples]
        options.append({"id": option["id"], "label": option["label"],
                        "detail": "Illustrative indexed capacity and costs; individual recovery is not additive with other options",
                        "unitsRecovered": interval(recovered), "extraCostUsd": interval(plans[mask]["cost"]),
                        "daysToEffect": float(np.median(days)), "daysToEffectRange": interval(days),
                        "defaultOn": option["defaultOn"], "assumption": True, "inputRanges": option})
    sensitivity = []
    response = np.array(default["unmet"])
    if np.ptp(response) > 1e-10:
        for key in ranges:
            values = np.array([s[key] for s in samples])
            if np.ptp(values) <= 1e-10:
                continue
            correlation = float(spearmanr(values, response).statistic)
            if math.isfinite(correlation):
                sensitivity.append({"assumption": key, "label": sensitivity_label(key, spec), "spearman": correlation})
    sensitivity.sort(key=lambda v: abs(v["spearman"]), reverse=True)
    target, planned = np.median(demands, axis=0), np.median(default["delivered"], axis=0)
    recovered_from = next((t for t in range(weeks) if np.all(planned[t:] >= target[t:] - 1e-7)), None)
    recovery = "Median indexed plan reaches the assumed weekly target from week " + str(recovered_from + 1) if recovered_from is not None else "Median indexed plan does not sustain the assumed target within this horizon"
    quota = {"weeks": [(date.fromisoformat(event["start"]) + timedelta(weeks=t)).isoformat() for t in range(weeks)],
             "target": target.tolist(), "noAction": np.median(baseline["delivered"], axis=0).tolist(), "withPlan": planned.tolist(),
             "recoverySentence": recovery, "unit": spec["unit"], "assumption": True, "scope": spec["scope"],
             "noActionRange": interval(baseline["delivered"]), "withPlanRange": interval(default["delivered"]),
             "optionPlans": [{"optionIds": [o["id"] for j, o in enumerate(spec["options"]) if mask[j]],
                              "withPlan": np.median(plan["delivered"], axis=0).tolist(), "withPlanRange": interval(plan["delivered"]),
                              "extraCostUsd": interval(plan["cost"])} for mask, plan in plans.items()]}
    if raw_dir is not None:
        raw_dir.mkdir(parents=True, exist_ok=True)
        with (raw_dir / f"{event['id']}_draws.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=[*ranges, "defaultUnmet", "defaultCostUsd"])
            writer.writeheader()
            writer.writerows({**s, "defaultUnmet": default["unmet"][i], "defaultCostUsd": default["cost"][i]} for i, s in enumerate(samples))
    return {"sampleData": True, "options": options, "quota": quota, "sensitivity": sensitivity,
            "optimization": {"assumption": True, "scope": spec["scope"], "draws": draws, "seed": seed, "inputRanges": spec,
                             "rangeDefinition": "2.5th/97.5th percentiles of independent uniform input draws; not empirically calibrated confidence bounds",
                             "solver": "OR-Tools GLOP", "ortoolsVersion": ortools.__version__, "pairedOptionCombinations": len(masks),
                             "sensitivityDefinition": "Spearman correlation with cumulative unmet indexed demand in the default plan; positive means more shortage",
                             "costDefinition": "Hypothetical incremental USD per indexed unit; no mapping to Apple units or revenue",
                             "baseCapacityRange": interval(capacities), "defaultExtraCostUsd": interval(default["cost"])}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", action="store_true")
    args = parser.parse_args()
    path = ROOT / ("data/review/optimizer_assumptions_proposed.json" if args.review else "data/sources/optimizer_assumptions.json")
    if not path.exists():
        parser.exit(1, "Missing approved optimizer inputs; review data/review/optimizer_method_proposal.md\n")
    spec = json.loads(path.read_text(encoding="utf-8"))
    if not args.review and spec.get("approved") is not True:
        parser.exit(1, "Optimizer assumptions require an explicit user decision\n")
    events = list(csv.DictReader((ROOT / "data/events.csv").open(encoding="utf-8")))
    outputs = {}
    for event in events:
        outputs[event["id"]] = simulate(spec, event, raw_dir=ROOT / "data/raw/optimizer")
        print(event["id"], spec["draws"], "draws;", len(outputs[event["id"]]["sensitivity"]), "ranked inputs", flush=True)
    target = ROOT / ("data/review/optimizer_preview.json" if args.review else "data/processed/optimizer_plans.json")
    target.write_text(json.dumps({"sampleData": True, "reviewOnly": args.review, "scenarios": outputs}, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    print("Saved", target.relative_to(ROOT), flush=True)


if __name__ == "__main__":
    main()
