import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.model_selection import CANDIDATES, FittedCandidate, choose_candidate
from ml.features import NUMERIC


def synthetic_events(count=6):
    rows = []
    for event in range(count):
        for i in range(8):
            rows.append({"eventId": f"event-{event}", "companyId": f"c-{event}-{i}", "hit": int(i >= 4),
                         "part_type": "sensor", **{name: float(i + event) for name in NUMERIC}})
    return pd.DataFrame(rows)


def test_inner_loop_fits_five_events_and_ties_follow_the_frozen_rule():
    training = synthetic_events()
    calls = []
    class Fake:
        def __init__(self, kind, frame):
            self.training_events = sorted(frame.eventId.unique())
            assert len(self.training_events) == 5
            calls.append((kind, set(self.training_events)))
        def predict(self, frame):
            assert not set(frame.eventId) & set(self.training_events)
            value = frame["distance_km"].to_numpy()
            return (value - value.min()) / (value.max() - value.min())
    selected, means, folds = choose_candidate(training, fit_factory=Fake)
    assert selected == "distance" and len(calls) == 18 and len(folds) == 6
    assert means == dict.fromkeys(CANDIDATES, 1.)
    with pytest.raises(ValueError, match="exactly six"):
        choose_candidate(synthetic_events(7), fit_factory=Fake)


def test_choice_is_based_on_mean_event_auc_and_not_pooled_company_count():
    training = synthetic_events()
    training["distance"] = np.where(training.hit == 1, .8, .2)
    training["logistic_regression"] = np.where(training.hit == 1, .7, np.tile([.1,.3,.5,.9,.0,.0,.0,.0], 6))
    training["lightgbm"] = .5
    large = pd.concat([training[training.eventId == "event-5"]] * 20, ignore_index=True)
    large["distance"] = np.where(large.hit == 1, .2, .8)
    large["logistic_regression"] = np.where(large.hit == 1, .8, .2)
    training = pd.concat([training[training.eventId != "event-5"], large], ignore_index=True)
    class Fake:
        def __init__(self, kind, frame):
            self.kind, self.training_events = kind, sorted(frame.eventId.unique())
        def predict(self, frame):
            return frame[self.kind].to_numpy()
    selected, means, _ = choose_candidate(training, fit_factory=Fake)
    assert selected == "distance"
    assert means == {"distance": pytest.approx(5/6), "logistic_regression": pytest.approx((5*.75+1)/6), "lightgbm": .5}


@pytest.mark.parametrize("kind", ["distance", "logistic_regression", "lightgbm"])
def test_candidate_explanations_reconstruct_the_actual_refit_score(kind):
    training = synthetic_events()
    training.loc[0, "size"] = np.nan
    prediction = synthetic_events(1).iloc[:4].copy()
    prediction.loc[0, "size"] = np.nan
    model = FittedCandidate(kind, training, rounds=2 if kind == "lightgbm" else None)
    base, phi, raw, method = model.explain(prediction)
    assert np.allclose(base + sum(phi.values()), raw)
    assert np.allclose(1 / (1 + np.exp(-raw)), model.predict(prediction))
    assert method


def test_saved_selection_never_uses_outer_labels_and_exports_the_modal_candidate():
    path = Path("data/processed/metrics.json")
    metrics = json.loads(path.read_text(encoding="utf-8"))
    if "modelSelection" not in metrics:
        pytest.skip("Frozen selector has not run yet")
    selection = metrics["modelSelection"]
    assert len(selection["outerFolds"]) == 7
    counts = dict.fromkeys(CANDIDATES, 0)
    for fold in selection["outerFolds"]:
        counts[fold["selectedModel"]] += 1
        assert len(fold["trainingEvents"]) == 6 and fold["eventId"] not in fold["trainingEvents"]
        assert len(fold["innerFolds"]) == 6
        for inner in fold["innerFolds"]:
            assert len(inner["trainingEvents"]) == 5
            assert inner["heldOutEvent"] not in inner["trainingEvents"]
            assert fold["eventId"] not in inner["trainingEvents"]
        expected = max(fold["innerMeanAuc"].values())
        assert fold["innerMeanAuc"][fold["selectedModel"]] == pytest.approx(expected)
    assert counts == selection["selectionCounts"] and sum(counts.values()) == 7
    assert counts[metrics["model"]] == max(counts.values())
