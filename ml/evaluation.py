"""Bootstrap uncertainty for fixed company-level held-out predictions."""
import numpy as np

SEED = 20261015


def auc_intervals(frame, columns, draws=10000, seed=SEED):
    """Stratified company bootstrap conditional on the event's class counts.

    Resampling one event as a cluster cannot estimate its own AUC uncertainty.
    Positives and negatives are therefore resampled separately within that
    event. All candidate columns share exactly the same bootstrap weights.
    This does not refit models or account for correlated firms/market shocks.
    """
    if "companyId" in frame and frame["companyId"].duplicated().any():
        raise ValueError("Per-event bootstrap needs one row per company")
    positive = frame[frame["hit"].astype(int) == 1]
    negative = frame[frame["hit"].astype(int) == 0]
    if positive.empty or negative.empty:
        raise ValueError("AUC bootstrap requires both outcome classes")
    rng = np.random.default_rng(seed)
    m, n = len(positive), len(negative)
    wp = rng.multinomial(m, np.full(m, 1 / m), size=draws)
    wn = rng.multinomial(n, np.full(n, 1 / n), size=draws)
    output = {}
    for name, column in columns.items():
        p, q = positive[column].to_numpy()[:, None], negative[column].to_numpy()[None, :]
        concordance = (p > q).astype(float) + .5 * (p == q)
        values = np.einsum("bi,ij,bj->b", wp, concordance, wn, optimize=True) / (m * n)
        output[name] = np.quantile(values, [.025, .975]).tolist()
    return output


def pair_decomposition(frame, column="pHit"):
    positive, negative = frame[frame.hit == 1], frame[frame.hit == 0]
    p, q = positive[column].to_numpy()[:, None], negative[column].to_numpy()[None, :]
    concordance = (p > q).astype(float) + .5 * (p == q)
    within = positive.eventId.to_numpy()[:, None] == negative.eventId.to_numpy()[None, :]
    return {"withinEventAuc": float(concordance[within].mean()), "crossEventAuc": float(concordance[~within].mean()),
            "crossEventPairShare": float((~within).mean()), "pooledAuc": float(concordance.mean()),
            "withinEventPairs": int(within.sum()), "crossEventPairs": int((~within).sum())}
