"""Test design: matched-market selection, within-pair randomization, power analysis.

Only pre-period data is used here -- the same information available before a
real test launches.
"""
import json
import sys

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, "analysis")
from did import did_estimate
from simulate import (GEOS, N_GEO, N_PRE, N_TEST, TEST_START, TEST_END,
                      draw_params, generate_panel)

MATCH_SEED, RAND_SEED = 7, 11
N_PAIRS = 10
MIN_CORR, SIZE_BAND = 0.80, (0.5, 2.0)


def load_base():
    df = pd.read_csv("data/_base_panel.csv")
    return df[df["period"] == "pre"].copy()


def matched_pairs(pre):
    """Draw candidate test geos, pair each with its most similar control via
    optimal (Hungarian) assignment on pre-period indexed-sales correlation,
    then randomize treatment within pairs. Only pre-period data is used."""
    rng = np.random.default_rng(MATCH_SEED)
    pre = pre.copy()
    pre["indexed"] = pre["sales"] / pre.groupby("geo_id")["sales"].transform("mean")
    wide = pre.pivot(index="week", columns="geo_id", values="indexed")
    # match on 4-week rolling means: pair markets on trend similarity,
    # not on idiosyncratic weekly noise (promo spikes, etc.)
    smooth = wide.rolling(4).mean().dropna()
    corr = smooth.corr()
    size = pre.groupby("geo_id")["sales"].mean()

    # business rule: the single largest market is held out of testing
    # (standard practice -- too much revenue at risk to experiment on)
    holdout = size.idxmax()
    pool = [g for g in GEOS if g != holdout]

    test_candidates = list(rng.choice(pool, size=N_PAIRS, replace=False))
    controls = [g for g in pool if g not in test_candidates]
    cost = np.full((N_PAIRS, len(controls)), 999.0)
    for i, t in enumerate(test_candidates):
        for j, g in enumerate(controls):
            ratio = size[g] / size[t]
            if SIZE_BAND[0] <= ratio <= SIZE_BAND[1]:
                cost[i, j] = -corr.loc[t, g]
    row_ind, col_ind = linear_sum_assignment(cost)
    assert (cost[row_ind, col_ind] < 900).all(), "infeasible match for some test geo"
    raw_pairs = []
    for i, j in zip(row_ind, col_ind):
        t, g = test_candidates[i], controls[j]
        raw_pairs.append((t, g, float(corr.loc[t, g]), float(size[g] / size[t])))
    min_corr = min(p[2] for p in raw_pairs)
    assert min_corr >= MIN_CORR, f"weakest match corr {min_corr:.3f} < {MIN_CORR}"
    # within-pair randomization: coin flip decides which geo is treated
    rrng = np.random.default_rng(RAND_SEED)
    final = []
    for i, (a, b, c, r) in enumerate(raw_pairs, 1):
        treated, control = (a, b) if rrng.random() < 0.5 else (b, a)
        final.append({"pair_id": i, "treated_geo": treated, "control_geo": control,
                      "pre_corr": round(c, 4), "size_ratio": round(r, 3),
                      "holdout_geo": holdout})
    return pd.DataFrame(final), corr


def power_analysis(params, treated_geos, control_geos, lifts, n_draws=200):
    """Simulation-based power: regenerate noise, apply each lift, run DiD."""
    rows = []
    post_weeks = list(range(TEST_START, TEST_END + 1))
    geos20 = list(treated_geos) + list(control_geos)  # DiD runs on matched geos
    for lift in lifts:
        hits = 0
        for k in range(n_draws):
            panel = generate_panel(params, noise_seed=1000 + k,
                                   lift=lift, treated=set(treated_geos))
            panel = panel[panel["week"] <= TEST_END]
            panel = panel[panel["geo_id"].isin(geos20)]
            r = did_estimate(panel, treated_geos, post_weeks)
            hits += r["p"] < 0.05 and r["delta"] > 0
        rows.append({"true_lift_pct": round(lift * 100, 1),
                     "power": round(hits / n_draws, 3)})
        print(f"  lift {lift * 100:4.1f}% -> power {hits / n_draws:.2f}", flush=True)
    return pd.DataFrame(rows)


def main():
    pre = load_base()
    pairs, corr = matched_pairs(pre)
    pairs.to_csv("data/market_matches.csv", index=False)
    treated = pairs["treated_geo"].tolist()
    print(f"{len(pairs)} pairs matched; mean pre-corr "
          f"{pairs['pre_corr'].mean():.3f}")

    params = draw_params()  # fixed geo characteristics; noise redrawn per draw
    print("power analysis (200 draws per lift level):")
    lifts = [0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15]
    curve = power_analysis(params, treated, pairs["control_geo"].tolist(), lifts)
    curve.to_csv("data/power_curve.csv", index=False)
    # MDE at 80% power via linear interpolation
    x = curve["true_lift_pct"].values / 100
    y = curve["power"].values
    mde = float(np.interp(0.8, y, x)) if y.max() >= 0.8 else None
    summary = {
        "n_pairs": N_PAIRS,
        "holdout_geo": pairs["holdout_geo"].iloc[0],
        "holdout_reason": "largest market held out of testing (revenue at risk)",
        "treated_geos": treated,
        "control_geos": pairs["control_geo"].tolist(),
        "mean_pre_corr": round(float(pairs["pre_corr"].mean()), 4),
        "mde_80_pct": round(mde * 100, 2) if mde else None,
        "power_at_true_lift": float(curve.loc[
            curve["true_lift_pct"] == 8.0, "power"].iloc[0]),
        "seeds": {"match": MATCH_SEED, "randomization": RAND_SEED},
    }
    with open("data/design_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"MDE(80%): {summary['mde_80_pct']}%, "
          f"power at true 8% lift: {summary['power_at_true_lift']}")


if __name__ == "__main__":
    main()
