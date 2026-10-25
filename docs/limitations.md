# Known limitations and open decisions

This document describes the archived household experiment. For the active
substation prototype, see [Day 4 integration](substation_day4.md).

- Historical 2010–2013 solar households do not represent current NSW equipment,
  tariffs, adoption, batteries, renters or all customer groups.
- Original download endpoint is unavailable; the research mirror's transport and
  original data provenance must remain distinguishable.
- The original licence grant has not independently been recovered.
- DST transition readings remain excluded pending source clarification.
- Whole-channel-day exclusion is conservative and loses some otherwise usable
  intervals. Coverage and reasons are reported, with no claims of unbiased missingness.
- GC excludes controlled load; GG is gross generation. Net-metered self-consumption
  or P2P surplus would be a future accounting assumption.
- Annual wide-table parsing is not fully streaming; interval output is batched.
- Initial preparation validates observations across years. The forecasting increment
  uses training/validation only; final-test performance remains unevaluated.
- No weather forecast archive covering these dates has been established.
- No customer elasticity, appliance constraints, network topology or demographic
  ground truth is available. Later simulation must state these assumptions.
- No software redistribution licence has been chosen by the team.
- Trained models and reports are operational; the integrated application and simulation remain pending.
- Observation availability is an assumed 30-minute delay, not a verified historical
  live smart-meter service. Longer-delay scenarios need separate evaluation.
- The baseline uses a seeded 30-household pilot. Generalisation beyond this cohort
  is untested; strict history completeness removes forecast days.
- Model validation was used for selection, so it is not unbiased final-test evidence.
  The demand evening improvement of 14.75% misses the 15% target; no final-test
  improvement, causal benefit or simulated savings are established.
- Models pool households without identity features. Weather, occupancy, appliance
  state and current household characteristics are unavailable; PV errors include
  night-time zeros. Small positive night-time PV forecasts may occur.
- Training carbon is estimated from assumed power and country-average intensity.
  It excludes development, AI assistance, data preparation and audit repeat fits.
