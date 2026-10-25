# Data and forecasting methodology

This document describes the archived household experiment. For the active
substation prototype, see [Day 4 integration](substation_day4.md).

1. Verify the complete source archive, or accept explicitly supplied original CSVs.
2. Enforce observed metadata/interval column order and parse both observed date formats.
3. Reject a complete channel-day when any interval is missing/nonfinite or negative;
   when quality is nonblank; when its source key is duplicated; when metadata is
   invalid/inconsistent; or when the day falls outside its source year or on a DST transition.
4. Keep physical-but-unusual high PV readings and count a warning if any half-hour
   average exceeds 125% of nameplate capacity. This is a screening flag, not a
   claim that the measurement is impossible or a tuned exclusion threshold.
5. Convert each accepted daily channel row to 48 interval rows. Use local
   interval-ending timestamps, including next-day midnight; power is energy / 0.5 h.
6. Store all accepted channels separately and report unavailable primary channels.
7. Chart measured power and daily energy with missing intervals left as gaps.

The ingestion stage performs no interpolation, forward filling or target clipping.
Its counts include controlled-load rows where present; they are not all demand/PV
target pairs. Forecast evaluation uses only GC and GG.

Data-quality eligibility is independent of future model errors. Later feature
construction rejects cases whose required lag histories are unavailable, including
lags crossing excluded transition days. Complete 48-slot target days are required.

## Forecast-available information

Each target day is forecast at 18:00 on the preceding local date. An observed
reading is available 30 minutes after its interval end. This delay is a research
assumption; the historical files do not establish real-time meter availability.
The prediction horizon spans the next day's complete 48 slots (roughly 6–30 hours
ahead). Target dates are local calendar dates; offsets account for Sydney DST.

For each household and target channel, features include cyclical slot/weekday/month,
weekend, Australian season, PV capacity, energy at the same slot two and seven
calendar days earlier, and a mean of all seven same-slot observations from days
-2 through -8. No mean is calculated from an incomplete window.

Previous-day same-slot energy is used only when its availability timestamp is at
or before issue time; otherwise the two-day value is used. An indicator records
that distinction. At the configured cutoff slots 1–35 qualify; slots 36–48 do not.
Every observed feature has a corresponding availability timestamp. Assertions and
future-data perturbation tests check the cutoff. Actual target values, dates,
timestamps, IDs and partition labels are not in the model-feature allowlist.

## Development partitions and cohort

Training is July 2010–December 2011; validation January–June 2012; final test July
2012–June 2013. Training-only daily coverage of both GC/GG must be at least 95%
of calendar days. A uniform seeded sample of 30 eligible households is selected
without replacement. It is a computational pilot, not a stratified representative
sample. Selection is fixed before validation errors are computed.

The builder verifies source hashes, reads no final-test annual interval file,
filters development observations by date and writes train/validation features only.
No fitted preprocessing is required. XGBoost hyperparameters are selected using
validation only, as documented in [modelling methodology](modelling.md). The final
test partition is defined and reserved for the later frozen-method evaluation.

## Baseline and metrics

Weekly persistence is the exact same local slot seven calendar dates earlier.
It uses the same complete-day feature mask intended for learned-model comparison.
This is stricter than the mask a standalone persistence model alone would need;
the loss of forecast coverage is reported explicitly.

MAE = mean absolute prediction error; RMSE = square root of mean squared error.
Primary units are kWh per half-hour. Average-power errors in kW are twice those
values. The evening window uses interval starts from 16:00 through 20:30 inclusive,
giving ten intervals ending at 21:00. GC excludes CL; GG is gross generation.

Pooled household errors give each accepted interval equal weight. Individual
household scores are also saved. Community errors first sum across the entire
fixed cohort and admit only days with every household in every slot. They are
not averages of household errors. Full-day PV errors include night-time zeros.

The saved validation predictions are independently joined to source target and
lag observations, and pooled metrics are independently recomputed. Missing
required histories are not imputed or shifted by row position. No demand-response,
tariff or causal claim follows from this baseline benchmark. Measured XGBoost
validation comparisons now appear in the separate model report and modelling notes.
