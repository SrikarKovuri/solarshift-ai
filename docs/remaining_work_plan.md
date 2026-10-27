# Remaining prototype work

Updated 27 October 2026 after reviewing Theo's 7 October team document,
`Closing the Peak Data & Features Explained for the Team.docx`.
This plan tracks functional milestones and their acceptance criteria. Forecast
integration, response scenarios, dashboard integration and grouped explanations are implemented;
final evaluation and handover remain outstanding. See [forecast evidence](substation_forecasting.md)
and [response evidence](substation_response.md).

## What the document changes

Before substation integration, the local implementation used Ausgrid household GC/GG data from
2010–2013, a 30-household pilot and point XGBoost forecasts. That archived experiment does not implement
the document's revised substation study. The substation implementation now supplies
substation validation output with the deviations documented separately. Similarities such as the evening window,
weekly persistence and leakage checks do not establish use of this document.

The document describes 60 residential-type substations, a 2021–2025 modelling
period, weather inputs, quantile forecasts, peak probabilities and top-down
household-response scenarios. It reports that the tutor approved that change;
that approval and the reported results have not been independently verified here.
The revised substation approach is the intended main prototype. Preserve the
existing household experiment as archived development history. The user confirmed
the pivot on 23 October: all remaining development and evaluation effort targets
Theo's substation approach. Do not add a household-pilot screen or rerun the old
experiment as a remaining milestone. Reuse generic utilities only where suitable.
The intended application is defined in [product scope](product_scope.md).

## Source access and revised handover — 23 October 2026 (historical status)

The user supplied `/Users/srikarkovuri/Downloads/ENGG2112_ClosingThePeak/` and
confirmed the substation pivot while retaining the working-prototype objective.
Keep the existing dashboard,
explanations, simulation and handover deliverables; change their data/model basis.

The folder is accessible. Inspection confirmed source modules, nine notebooks,
two test files, report outputs, raw Ausgrid FY2021–FY2025 ZIPs, cached weather and
AEMO/CER CSVs. Processed assets include retained sites, training peak thresholds,
anomaly days and locations. The documented cleaned substation tables and
`features_v1_residential.parquet` are absent from the supplied processed directory;
they must be rebuilt from raw inputs. Existing report scores remain Theo-supplied
results until reproduced. Access is resolved; integration is not yet complete.

Use the handoff documents as project requirements/reference material under the
user's requested pivot, not as authorization to send team messages, sign names,
upload to Drive or execute the reserved test. Preserve the supplied folder as the
reference and implement adapted code in this project's workspace.

Source inspection resolves several planning details:

- `src/config.py` confirms midnight issue time, the stated split dates and evening
  half-hours 32–41. Interval-label and availability checks remain necessary.
- `src/trigger.py` already implements the 30% activation / 1.5× cap formula below.
  It averages interval quantiles and uses a piecewise-linear CDF with linear tails,
  clipping the CDF to 0.01–0.99. This is an assumption to validate, not an exact
  derivation of evening-mean uncertainty.
- `src/simulate.py` supplies the stated defaults and 10:00–15:00 / 21:00–23:00
  destinations. Add parameter bounds, signed-flow handling and capacity checks;
  its per-day energy sums need the 0.5-hour conversion for MWh display.
- `src/weather.py` explicitly documents Jan 2024–Apr 2025 error donors, and
  `src/config.py` requires coverage in every split. The leakage concerns below
  therefore apply to actual source code, not just wording in the Word document.
- The pre-registration specifies **weekly** block bootstrap (500 resamples,
  seed 2112). Use that specification for the primary uncertainty analysis.

Prioritize one complete validation-backed journey:
site/date → forecast → warning → response scenario → evidence. LSTM, hosting and
extra model searches are stretch work. A runnable validation-backed prototype can
be delivered even if team sign-off for final-test evaluation remains outstanding.
Do not describe that as completed held-out evaluation.

## Data integration and forecast alignment

**Outcome:** a reproducible substation validation forecast feeding a common
interface, with provenance and units visible.

- Import and inspect Theo's source, tests, data dictionary, source register and
  pre-registration. Record file hashes, versions and actual team contributions.
  Keep raw files outside Git; verify source terms before any redistribution.
- Reuse the tested pipeline where possible. Check date parsing, FY2025 time-column
  sorting, interval endings, DST, gaps, flat runs, spikes and switching flags.
  Average two 15-minute MW readings to half-hour MW; use MW × 0.5 for MWh.
- Preserve signed flow separately from the consistently defined magnitude
  forecast target. Check the reported May 2023 sign break. Never apply the
  household parser's blanket negative-value rejection to substation exports.
- Implement an explicit substation schema: site, issue time, interval start/end,
  signed actual MW, magnitude target MW, q10/q50/q90 MW, split, weather provenance
  and quality flags. Inverse-transform normalised predictions before MW metrics.
- Use the document's training period (May 2021–April 2023), validation period
  (May 2023–April 2024) and reserved test period (May 2024–29 April 2025).
  Verify boundaries against source timestamps. Establish the midnight issue-time
  and reading/weather availability contract; do not silently inherit 18:00.
- Reconcile the five feature families: historical load, forecast weather,
  calendar, sun position and training-derived substation attributes. Compare
  weekly persistence, yesterday persistence and weather/calendar regression
  against the quantile boosted model on identical eligible rows.

**Acceptance:** source-backed validation output, explicit units and target,
feature-availability tests, reproducible baseline comparison and no test scoring.
If assets are unavailable, finish the interface and small labelled test fixtures;
record real-data integration as blocked, rather than marking this milestone done.

## Peak warnings and constrained response (implemented 25 October)

**Outcome:** an explainable warning and pricing rule with an auditable simulation.

- Fix each site's peak-event threshold at the training 90th percentile of daily
  16:00–21:00 mean load. Specify magnitude versus signed-flow semantics in the
  event definition and evaluate predictions against that same definition.
- Inspect and reproduce `trigger.py`'s probability calculation. Three interval
  quantiles alone do not uniquely determine the probability of an evening-mean
  event; document the aggregation/distribution assumption and validate calibration.
- Use the document's 30% switch-on and 1.5× cap. A proposed explicit continuous
  rule is 1 below p=0.30, otherwise 1 + 0.5(p−0.30)/0.70, for p in [0,1].
  Source inspection confirms Theo's implementation matches this formula; test its boundaries. Apply the
  signal to the defined evening window; show multipliers unless a tariff is sourced.
- Implement scenario defaults from the document: 60% residential share, movable
  fraction 5–25%, response 0–30%, 10% exempt households, and a proposed 2× battery
  response. Keep every assumption editable and bound effective response at 100%.
  Check solar/battery group overlap rather than double-counting households.
- Move half the displaced evening energy to midday and half after 21:00 using
  explicit destination weights and capacity constraints. Use signed validation
  flow; do not calculate movable residential demand from absolute export values.
  State the approximation needed to infer residential demand from net flow.
- Test conservation in MWh, zero response, exemptions, cap boundaries, feasible
  removal and rebound peaks. Report evening mean, evening maximum, whole-day
  maximum and warning frequency separately. These are simulated effects.

**Acceptance:** source-backed warning metrics, calibrated probability diagnostics,
boundary checks and conserved energy across the full sensitivity sweep. Treat
Deakin's 17.3% as an attributed analogy only, never a measured evening response.

## Integrated prototype and explanations (implemented 27 October)

**Outcome:** an interactive Streamlit demonstration using the revised pipeline.
Implemented and checked; see [dashboard guide](dashboard.md). Grouped permutation importance
is included; optional SHAP is deferred.

- Add site/date selection, forecast ranges and actual flow, evening-window marking,
  peak threshold, warning probability, multiplier and scenario controls.
- Show before/after curves, displaced MWh, peak changes and rebound indicators.
  Clearly distinguish measured data, model forecasts and simulated responses.
- Include grouped permutation importance and, if feasible, SHAP. Explain the
  contribution of lags, weather and calendar without implying causation.
- Display data dates, source, units, exclusions and uncertainty. Exclude the old
  household pilot from the application and final headline results. Its evaluation
  is archived history and does not substantiate the revised substation product.
- Include equity explanations for renters, inflexible users and households without
  solar; show voluntary response, exemptions and the price cap in the interface.

**Acceptance:** a complete site/date → forecast → warning → scenario demonstration,
clear unavailable-data errors, verified chart labels and documented limitations.

## Final evaluation and handover

**Outcome:** a reproducible evidence pack, demonstration and report-ready findings.

- Freeze methods, feature definitions, cohort, probability calibration, price rule,
  simulation assumptions and success criteria before final-test evaluation.
  Record genuine team sign-off; never set the sign-off flag on their behalf.
- The document proposes ≥30% evening MAE improvement against weekly persistence,
  lower confidence bound >15%, warning F1 above naive/seasonal rules, 70–90%
  coverage for an intended 80% range, meaningful feature explanations and a
  reported CodeCarbon estimate. Label these proposed until team agreement.
- Reproduce chronological CQR calibration and later validation checks; freeze the
  calibration before testing. Report coverage and width, MAE/RMSE/nMAE, week-block
  bootstrap intervals, precision/recall/F1, false alarms and probability calibration.
- Inspect the existing robustness scripts for earlier-year backtesting, lockdown
  sensitivity and mixed substations. Run feasible checks without retuning to test.
- After the freeze and genuine sign-off, score the reserved year once. Record
  failures and deviations; if prerequisites remain unmet, deliver validation-only
  evidence and identify the final test as outstanding.
- Record actual substation-model training carbon estimates and their scope;
  the existing household CodeCarbon run cannot stand in for the revised model.
- Prepare screenshots, a short demo script, reproducibility steps, ethics,
  limitations and accurate AI/human contribution records. LSTM is a stretch goal.

**Acceptance:** every headline number traces to an executed output, every simulation
assumption is visible, and the report distinguishes validation from held-out testing.

## Issues to resolve before adopting the reported results

1. The document's site coverage rule uses train, validation and test coverage.
   Fit clustering, scaling and anomaly rules on training only; audit and disclose
   any test-period participation in cohort selection. Prefer a training-selected
   cohort with later coverage reported separately, retaining the original analysis
   as a labelled comparison if changing selection changes its results.
2. Its pre-2024 weather error transplant draws errors from 2024–2025, potentially
   overlapping the held-out year. Inspect exact donor timestamps. Use only
   pre-test donors with a documented chronology, or genuine temperature-only
   inputs for the primary leakage-controlled model. Treat synthetic weather as
   a separate sensitivity experiment rather than genuine issued forecasts.
3. The document reports scikit-learn model results; an XGBoost rerun needs its own
   evaluation. The reported 57% improvement, 83% warning recall, 77.9% recalibrated
   coverage and roughly 1.1% simulated reduction are reference claims, not local
   results. Do not transfer them to the app or report as reproduced findings.
4. Verify external context, source permissions and the Deakin wording against
   original sources during report preparation. Do not carry forward expired
   October 12–21 deadlines or describe historical data as current measurements.

## Proposed responsibility split

Theo supplies and reviews the data/features assets; Lucas reviews quantile models,
calibration and forecast evaluation; Srikar reviews pricing, equity, simulation and
integration. These are proposed responsibilities, not claims of work completed.

## Delivery practice

Commit and push completed, verified changes with descriptive milestone messages.
Keep raw/generated datasets, model binaries and environments excluded by Git rules.
Final reserved-test evaluation depends on method freeze and genuine team sign-off.

## 28 October update

Atlas theme, chronological CQR diagnostics, paired weekly bootstrap and monthly/anomaly
sensitivity slices are complete. See [validation handover](validation_handover.md). Historical outstanding-work statements above describe the earlier milestone.
Reserved testing, genuine sign-off, training carbon and broader robustness remain outstanding.
