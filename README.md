# Geo-incrementality experiment: does extra streaming weight cause extra sales?

A complete, end-to-end geo-experiment case study for a fictional CPG brand
(**Everline Foods**). Ten test DMAs get incremental streaming-video weight for
8 weeks; ten matched control DMAs don't. Diff-in-diff recovers the lift, and
because **all data are simulated with a known true lift (+8%)**, the analysis
is graded against the truth — the one validation you can never run on real data.

Companion project: [MMM case study](https://github.com/matthewkaran33/mmm-case-study)
— observational modeling on the same fictional brand. This repo is the
experimental half: the "test and learn" behind the model.

## Headline findings

- **Recovered lift: +6.7%** (95% CI +0.7% to +13.0%, p = 0.030) vs a **true lift of +8%** — 1.3 points under, inside the interval. The interval did its job.
- **Placebo checks clean**: fake test window in the pre-period finds nothing (p = 0.80); the observed lift beats 99.8% of 500 random treatment reassignments.
- **Synthetic control agrees**: +6.0% mean lift across test geos.
- **Design was powered**: minimum detectable effect 7.5% at 80% power; 94% power at the true 8% lift.

## Repo map

| Path | What it is |
|---|---|
| `docs/case_study.md` | Full write-up: question, design, power, results, limitations |
| `analysis/simulate.py` | Generates the simulated geo-week panel (known +8% true lift) |
| `analysis/design.py` | Matched-market selection, within-pair randomization, power analysis |
| `analysis/analyze.py` | DiD, event study, placebo tests, synthetic control |
| `analysis/plots.py` | All charts |
| `analysis/did.py` | Two-way FE DiD with geo-clustered SEs (numpy/scipy) |
| `data/` | Tidy simulated CSVs: weekly panel, market matches, results, power curve |
| `charts/` | Six PNGs (see below) |

## Charts

1. `01_parallel_trends.png` — test vs control indexed sales; parallel pre-test, divergence in test window
2. `02_event_study.png` — weekly lift coefficients; no pre-trend, effect starts at week 53
3. `03_lift_estimate.png` — recovered +6.7% vs true 8%, with the clean placebo beside it
4. `04_placebo_distribution.png` — 500 permutations; observed lift is not noise (p = 0.002)
5. `05_power_curve.png` — power vs true lift; MDE(80%) = 7.5%
6. `06_match_quality.png` — pre-period similarity heatmap with chosen pairs marked

## Reproduce it

```bash
./run_all.sh
```

Requires Python 3 with numpy, pandas, matplotlib, scipy. Fixed seeds — the
numbers above regenerate exactly.

## Data note

Everything under `data/` is **simulated**. `data/truth.json` records the
baked-in true lift. No real markets, no real sales, no real people.
