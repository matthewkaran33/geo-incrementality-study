"""Diff-in-diff helpers: two-way (geo + week) fixed effects with SEs clustered by geo.

Implemented directly with numpy -- no statsmodels dependency. CRV1-style
clustered variance with a G/(G-1) small-sample correction, p-values from a
t distribution with G-1 degrees of freedom (conservative with few clusters).
"""
import numpy as np
import pandas as pd
from scipy import stats


def _demean(s, geo, week):
    return (
        s - s.groupby(geo).transform("mean")
        - s.groupby(week).transform("mean") + s.mean()
    )


def did_estimate(df, treated_geos, post_weeks, value_col="sales",
                 geo_col="geo_id", week_col="week"):
    """Single-coefficient DiD. Returns dict with estimate (log points), SE, CI, p."""
    d = df.copy()
    d["y"] = np.log(d[value_col])
    d["D"] = (
        d[geo_col].isin(set(treated_geos)) & d[week_col].isin(set(post_weeks))
    ).astype(float)
    yt = _demean(d["y"], d[geo_col], d[week_col])
    Dt = _demean(d["D"], d[geo_col], d[week_col])
    XtX = float((Dt * Dt).sum())
    delta = float((Dt * yt).sum() / XtX)
    resid = yt - delta * Dt
    scores = (Dt * resid).groupby(d[geo_col]).sum()   # per-cluster scores
    G = scores.shape[0]
    meat = float((scores ** 2).sum())
    var = (G / (G - 1)) * meat / XtX ** 2
    se = float(np.sqrt(var))
    t = delta / se
    crit = stats.t.ppf(0.975, df=G - 1)
    return dict(
        delta=delta, se=se,
        ci_lo=delta - crit * se, ci_hi=delta + crit * se,
        t=t, p=float(2 * stats.t.sf(abs(t), df=G - 1)),
        n_clusters=G, n_obs=len(d),
    )


def event_study(df, treated_geos, weeks, ref_week, value_col="sales",
                geo_col="geo_id", week_col="week"):
    """Per-week treatment coefficients (reference week omitted). Clustered SEs."""
    weeks = list(weeks)
    d = df[df[week_col].isin(weeks)].copy()
    d["y"] = np.log(d[value_col])
    d["tr"] = d[geo_col].isin(set(treated_geos)).astype(float)
    cols = []
    for w in weeks:
        if w == ref_week:
            continue
        c = f"D_{w}"
        d[c] = d["tr"] * (d[week_col] == w).astype(float)
        cols.append(c)
    geo = d[geo_col].values
    wk = d[week_col].values
    Y = _demean(d["y"], d[geo_col], d[week_col]).values
    X = np.column_stack([_demean(d[c], d[geo_col], d[week_col]).values for c in cols])
    beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
    resid = Y - X @ beta
    XtX_inv = np.linalg.inv(X.T @ X)
    # cluster meat: sum over geos of (X_g' e_g)(X_g' e_g)'
    meat = np.zeros((len(cols), len(cols)))
    for g in np.unique(geo):
        m = geo == g
        s = X[m].T @ resid[m]
        meat += np.outer(s, s)
    G = len(np.unique(geo))
    V = (G / (G - 1)) * XtX_inv @ meat @ XtX_inv
    se = np.sqrt(np.diag(V))
    crit = stats.t.ppf(0.975, df=G - 1)
    out = pd.DataFrame({
        "week": [int(c.split("_")[1]) for c in cols],
        "delta": beta, "se": se,
    })
    out["ci_lo"] = out["delta"] - crit * out["se"]
    out["ci_hi"] = out["delta"] + crit * out["se"]
    return out.sort_values("week").reset_index(drop=True)
