# Interactive validation dashboard

Implemented 27 October 2026 (the work request began on 26 October, before midnight).
Run from the `solarshift-ai` directory:

```sh
.venv/bin/python -m pip install -r requirements-lock.txt
PYTHONPATH=src .venv/bin/python -m streamlit run streamlit_app.py --server.address=127.0.0.1 --browser.gatherUsageStats=false
```

Open http://localhost:8501. Local Day 4 and Day 5 generated artifacts are required;
follow `substation_forecasting.md` and `substation_response.md` if rebuilding on a
fresh machine. The application displays an actionable error when these are absent.
`SOLARSHIFT_RESULTS` can point to another generated-results directory. Restart the
server after replacing an experiment's artifacts. No live API or cloud deployment
is required, and the household experiment is excluded from the application.

## Demonstration (about three minutes)

1. Choose **Aberdeen 66_11kV**, **2023-11-01**. Explain the midnight forecast,
   q10–q90 magnitude range, weekly baseline and evening-mean threshold. Reveal
   measured magnitude. This example has no price uplift and no shifted energy.
2. Choose **Aberdeen 66_11kV**, **2023-11-12**, the audited active example.
   Show calibrated risk and the non-exempt evening multiplier. Open Response scenario.
3. Increase response from 10% to 30%, then set response to zero: displaced energy
   becomes zero. Restore response and set exemptions to 100%: it is again zero.
   Discuss the signed-flow chart, import ceiling and rebound flags.
4. Open Evidence & explanations. Compare validation baselines and warnings, then
   show grouped feature importance. These are global predictive associations;
   they do not explain causality or attribute this day's forecast to individual inputs.
5. Download the replay CSV and assumption JSON. Explain that energy is shifted,
   not saved, and that final-test evaluation still requires a method freeze and
   genuine team sign-off.

## Explanation computation

```sh
PYTHONPATH=src .venv/bin/python -m solarshift.substation.explain
PYTHONPATH=src .venv/bin/python scripts/verify_day6.py
PYTHONPATH=src .venv/bin/python -m pytest -q
```

The explanation run samples 12,000 eligible November 2023–April 2024 evening
intervals with seed 2112. Each feature family is jointly shuffled five times across
those rows. The three saved quantile models are reloaded; their clipped, sorted
median is inverse-scaled to MW exactly as in the original pipeline. The original
site scale remains fixed when training-attribute features are shuffled. This is
feature sensitivity of the fitted model, not a simulation of changing physical sites.

Mean MAE increases: historical load 1.119693 MW, forecast temperature 0.612789 MW,
sun position 0.031747 MW, calendar 0.022980 MW and training attributes 0.018686 MW.
The unshuffled sample MAE is 1.134694 MW. Correlated features and implausible
permutations limit interpretation; repeat standard deviations are not confidence
intervals. SHAP is deferred; there is no local SHAP explanation claim.

The independent audit matches sample loss to the saved validation forecasts,
checks source/model hashes, compares every selectable day with the Day 5 scenario
catalog and checks an activated replay against saved displaced energy. UI tests
use Streamlit AppTest, including site/date changes, zero response, full exemptions,
invalid group shares and missing artifacts. Chart tests separate magnitude and
signed-flow units. The browser was also inspected at narrow and wider panel sizes.

Screenshots and compact numeric evidence are retained in
`results/evidence/substation_day6/`. Large feature tables and model binaries remain
ignored. Sources and models were not retrained or retuned for this milestone.

## Remaining evaluation

The dashboard explicitly reports uncalibrated interval coverage and displays the
separate probability calibration. Chronological CQR, week-block bootstrap,
robustness analysis, substation training carbon instrumentation and the reserved
final test remain part of final evaluation. The household carbon estimate is not
reused. No final-test observation was loaded for this milestone.

## 28 October update

Atlas theme, chronological CQR diagnostics, paired weekly bootstrap and monthly/anomaly
sensitivity slices are complete. See [validation handover](validation_handover.md). Historical outstanding-work statements above describe the earlier milestone.
Reserved testing, genuine sign-off, training carbon and broader robustness remain outstanding.
