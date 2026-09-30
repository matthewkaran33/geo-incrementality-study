"""Validation tests for the estimators in did.py and analyze.py.

Run from the repo root:

    python3 analysis/test_estimators.py

1. The hand-rolled two-way FE DiD in did.py must match statsmodels OLS
   (geo + week dummies, SEs clustered by geo) on the simulated panel.
2. The exact randomization-inference p-value must behave correctly:
   it rejects on data with a real lift baked in, and does not reject
   on data with no treatment effect.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "analysis")
from analyze import randomization_pvalue
from did import did_estimate
from simulate import (draw_params, generate_panel, TEST_START, TEST_END)


def load_matched_panel(lift, noise_seed=42):
    pairs = pd.read_csv("data/market_matches.csv")
    treated = set(pairs["treated_geo"])
    post_weeks = list(range(TEST_START, TEST_END + 1))
    geos20 = pairs["treated_geo"].tolist() + pairs["control_geo"].tolist()
    params = draw_params()
    panel = generate_panel(params, noise_seed=noise_seed, lift=lift,
                           treated=treated)
    panel = panel[panel["week"] <= TEST_END]
    panel20 = panel[panel["geo_id"].isin(geos20)]
    return panel20, pairs, treated, post_weeks


def test_did_matches_statsmodels():
    """did_estimate == OLS with geo+week dummies and geo-clustered SEs."""
    import statsmodels.formula.api as smf

    panel20, pairs, treated, post_weeks = load_matched_panel(lift=0.08)
    mine = did_estimate(panel20, treated, post_weeks)

    d = panel20.copy()
    d["y"] = np.log(d["sales"])
    d["D"] = (d["geo_id"].isin(treated)
              & d["week"].isin(post_weeks)).astype(float)
    G = d["geo_id"].nunique()
    sm = smf.ols("y ~ D + C(geo_id) + C(week)", data=d).fit(
        cov_type="cluster",
        cov_kwds={"groups": d["geo_id"], "use_correction": False})
    # same G/(G-1) small-sample correction did.py applies
    se_sm = float(sm.bse["D"] * np.sqrt(G / (G - 1)))

    assert np.isclose(mine["delta"], sm.params["D"], rtol=1e-8), \
        f"delta mismatch: {mine['delta']} vs {sm.params['D']}"
    assert np.isclose(mine["se"], se_sm, rtol=1e-6), \
        f"SE mismatch: {mine['se']} vs {se_sm}"
    print(f"PASS test_did_matches_statsmodels "
          f"(delta={mine['delta']:.6f}, se={mine['se']:.6f})")


def test_randomization_inference():
    """RI rejects with a real lift, and does not reject with no effect."""
    # with effect: must reject at 5%
    panel20, pairs, treated, post_weeks = load_matched_panel(lift=0.08)
    obs = did_estimate(panel20, treated, post_weeks)["delta"]
    p, stats = randomization_pvalue(panel20, pairs, obs, post_weeks)
    assert len(stats) == 1024, f"expected 1024 assignments, got {len(stats)}"
    assert p < 0.05, f"should reject with real lift, got p={p}"
    print(f"PASS randomization rejects with real lift (p={p:.4f})")

    # without effect: must not reject at 5% (deterministic: fixed seeds)
    panel20, pairs, treated, post_weeks = load_matched_panel(lift=0.0)
    obs0 = did_estimate(panel20, treated, post_weeks)["delta"]
    p0, stats0 = randomization_pvalue(panel20, pairs, obs0, post_weeks)
    assert len(stats0) == 1024
    assert p0 >= 1 / 1024, "actual assignment must be in the enumeration"
    assert p0 > 0.05, f"should not reject with no effect, got p={p0}"
    print(f"PASS randomization does not reject with no effect (p={p0:.4f})")


if __name__ == "__main__":
    test_did_matches_statsmodels()
    test_randomization_inference()
    print("all tests passed")
