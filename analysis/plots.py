"""Charts for the geo-incrementality case study."""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd

plt.rcParams.update({
    "font.size": 11, "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linestyle": "--",
    "figure.dpi": 150,
})
NAVY, BLUE, GRAY, RED, GREEN = "#1f3a5f", "#3a7bd5", "#9aa0a6", "#c0392b", "#1e8449"
SRC = "Simulated data \u2014 Everline Foods geo-experiment"
N_PRE, TEST_START, TEST_END = 52, 53, 60


def shade_test(ax):
    ax.axvspan(TEST_START - 0.5, TEST_END + 0.5, color=BLUE, alpha=0.08)
    ax.text(56.5, ax.get_ylim()[1] * 0.97, "test window", ha="center",
            va="top", fontsize=9, color=BLUE)


def finalize(fig, ax, title, fname, note=SRC):
    ax.set_title(title, loc="left", pad=12)
    fig.text(0.01, 0.005, note, fontsize=8, color="gray")
    fig.tight_layout(rect=[0, 0.03, 1, 1])
    fig.savefig(f"charts/{fname}", bbox_inches="tight")
    plt.close(fig)
    print("wrote", fname)


def p01_parallel_trends():
    obs = pd.read_csv("data/geo_weekly_sales.csv")
    pairs = pd.read_csv("data/market_matches.csv")
    d = obs[obs["week"] <= TEST_END].copy()
    base = d[d["week"].between(N_PRE - 3, N_PRE)].groupby("geo_id")["sales"].mean()
    d["indexed"] = d["sales"] / d["geo_id"].map(base) * 100
    d["group"] = np.where(d["geo_id"].isin(pairs["treated_geo"]), "Test", "Control")
    g = d.groupby(["week", "group"])["indexed"].mean().unstack()
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(g.index, g["Test"], color=NAVY, lw=2.2, label="Test geos (avg)")
    ax.plot(g.index, g["Control"], color=GRAY, lw=2.2, label="Control geos (avg)")
    shade_test(ax)
    ax.set_ylabel("Indexed sales (wk 49-52 = 100)")
    ax.set_xlabel("Week")
    ax.legend(frameon=False)
    finalize(fig, ax, "Parallel trends hold pre-test; test geos diverge in the test window",
             "01_parallel_trends.png")


def p02_event_study():
    es = pd.read_csv("data/event_study.csv")
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axhline(0, color="black", lw=1)
    ax.fill_between(es["week"], es["ci_lo"] * 100, es["ci_hi"] * 100,
                    color=BLUE, alpha=0.2)
    ax.plot(es["week"], es["delta"] * 100, color=NAVY, lw=2, marker="o", ms=4)
    shade_test(ax)
    ax.set_ylabel("Weekly lift vs week 52 (%)")
    ax.set_xlabel("Week")
    finalize(fig, ax, "Event study: no pre-trend, lift appears exactly in the test window",
             "02_event_study.png")


def p03_lift_estimate():
    s = pd.read_csv("data/results_summary.csv")
    main = s.iloc[0]
    plac = s.iloc[1]
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.axvline(8.0, color=RED, ls="--", lw=1.5, label="True lift (8%, known: simulated)")
    for i, (row, label, col) in enumerate([
            (main, "DiD estimate", NAVY), (plac, "Placebo (pre-period)", GRAY)]):
        ax.errorbar(row["delta_pct"], i, xerr=[[row["delta_pct"] - row["ci_lo_pct"]],
                                               [row["ci_hi_pct"] - row["delta_pct"]]],
                    fmt="o", color=col, capsize=6, ms=8, lw=2)
        ax.text(row["ci_hi_pct"] + 0.3, i,
                f"{row['delta_pct']:.1f}%  [{row['ci_lo_pct']:.1f}, {row['ci_hi_pct']:.1f}]",
                va="center", fontsize=10)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["DiD estimate", "Placebo (pre-period)"])
    ax.set_xlabel("Lift (%) with 95% CI")
    ax.legend(frameon=False, loc="upper left")
    ax.set_xlim(-7, 16)
    finalize(fig, ax, "Recovered lift vs known truth (calibration check)",
             "03_lift_estimate.png")


def p04_placebo_distribution():
    perm = pd.read_csv("data/placebo_permutation.csv")["perm_delta_logpts"] * 100
    with open("data/analysis_summary.json") as f:
        summ = json.load(f)
    obs = summ["did_lift_pct"]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(perm, bins=30, color=GRAY, alpha=0.7, edgecolor="white")
    ax.axvline(obs, color=NAVY, lw=2.5, label=f"Observed: {obs:.1f}%")
    ax.axvline(-obs, color=NAVY, lw=1.5, ls=":")
    ax.set_xlabel("Fake-treatment lift (%)")
    ax.set_ylabel("Count of 500 permutations")
    ax.legend(frameon=False)
    ax.text(0.98, 0.95, f"permutation p = {summ['permutation_p']:.3f}",
            transform=ax.transAxes, ha="right", va="top", fontsize=11,
            bbox=dict(boxstyle="round", fc="white", ec="gray"))
    finalize(fig, ax, "Permutation placebo: the observed lift is not random noise",
             "04_placebo_distribution.png",
             note=SRC + " \u2014 500 random reassignments of treatment across 50 geos")


def p05_power_curve():
    curve = pd.read_csv("data/power_curve.csv")
    with open("data/design_summary.json") as f:
        d = json.load(f)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(curve["true_lift_pct"], curve["power"], color=NAVY, lw=2.5, marker="o")
    ax.axhline(0.8, color=RED, ls="--", lw=1.2, label="80% power")
    if d["mde_80_pct"]:
        ax.axvline(d["mde_80_pct"], color=RED, ls=":", lw=1.2)
        ax.text(d["mde_80_pct"] + 0.2, 0.35,
                f"MDE(80%) = {d['mde_80_pct']:.1f}%",
                color=RED, fontsize=11)
    ax.scatter([8.0], [d["power_at_true_lift"]], color=GREEN, s=90, zorder=5,
               label=f"True lift 8% \u2192 power {d['power_at_true_lift']:.0%}")
    ax.set_xlabel("True lift (%)")
    ax.set_ylabel("Power (share significant at 5%)")
    ax.set_ylim(0, 1.03)
    ax.legend(frameon=False)
    finalize(fig, ax, "Power analysis: the design detects lifts well below the true 8%",
             "05_power_curve.png",
             note=SRC + " \u2014 200 simulated experiments per lift level")


def p06_match_quality():
    base = pd.read_csv("data/_base_panel.csv")
    pairs = pd.read_csv("data/market_matches.csv")
    pre = base[base["period"] == "pre"].copy()
    pre["indexed"] = pre["sales"] / pre.groupby("geo_id")["sales"].transform("mean")
    wide = pre.pivot(index="week", columns="geo_id", values="indexed")
    smooth = wide.rolling(4).mean().dropna()   # same basis the matches were made on
    corr = smooth.corr()
    treated = pairs["treated_geo"].tolist()
    matched = dict(zip(pairs["treated_geo"], pairs["control_geo"]))
    candidates = [g for g in corr.columns if g not in treated]  # all non-test geos
    # keep the 40 non-test geos as candidate columns (all of them here)
    mat = corr.loc[treated, candidates]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    im = ax.imshow(mat.values, cmap="Blues", vmin=0.5, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(candidates)))
    ax.set_xticklabels(candidates, rotation=90, fontsize=7)
    ax.set_yticks(range(len(treated)))
    ax.set_yticklabels(treated, fontsize=9)
    ax.set_xlabel("Candidate control geos")
    ax.set_ylabel("Test geos")
    # outline chosen matches
    for i, t in enumerate(treated):
        j = candidates.index(matched[t])
        ax.add_patch(patches.Rectangle((j - 0.5, i - 0.5), 1, 1,
                                       fill=False, edgecolor=RED, lw=2))
    fig.colorbar(im, ax=ax, label="Pre-period correlation (4-wk smoothed indexed sales)")
    finalize(fig, ax, "Matched markets: each test geo paired with its closest control "
                      "(red boxes)",
             "06_match_quality.png")


if __name__ == "__main__":
    p01_parallel_trends()
    p02_event_study()
    p03_lift_estimate()
    p04_placebo_distribution()
    p05_power_curve()
    p06_match_quality()
