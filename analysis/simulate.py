"""Simulate geo-weekly sales for the Everline Foods geo-experiment.

All data are SIMULATED. This script generates *untreated potential outcomes* for
50 geos x 78 weeks (52 pre + 8 test + 18 post). The treatment effect is applied
later by analyze.py, so the design step (matching, power analysis) only ever
sees pre-period data -- the same information a real analyst would have.

DGP (in log space):
    log sales = geo baseline + geo trend + annual seasonality
                + promo bump + common demand shock + noise
"""
import json

import numpy as np
import pandas as pd

SEED = 42
N_GEO = 50
N_PRE, N_TEST, N_POST = 52, 8, 18
N_WEEKS = N_PRE + N_TEST + N_POST
TEST_START = N_PRE + 1          # week 53
TEST_END = N_PRE + N_TEST        # week 60
TRUE_LIFT = 0.08                # baked-in true lift on treated geos, test weeks

GEOS = [f"G{i:02d}" for i in range(1, N_GEO + 1)]
WEEKS = np.arange(1, N_WEEKS + 1)


def draw_params(seed=SEED):
    """Time-invariant geo characteristics (fixed across power-sim draws)."""
    rng = np.random.default_rng(seed)
    return dict(
        log_base=rng.normal(11.7, 0.8, N_GEO),        # median ~$120k/week/geo
        trend=rng.normal(0.001, 0.0008, N_GEO),       # ~0.1%/week drift
        season_amp=np.abs(rng.normal(0.15, 0.03, N_GEO)),
        season_phase=rng.normal(0, 1.5, N_GEO),
        promo=(rng.random((N_GEO, N_WEEKS)) < 0.08).astype(int),
    )


def generate_panel(params, noise_seed, lift=TRUE_LIFT, treated=None):
    """Build a geo-week panel. `treated` is a set of geo_ids getting `lift`
    (as a fraction) during the test window; None means no treatment."""
    rng = np.random.default_rng(noise_seed)
    treated = set(treated or [])
    log_sales = np.zeros((N_GEO, N_WEEKS))
    for g in range(N_GEO):
        seas = params["season_amp"][g] * np.sin(
            2 * np.pi * (WEEKS + params["season_phase"][g]) / 52
        )
        lp = (
            params["log_base"][g]
            + params["trend"][g] * WEEKS
            + seas
            + params["promo"][g] * np.log(1.30)   # promo weeks: +30% sales
        )
        # common demand shock mid-test (a time fixed effect absorbs this in DiD)
        lp = lp + np.where((WEEKS == 55) | (WEEKS == 56), np.log(1.04), 0.0)
        lp = lp + rng.normal(0, 0.05, N_WEEKS)    # idiosyncratic noise
        if GEOS[g] in treated:
            lp = lp + np.where(
                (WEEKS >= TEST_START) & (WEEKS <= TEST_END), np.log(1 + lift), 0.0
            )
        log_sales[g] = lp
    df = pd.DataFrame({
        "geo_id": np.repeat(GEOS, N_WEEKS),
        "week": np.tile(WEEKS, N_GEO),
        "promo": params["promo"].ravel(),
        "sales": np.exp(log_sales).ravel(),
    })
    df["period"] = pd.cut(
        df["week"],
        bins=[0, N_PRE, N_PRE + N_TEST, N_WEEKS],
        labels=["pre", "test", "post"],
    ).astype(str)
    return df


def main():
    params = draw_params()
    base = generate_panel(params, noise_seed=SEED, lift=0.0, treated=None)
    base.to_csv("data/_base_panel.csv", index=False)   # intermediate, gitignored
    np.savez(
        "data/_dgp_params.npz",
        log_base=params["log_base"], trend=params["trend"],
        season_amp=params["season_amp"], season_phase=params["season_phase"],
        promo=params["promo"],
    )
    truth = {
        "simulated": True,
        "brand": "Everline Foods (fictional)",
        "n_geos": N_GEO,
        "n_pre_weeks": N_PRE, "n_test_weeks": N_TEST, "n_post_weeks": N_POST,
        "true_lift_pct": round(TRUE_LIFT * 100, 2),
        "true_lift_logpts": round(float(np.log(1 + TRUE_LIFT)), 5),
        "test_weeks": [int(TEST_START), int(TEST_END)],
        "notes": "Treatment effect applies to treated geos only, test weeks only. "
                 "All sales figures are simulated.",
    }
    with open("data/truth.json", "w") as f:
        json.dump(truth, f, indent=2)
    print(f"base panel: {base.shape}, sales mean ${base.sales.mean():,.0f}")
    print("truth: +8% lift on treated geos, weeks 53-60")


if __name__ == "__main__":
    main()
