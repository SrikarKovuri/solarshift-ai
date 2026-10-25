# Day 5 — peak warnings, pricing and constrained response

Completed 25 October 2026 on the Day 4 substation pivot. Outputs are historical
validation and scenario evidence. No reserved-test scoring, live pricing or device
control was performed. Day 6 remains the integrated dashboard and explanations.

## Executed results

Calibration uses **9,747 site-days from May–October 2023**. Evaluation uses
**7,982 eligible site-days from November 2023–April 2024** (826 peak events).
No probability threshold or model was selected by optimizing this later period.

| Warning rule | Precision | Recall | F1 |
|---|---:|---:|---:|
| Raw quantile risk ≥30% | 63.74% | 78.33% | 0.7029 |
| Calibrated risk ≥30% | 62.75% | 78.93% | 0.6992 |
| Weekly forecast above threshold | 27.93% | 30.27% | 0.2905 |
| Yesterday forecast above threshold | 43.97% | 44.55% | 0.4426 |
| Summer/winter weekday rule | 22.16% | 72.76% | 0.3397 |

Calibration improves Brier score from **0.043915 to 0.043005** (lower is better),
but slightly worsens F1. Both results are retained. The calibrated rule warns on
13.02% of evaluated site-days: 652 true warnings, 387 false warnings, 174 missed
events and 6,769 true negatives. There are 1.455 false warnings per 30 eligible
site-days; this is exposure-normalized, not a count per full calendar month.
Reliability tables contain ten fixed probability bins, their counts, predictions
and observed event rates. Empty bins are unestimated, not zero event rates.

Simulations require complete 48-slot signed days: **6,569 site-days** qualify;
1,413 warning-evaluation days are excluded because other intervals are missing.
Different denominators are intentional and recorded.

| Default simulated effect | All eligible days | Days with uplift | Actual peak-event days |
|---|---:|---:|---:|
| Evening mean reduction | 0.0427% | 0.3319% | 0.2864% |
| Evening maximum reduction | 0.0430% | 0.3331% | 0.2869% |
| Whole-day maximum reduction | 0.0330% | 0.2536% | 0.2525% |

These percentages compare sums/means of per-site-day values, not the simultaneous
network peak and not an average of individual percentage reductions. The default
moves **136.606 MWh** across the eligible days. Capacity limits constrain 36 days;
44 days have an increased whole-day maximum, 687 have an increased late-window
maximum, and six move their maximum from evening to outside the evening window.
An increase in a late-window maximum is not necessarily a new whole-day maximum.
There are 586 baseline days already above the assumed import ceiling; the simulation
does not claim to repair those pre-existing exceedances.

All **96 sensitivity combinations / 630,624 site-day runs** passed conservation,
removal and destination-headroom checks. Energy imbalance is floating-point noise
(the default maximum is about 1.14e-13 MWh). **92 tests and the independent audit
passed.** Small reductions and rebound risks are reported without retuning the
assumptions to reproduce Theo's reference figures.

## Warning and calibration definitions

A peak event is a complete 16:00–21:00 mean **flow magnitude** above that site's
training 90th percentile of complete evening means. Day 4 thresholds are hashed and
independently reconstructed from May 2021–April 2023 data before this run proceeds.
Thresholds remain in MW and do not roll forward.

Theo's probability heuristic is reproduced: average q10/q50/q90 over the ten evening
half-hours, linearly interpolate/extrapolate their CDF, and clip it to 0.01–0.99.
Averaging quantiles corresponds to a shared-rank/comonotonic dependence assumption;
three marginal interval quantiles do not identify the distribution of evening mean.
The clipped tails and epsilon denominator for tied quantiles are heuristic conventions,
not a uniquely justified probability distribution. Ties use Theo's original formula.

Pooled monotonic isotonic calibration is fitted only on early validation risk scores
and events. Its saved x/y knots support linear interpolation and endpoint clipping.
Later validation is evaluated without refitting. Early-period calibrated probabilities
and prices are left unavailable in the published daily table, avoiding an in-sample
performance claim. This probability calibration is separate from forecast-interval
CQR calibration, which remains Day 7 work. No final-test generalization or confidence
interval is claimed; earlier project development has already inspected validation.

## Transparent price signal and equity

For p in [0,1]: multiplier = 1 + 0.5 × max(p−0.30,0)/0.70.
It is 1 below and exactly at p=0.30, and 1.5 at p=1. A warning is p≥0.30; a positive
uplift requires p>0.30. Apply the signal only to half-hours 32–41 (16:00–21:00).
Outside this window, and for exempt households at every time, multiplier is 1.
These are illustrative multipliers, not dollar tariffs or actual bills.

The default exemption share is 10%. Exemption is applied uniformly within each
household group; no eligibility classification is inferred. Voluntary response does
not establish that households can afford higher prices or shift essential use.
Renters and inflexible households may have fewer opportunities to respond. A cap
and exemptions are explicit safeguards, not evidence that the policy is equitable.

## Response assumptions and physical accounting

| Editable assumption | Default |
|---|---:|
| Residential share of positive net imports | 60% |
| Flexible fraction of residential proxy | 15% |
| Response rate at maximum uplift | 10% |
| Exempt share | 10% |
| Solar share | 21% |
| Solar-and-battery share (subset of solar) | 2% |
| Battery response factor | 2× |
| Fraction of shifted energy going to midday | 50% |

The shares are inherited scenario assumptions/proxies from Theo's handover, not
verified contemporary household prevalence. Three disjoint groups are no solar,
solar only, and solar+battery. Battery share cannot exceed solar share. Clip each
group's response to 100% before weighting, then exclude exempt households. Solar
and non-solar homes have the same default response coefficient; changing solar
share alone does not change the result when battery share is fixed.

For each evening slot, movable power is positive signed net imports × residential
share × flexible fraction × effective response. Effective response already includes
price strength, (multiplier−1)/0.5, exactly once. Positive net imports are an explicit proxy for residential
consumption, not gross behind-the-meter demand. Never remove negative export power
as if it were consumption. Magnitude-based warning events and signed-import response
metrics are different quantities; their reductions must not be conflated.

Convert removed MW to MWh using 0.5 hours. Assign half to 10:00–15:00 and half to
21:00–23:00, using equal destination weights by default. The API supports custom
nonnegative weights and an editable midday fraction. Weighted allocation fills
available headroom without exceeding it. The default ceiling is each site's
**training 99th-percentile magnitude**, explicitly a scenario proxy—not a transformer
rating. Additional energy can reduce a negative export reading. Slots already above
the ceiling receive no additional load; existing exceedances remain visible.

Scale the total removal down if either destination cannot accept its required
share. Unshiftable energy stays in the original evening intervals. This preserves
the destination ratio, avoids infeasible removals and conserves signed daily energy.
No battery efficiency loss or actual storage dynamics are modeled: the battery
factor represents assumed participation, not a physical battery dispatch model.

Simulation uses realized historical flow and headroom to assess feasibility. It is
a retrospective scenario with perfect knowledge of that day's flow, not a claim
that an operational controller could know that headroom at midnight. Moving load
into midday assumes advance scheduling from the midnight signal. No causal customer
response, cost saving or measured energy saving is inferred.

The sweep crosses response rates 0%, 5%, 10%, 15%, 20%, 30%; flexible fractions
5%, 10%, 15%, 25%; and capacity factors 0.8, 1.0, 1.2, 1.5. Deakin's 17.3% analogy
is not adopted as a measured response or required target.

## Reproduce and integrate

From `solarshift-ai` with the existing pinned environment:

```sh
PYTHONPATH=src OPENBLAS_NUM_THREADS=4 OMP_NUM_THREADS=4 .venv/bin/python -m solarshift.substation.day5
PYTHONPATH=src .venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python scripts/verify_day5.py
```

Generated tables are under `results/generated/substation_day5/`. Compact evidence
is under `results/evidence/substation_day5/`. Inputs are checked against the Day 4
audit's hashes before evaluation. Raw data and the original source folder are not
modified. The original household experiment remains archived.

For Day 6, call:

```python
from solarshift.substation.scenario_replay import replay_scenario
from solarshift.substation.response import Scenario
result = replay_scenario(
    "results/generated/substation_day4",
    "results/generated/substation_day5",
    site="Aberdeen 66_11kV", date="2023-11-01",
    params=Scenario(response_rate=0.10, flexible_fraction=0.15),
)
# result includes warning probability, multiplier, threshold, assumed ceiling,
# scalar scenario metrics, and a 48-row intervals DataFrame with before/after MW.
```

The API rejects dates inside/before calibration fitting, reserved dates and
incomplete days. `capacity_mw` may override the default assumed ceiling. Invalid
shares, probabilities, multipliers, weights and nonfinite load are rejected.
See `audit.json` for verified complete examples rather than assuming every date
has sufficient source coverage. The documentation example is checked separately.

## Verification and source attribution

The new tests cover the original CDF formula, clipped tails, price boundaries,
invalid inputs, exemptions, overlapping solar/battery shares, per-group saturation,
zero response, known MW/MWh examples, signed exports, constrained destinations,
weighted allocation, rebound peaks and randomized conservation cases. Perturbing
later event labels cannot change the fitted calibration; changing current actuals
cannot change the raw warning score.

The artifact audit independently rejoins signed source readings, recomputes Brier
and confusion counts, checks calibration chronology, compares source and simulated
energy, verifies destination splitting/headroom, exemptions and unaffected intervals,
and exercises the dashboard API on complete and actively shifted examples.

Theo's supplied `trigger.py` and `simulate.py` provided the original warning and
scenario concepts. Codex implemented this adapted, bounded, validation-only version,
tests and evidence under the user's requested Day 5 work. Original-file hashes are
recorded with the evidence. No team signatures or final-method approval are implied.
