import numpy as np
import pandas as pd
import pytest
from ml.evaluation import auc_intervals, pair_decomposition


def test_bootstrap_resamples_companies_and_preserves_perfect_ranking_and_ties():
    frame = pd.DataFrame({"companyId": list("abcd"), "hit": [0,0,1,1], "perfect": [.1,.2,.8,.9], "tied": [.5]*4})
    result = auc_intervals(frame, {"perfect": "perfect", "tied": "tied"}, draws=100)
    assert result == {"perfect": [1.,1.], "tied": [.5,.5]}
    with pytest.raises(ValueError, match="one row per company"):
        auc_intervals(pd.concat([frame, frame.iloc[:1]]), {"perfect": "perfect"})
    with pytest.raises(ValueError, match="both outcome classes"):
        auc_intervals(frame.iloc[:2], {"perfect": "perfect"})


def test_pair_decomposition_explains_cross_event_probability_scale_distortion():
    # Each event ranks its own hit correctly, but event B's baseline is lower.
    frame = pd.DataFrame({"eventId": ["a","a","b","b"], "hit": [0,1,0,1], "pHit": [.8,.9,.1,.2]})
    result = pair_decomposition(frame)
    assert result["withinEventAuc"] == 1 and result["crossEventAuc"] == .5
    assert result["pooledAuc"] == .75 and result["crossEventPairShare"] == .5
