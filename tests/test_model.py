import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.train import Encoder, NUMERIC, calibration, distance_rule, lgb


def test_native_tree_shap_adds_to_the_actual_raw_prediction():
    x = np.column_stack([np.arange(40), np.arange(40) % 3])
    y = (x[:, 0] > 20).astype(int)
    model = lgb.train({"objective": "binary", "num_leaves": 3, "max_depth": 2, "min_data_in_leaf": 2, "num_threads": 1, "verbosity": -1},
                      lgb.Dataset(x, label=y), num_boost_round=5)
    contributions = model.predict(x, pred_contrib=True, num_threads=1)
    assert np.allclose(contributions.sum(axis=1), model.predict(x, raw_score=True, num_threads=1))


def test_distance_rule_ranks_nearby_points_and_uses_no_held_out_outcomes():
    result = distance_rule([0, 50, 100, 200], [0, 0, 0, 1], [0, 100, 200, np.nan])
    assert result[0] > result[1] > result[2]
    assert result[3] == 0.25
    assert ((result >= 0) & (result <= 1)).all()


def test_encoder_handles_a_new_held_out_category_without_fitting_on_it():
    training = pd.DataFrame({**{name: [np.nan, 1] for name in NUMERIC}, "part_type": ["semiconductors", "unknown"]})
    held = pd.DataFrame({**{name: [np.nan] for name in NUMERIC}, "part_type": ["unseen"]})
    encoder = Encoder().fit(training)
    values = encoder.transform(held)
    assert values.shape[1] == len(NUMERIC) + 2
    assert np.all(values[0, len(NUMERIC):] == 0)


def test_calibration_omits_empty_bins_and_preserves_real_counts():
    frame = pd.DataFrame({"pHit": [0.01, 0.02, 0.95], "hit": [0, 1, 1]})
    bins = calibration(frame)
    assert sum(b["n"] for b in bins) == 3
    assert bins[0]["observed"] == 0.5 and len(bins) == 2


def test_saved_ensembles_exclude_the_event_and_have_200_members():
    path = Path("ml/model_manifest.json")
    if not path.exists():
        pytest.skip("Full training has not been run")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for fold in manifest["folds"]:
        assert fold["members"] == 200
        assert fold["heldOutEvent"] not in fold["trainingEvents"]
        assert fold["innerValidationEvent"] in fold["trainingEvents"]
        assert fold["parameters"]["max_depth"] == 3
        assert fold["earlyStoppedRounds"] <= 400
    sites = json.loads(Path("data/processed/site_predictions.json").read_text(encoding="utf-8"))["predictions"]
    assert len(sites) == manifest["sitePredictions"]
    for record in sites:
        assert 0 <= record["ciLow"] <= record["pHit"] <= record["ciHigh"] <= 1
        assert sum(s["value"] for s in record["shap"]) + record["shapBaseValue"] == pytest.approx(record["shapMeanRawScore"])
