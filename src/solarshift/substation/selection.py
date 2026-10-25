"""Stage 1: choose which substations to model, and flag odd days (unsupervised ML).

Plain-language steps
  1. Coverage rule: keep substations with >=90% valid half-hours in training only.
  2. Shape clustering (k-means): describe each substation by its average WEEKDAY and WEEKEND
     daily shape in the TRAINING period, each scaled by its own mean (so size does not matter).
     Pick k by silhouette score. Label clusters as residential-like if the shape has an evening
     peak bigger than the midday level and a weekend that is not much lower than weekdays
     (commercial/CBD sites drop sharply at weekends).
  3. Anomaly days (Isolation Forest): per substation-day features that reveal switching
     (load suddenly moved to/from a neighbour) or metering faults. Flagged days get weight 0 in
     training; they are kept (and reported separately) in validation/test.
Everything is fitted on TRAINING data only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.metrics import silhouette_score

from . import config


def _in_split(long, name):
    a, b = config.SPLITS[name]
    return (long["date"] >= pd.Timestamp(a)) & (long["date"] <= pd.Timestamp(b))


def shape_vectors(long: pd.DataFrame, subs) -> pd.DataFrame:
    tr = long[_in_split(long, "train") & long["substation"].isin(subs)].copy()
    tr["weekend"] = tr["date"].dt.dayofweek >= 5
    prof = tr.groupby(["substation", "weekend", "hh"])["mw"].mean().unstack("hh")
    mean_level = tr.groupby("substation")["mw"].mean()
    prof = prof.div(mean_level, axis=0, level="substation")
    wd = prof.xs(False, level="weekend").add_prefix("wd_")
    we = prof.xs(True, level="weekend").add_prefix("we_")
    return wd.join(we).dropna()


def cluster_shapes(S: pd.DataFrame, k_range=range(2, 9)):
    scores = {}
    for k in k_range:
        km = KMeans(n_clusters=k, n_init=20, random_state=config.SEED).fit(S)
        scores[k] = silhouette_score(S, km.labels_)
    k_best = max(scores, key=scores.get)
    km = KMeans(n_clusters=k_best, n_init=20, random_state=config.SEED).fit(S)
    return km, k_best, scores


def describe_clusters(S: pd.DataFrame, labels) -> pd.DataFrame:
    wd = S.filter(like="wd_").to_numpy(); we = S.filter(like="we_").to_numpy()
    df = pd.DataFrame({
        "cluster": labels,
        "evening_peak": wd[:, config.EVENING_HH].mean(1),        # 4-9 pm, relative to daily mean
        "midday": wd[:, 20:30].mean(1),                          # 10 am - 3 pm
        "weekend_ratio": we.mean(1) / wd.mean(1),
    }, index=S.index)
    summ = df.groupby("cluster").agg(n=("evening_peak", "size"), evening_peak=("evening_peak", "mean"),
                                     midday=("midday", "mean"), weekend_ratio=("weekend_ratio", "mean"))
    summ["residential_like"] = (summ["evening_peak"] > summ["midday"]) & (summ["weekend_ratio"] > 0.85)
    return df, summ


def anomaly_days(long: pd.DataFrame, subs, contamination=0.01) -> pd.DataFrame:
    """Isolation Forest on per substation-day features, fitted on training days only."""
    d = long[long["substation"].isin(subs)].copy()
    daily = d.groupby(["substation", "date"])["mw"].agg(["mean", "max", "min", "count"])
    daily = daily[daily["count"] >= 40].copy()
    g = daily.groupby(level="substation")["mean"]
    # level vs the substation's own rolling 28-day median of PAST days (shift first = no look-ahead)
    roll = g.transform(lambda s: s.shift(1).rolling(28, min_periods=7).median())
    daily["level_ratio"] = np.log(daily["mean"].clip(lower=1e-3) / roll.clip(lower=1e-3))
    step = d.groupby(["substation", "date"])["mw"].apply(lambda s: s.diff().abs().max())
    # scale the biggest half-hour jump by the substation's typical (past) level, NOT the day's mean:
    # growing rooftop solar shrinks daily means and would make normal days look odd.
    daily["max_step_ratio"] = step.reindex(daily.index) / roll.abs().clip(lower=1e-3)
    # NOTE: we deliberately do NOT use peak/trough ratios. We tried them: they flagged 10% of
    # test-year days vs 1% of training days because midday troughs turned NEGATIVE (reverse power
    # flow from rooftop solar). That is real structural change, not a fault.
    F = daily[["level_ratio", "max_step_ratio"]].replace([np.inf, -np.inf], np.nan).dropna()
    dates = F.index.get_level_values("date")
    tr = (dates >= pd.Timestamp(config.SPLITS["train"][0])) & (dates <= pd.Timestamp(config.SPLITS["train"][1]))
    iso = IsolationForest(n_estimators=300, contamination=contamination, random_state=config.SEED).fit(F[tr])
    out = F.copy()
    out["anomaly_score"] = -iso.score_samples(F)
    out["anomaly"] = iso.predict(F) == -1
    return out.reset_index()
