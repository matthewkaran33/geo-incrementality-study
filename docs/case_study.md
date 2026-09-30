# Measuring incrementality with a geo-experiment: a case study

**All data in this project are simulated.** The brand ("Everline Foods") is fictional.
The point of the simulation is that the true lift is *known*, so the analysis
can be graded against it — something you can never do with real data.

## The question

Everline Foods is considering adding streaming-video weight nationally and wants
to know one thing: does the extra spend actually cause extra sales, or would
those sales have happened anyway? A marketing mix model can estimate this from
history (see my companion [MMM case study](https://github.com/matthewkaran33/mmm-case-study)),
but MMM is observational — it can be fooled by anything that moves with spend.
A geo-experiment answers the question causally: spend more in some markets,
hold others back, and compare.

## Why geo-experiments — and what they can't do

Geo-experiments are the closest thing media measurement has to a randomized
trial. They handle the problems that keep MMM honest people up at night:
unobserved confounders, spend that follows expected demand, promotions that
coincide with flights.

Their limits are real too. They measure the *marginal* increment of the tested
weight, not the average effectiveness of the channel. They take weeks and cost
real money. They assume no spillover between test and control markets (no
national spill from a streaming buy is a reasonable assumption; it would not
be for a national TV flight). And eight weeks tells you nothing about
long-run or lagged effects. I treat geo-testing and MMM as complements, not
rivals: the experiment calibrates the model, the model generalizes the
experiment.

## Test design

- **50 geos**, 78 weeks of weekly sales each: 52 pre-period, 8 test, 18 post.
- The **largest market (G31) was held out** of the test pool — standard practice,
  too much revenue at risk to experiment on.
- From the remaining 49, **10 test geos were drawn at random**, then each was
  paired with its most similar control using optimal (Hungarian) assignment on
  pre-period sales correlations, with a size band of 0.5x–2x. Matching used
  4-week rolling averages so markets pair on trend similarity, not weekly noise.
  Mean pair correlation: **0.92**.
- **Treatment was randomized within pairs** (coin flip), giving 10 test and
  10 control geos.
- Test window: **weeks 53–60**. Test geos received incremental streaming-video
  weight calibrated to a **true lift of +8%** — baked into the simulation so
  the analysis can be checked against it.

The sales data itself has everything that makes real geo data annoying:
annual seasonality, market-specific trends, promo spikes, and a demand shock
hitting all markets mid-test (weeks 55–56). A good design should see through
all of it.

## Power analysis

Before reading results, I checked the design could actually detect the effect.
200 simulated experiments at each lift level, same 10-pair design:

| True lift | Power |
|---|---|
| 0% | 0% |
| 4% | 1% |
| 6% | 39% |
| **8%** | **94%** |
| 10%+ | 100% |

Minimum detectable effect at 80% power: **7.5%**. The design is adequately
powered for the true 8% lift, and would likely miss anything under ~6% — worth
knowing before spending the money, not after.

## Results

Two-way fixed-effects diff-in-diff (geo + week fixed effects, standard errors
clustered by geo):

- **Recovered lift: +6.7%**, 95% CI [+0.7%, +13.0%], p = 0.030.

The honest version: the point estimate came in **1.3 points under the true 8%**.
That's sampling noise, not bias — the 95% interval covers the truth comfortably,
and the estimate is statistically distinguishable from zero. This is exactly
why you report intervals instead of points: the interval did its job.

The event study (chart 02) shows no pre-trend — weekly coefficients hover
around zero through week 52 — and the lift appears exactly when the test
starts. Parallel trends, the one assumption that matters, holds.

## Placebo checks

Two falsification tests, both clean:

1. **Placebo in time**: ran the same DiD on the pre-period with a fake 8-week
   "test" window. Estimated lift: −0.5%, p = 0.80. Nothing there, as expected.
2. **Randomization check**: the experiment randomized treatment within 10
   matched pairs, so the exact null distribution comes from re-running the
   DiD under all 1,024 possible within-pair assignments. The observed +6.7%
   is larger in absolute value than 98.4% of them (p = 0.016).

## Robustness

- **Synthetic control** (one per test geo, donors = the 10 control markets,
  weights constrained non-negative and summing to 1): mean lift **+6.0%** —
  right in line with the DiD estimate.
- **Pair-level estimates** ranged from about +1% to +12% across the 10 pairs.
  That spread is normal with 10 pairs; it's also why nobody should make a
  national decision off a single market pair.

## What it means for the media decision

The test says the streaming-video increment works: roughly +7% sales in
treated markets, causal, surviving every falsification check I ran. If the
incremental spend behind that weight costs less than the margin on ~7% of
8 weeks of sales in those markets, it pays for itself — roll it out, and use
the measured lift to calibrate the always-on MMM rather than replacing it.

What I would *not* claim: that streaming video always returns +7%, that the
effect persists beyond eight weeks, or that doubling the weight doubles the
lift. The test measured one weight, in ten markets, for eight weeks.

## Limitations

- Simulated data: the DGP is realistic but tidier than reality — no
  hurricanes, no competitor conquesting, no supply outages.
- SUTVA assumed: no spillover between test and control geos. Plausible for a
  streaming buy, but untestable here.
- Ten pairs detected a positive average effect, but the 95% interval (+0.7%
  to +13.0%) leaves substantial uncertainty. For a media decision, that
  matters: the test rules out zero or negative lift, but the ROI case looks
  very different at +1% than at +13%. A rollout call has to be made on
  expected value across that range, not on the +6.7% point estimate. Ten
  pairs is also thin for studying *which* markets respond most.
- The common demand shock in weeks 55–56 was absorbed by time fixed effects;
  a shock hitting only test markets would not have been.

## Reproduce it

```bash
pip install -r requirements.txt
./run_all.sh
python3 analysis/test_estimators.py
```

`analysis/simulate.py` → `design.py` → `analyze.py` → `plots.py`.
Seeds are fixed; the numbers above regenerate exactly. The test script
checks the hand-rolled DiD against statsmodels OLS and verifies the
randomization inference rejects with a real lift and not without one.
