"""Estimate the test effect: DiD, placebo checks, synthetic-control robustness.

Builds the *observed* panel by applying the baked-in true lift to treated geos
in the test window, then runs the full analysis battery.
"""
import json
import sys

import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, "analysis")
from did import did_estimate, event_study
from simulate import TRUE_LIFT, TEST_START, TEST_END, N_PRE


def randomization_pvalue(panel20, pairs, observed_delta, post_weeks):
    """Exact Fisher randomization inference over all 2^10 within-pair
    treatment assignments -- the experiment's actual assignment mechanism.

    Under the sharp null of no treatment effect, the observed panel is the
    untreated panel, so re-running the DiD estimator under every possible
    within-pair assignment gives the exact null distribution of the test
    statistic. Returns (p_value, array of 1,024 statistics).
    """
    pair_list = list(pairs[["treated_geo", "control_geo"]]
                     .itertuples(index=False, name=None))
    stats = np.empty(1 << len(pair_list))
    for mask in range(1 << len(pair_list)):
        fake = {a if (mask >> i) & 1 else b
                for i, (a, b) in enumerate(pair_list)}
        stats[mask] = did_estimate(panel20, fake, post_weeks)["delta"]
    p = float((np.abs(stats) >= abs(observed_delta)).mean())
    return p, stats


def load_observed():
    base = pd.read_csv("data/_base_panel.csv")
    pairs = pd.read_csv("data/market_matches.csv")
    treated = set(pairs["treated_geo"])
    obs = base.copy()
    mask = obs["geo_id"].isin(treated) & obs["week"].between(TEST_START, TEST_END)
    obs.loc[mask, "sales"] = obs.loc[mask, "sales"] * (1 + TRUE_LIFT)
    obs["treated"] = obs["geo_id"].isin(treated).astype(int)
    obs["post"] = (obs["week"] >= TEST_START).astype(int)
    obs.to_csv("data/geo_weekly_sales.csv", index=False)
    return obs, pairs, treated


def synth_control_weights(y_treated_pre, Y_donor_pre):
    """Non-negative weights summing to 1 minimizing pre-period MSE (SLSQP)."""
    n = Y_donor_pre.shape[1]
    w0 = np.full(n, 1 / n)
    res = minimize(
        lambda w: float(((y_treated_pre - Y_donor_pre @ w) ** 2).mean()),
        w0, method="SLSQP",
        bounds=[(0, 1)] * n,
        constraints={"type": "eq", "fun": lambda w: w.sum() - 1},
        options={"maxiter": 500, "ftol": 1e-10},
    )
    return res.x


def main():
    obs, pairs, treated = load_observed()
    geos20 = pairs["treated_geo"].tolist() + pairs["control_geo"].tolist()
    post_weeks = list(range(TEST_START, TEST_END + 1))
    panel = obs[obs["week"] <= TEST_END]
    panel20 = panel[panel["geo_id"].isin(geos20)]

    results = []

    # 1. main DiD
    r = did_estimate(panel20, treated, post_weeks)
    r.update({"estimator": "DiD (geo+week FE, clustered SE)",
              "window": f"weeks 1-{TEST_END}"})
    results.append(r)
    print(f"main DiD: delta={r['delta']:.4f} log-pts "
          f"({(np.exp(r['delta']) - 1) * 100:.2f}%), "
          f"95% CI [{(np.exp(r['ci_lo']) - 1) * 100:.2f}, "
          f"{(np.exp(r['ci_hi']) - 1) * 100:.2f}], p={r['p']:.4f}")

    # 2. placebo in time: fake 8-week "test" at the end of the pre-period
    fake_post = list(range(N_PRE - 7, N_PRE + 1))
    pre_only = panel20[panel20["week"] <= N_PRE]
    rp = did_estimate(pre_only, treated, fake_post)
    rp.update({"estimator": "Placebo (fake test in pre-period)",
               "window": f"weeks 1-{N_PRE}"})
    results.append(rp)
    print(f"placebo-in-time: delta={rp['delta']:.4f} (p={rp['p']:.3f})")

    # 3. event study (weekly coefficients, ref = last pre week)
    es = event_study(panel20, treated, list(range(41, TEST_END + 1)), ref_week=N_PRE)
    es.to_csv("data/event_study.csv", index=False)

    # 4. exact randomization inference: all 2^10 within-pair assignments
    ri_p, ri_stats = randomization_pvalue(panel20, pairs, r["delta"],
                                          post_weeks)
    pd.DataFrame({"ri_delta_logpts": ri_stats}).to_csv(
        "data/placebo_permutation.csv", index=False)
    print(f"randomization inference: p={ri_p:.4f} "
          f"(|reassigned| >= |observed| over {len(ri_stats)} assignments)")

    # 5. synthetic control per treated geo (donors = 10 control geos)
    controls = pairs["control_geo"].tolist()
    pre_weeks = list(range(1, N_PRE + 1))
    sc_rows = []
    for _, row in pairs.iterrows():
        t = row["treated_geo"]
        y_pre = np.log(obs[(obs["geo_id"] == t) & obs["week"].isin(pre_weeks)]
                       .sort_values("week")["sales"].values)
        Y_pre = np.column_stack([
            np.log(obs[(obs["geo_id"] == c) & obs["week"].isin(pre_weeks)]
                   .sort_values("week")["sales"].values) for c in controls
        ])
        w = synth_control_weights(y_pre, Y_pre)
        y_test = np.log(obs[(obs["geo_id"] == t) & obs["week"].isin(post_weeks)]
                        .sort_values("week")["sales"].values)
        Y_test = np.column_stack([
            np.log(obs[(obs["geo_id"] == c) & obs["week"].isin(post_weeks)]
                   .sort_values("week")["sales"].values) for c in controls
        ])
        gap = float(np.mean(y_test - Y_test @ w))
        sc_rows.append({"treated_geo": t, "sc_lift_logpts": round(gap, 5),
                        "sc_lift_pct": round((np.exp(gap) - 1) * 100, 2)})
    sc = pd.DataFrame(sc_rows)
    sc.to_csv("data/synth_control.csv", index=False)
    print(f"synthetic control: mean lift "
          f"{(np.exp(sc['sc_lift_logpts'].mean()) - 1) * 100:.2f}% "
          f"across {len(sc)} treated geos")

    # 6. pair-level DiD (heterogeneity, point estimates)
    pair_rows = []
    for _, row in pairs.iterrows():
        sub = panel[panel["geo_id"].isin([row["treated_geo"], row["control_geo"]])]
        rk = did_estimate(sub, [row["treated_geo"]], post_weeks)
        pair_rows.append({"pair_id": row["pair_id"], "treated_geo": row["treated_geo"],
                          "pair_lift_pct": round((np.exp(rk["delta"]) - 1) * 100, 2)})

    # results summary
    summ = pd.DataFrame(results)
    for c in ["delta", "se", "ci_lo", "ci_hi"]:
        summ[c + "_pct"] = (np.exp(summ[c]) - 1) * 100
    summ["true_lift_pct"] = TRUE_LIFT * 100
    summ.to_csv("data/results_summary.csv", index=False)
    pd.DataFrame(pair_rows).to_csv("data/pair_lifts.csv", index=False)

    with open("data/analysis_summary.json", "w") as f:
        json.dump({
            "did_lift_pct": round(float((np.exp(r["delta"]) - 1) * 100), 2),
            "did_ci_pct": [round(float((np.exp(r["ci_lo"]) - 1) * 100), 2),
                           round(float((np.exp(r["ci_hi"]) - 1) * 100), 2)],
            "did_p": round(float(r["p"]), 4),
            "true_lift_pct": TRUE_LIFT * 100,
            "placebo_in_time_delta": round(float(rp["delta"]), 5),
            "placebo_in_time_p": round(float(rp["p"]), 4),
            "randomization_p": round(ri_p, 4),
            "randomization_n_assignments": int(len(ri_stats)),
            "synth_control_mean_lift_pct": round(
                float((np.exp(sc["sc_lift_logpts"].mean()) - 1) * 100), 2),
        }, f, indent=2)
    print("wrote data/geo_weekly_sales.csv + results")


if __name__ == "__main__":
    main()
