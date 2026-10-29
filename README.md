# SolarShift AI — Closing the Peak

An ENG2112 research prototype for substation demand forecasting, peak warnings
and voluntary load-shifting scenarios. The app shows historical forecasts,
editable simulations and separately labelled validation and final-test evidence.

**Marker: start here.** This repository contains the code, trained models, compact
research evidence and model outputs for a small genuine-data walkthrough. The
walkthrough downloads original readings directly from Ausgrid once (about 17 MB).
You do not need the team's private data folder, an API key or a training run.

## Run the application

Use **Python 3.12**. Clone or download this repository, then open a terminal in it.

**macOS / Linux**

```sh
git clone https://github.com/SrikarKovuri/solarshift-ai.git
cd solarshift-ai
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

The walkthrough replays saved forecasts and does not load XGBoost or require its
native OpenMP library. For optional model training or model reload checks, install
OpenMP **before** running those commands: `brew install libomp` on macOS
(requires Homebrew), or `sudo apt-get install libgomp1` on Debian/Ubuntu.

If an older checkout reports `Library not loaded: @rpath/libomp.dylib`, stop the
app with Ctrl+C, run `git pull --ff-only`, then run `python run.py` again.
You do not need to recreate the virtual environment or download the data again.

**Windows PowerShell**

```powershell
git clone https://github.com/SrikarKovuri/solarshift-ai.git
cd solarshift-ai
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

Open **http://localhost:8501** when the terminal says the app is ready. Keep the
terminal running. Stop with Ctrl+C. The first run needs internet for dependencies
and the public data download; subsequent runs reuse the verified local archive.
These commands work with source-tree imports; installing this package is optional.

**Browser-only alternative:** open the repository in GitHub Codespaces, wait for
the supplied dev container to install dependencies, run `python run.py`, and open
the forwarded port 8501. This uses the marker's GitHub account and its Codespaces
allowance; it is not an already-hosted public app.

See [marker guide](docs/marker_guide.md) for a two-minute demonstration, offline
archive fallback and troubleshooting. GitHub displays the source code; it does
not run Streamlit. A `localhost` URL points to the visitor's own computer.

## What is included

- **Working interface:** forecasts and uncertainty, warning probability and price
  multiplier, response/exemption controls, before/after curves and CSV/JSON exports.
- **Walkthrough:** 42 complete site-days across Aberdeen, Adamstown and Avoca in
  November 2023. These are genuine saved forecasts, not generated sample data.
  Measured flow and persistence readings are rebuilt from the official archive.
- **Full study evidence:** 63 training-selected substations, chronological
  validation, final held-out evaluation, feature importance and sensitivity checks.
  Evidence tables cover the full study, not only the walkthrough sample.
- **Frozen trained models:** three native XGBoost UBJSON files and portable ridge
  coefficients in `artifacts/frozen_models/`. The app replays saved predictions;
  scenario controls do not train or forecast a live electricity network.
- **Tests and CI:** unit, leakage, scenario, marker and dashboard checks. GitHub
  Actions runs tests on each push; raw-data-dependent checks skip in a bare clone.

## Final held-out results

The frozen training-only models were evaluated once on **1 May 2024–29 April 2025**
after Srikar confirmed team approval. No models or calibration were tuned on the test.

| Measure | Held-out result |
| --- | ---: |
| Eligible intervals | 972,371 |
| Substations | 63 |
| Evening MAE improvement over weekly persistence | 54.22% |
| 95% week-block bootstrap interval | 50.26–57.27% |
| Recalibrated nominal-80% evening coverage | 77.21% |
| Complete simulated site-days | 17,822 |

Coverage remains below nominal 80%. The default scenario reduces mean evening
flow by **0.0886%** across all complete test days; these are simulated effects,
not measured customer behaviour or energy savings. Rebound increased the whole-day
maximum on 32 simulated days. All 96 scenario combinations conserve energy.

[Final evaluation methods and verification](docs/final_evaluation.md) ·
[Machine-readable final evidence](results/evidence/final_evaluation/summary.json)

## Verify and reproduce

```sh
python -m pip install --no-deps -e .
python -m pytest -q
```

`python run.py --prepare-only` prepares the walkthrough without opening a server.
The full original data and feature tables are deliberately not committed. Full
reproduction requires the source archives/weather handover documented in
[research reproduction](docs/reproduction.md). `python run.py --full` uses already
prepared full research artifacts. Do not confuse a walkthrough with independently
retraining or reproducing the entire study.

## Sources, scope and attribution

Ausgrid supplies historical zone-substation readings; Open-Meteo supplies the
cached previous-run temperature used in model development. See
[source notices](docs/source_notices.md). Raw source archives and reconstructed
measurements stay local and Git-ignored. This repository does not grant new rights
over third-party data or all team-authored code.

Theo supplied source assets and scenario concepts. Local implementation and checks
were developed with Codex assistance at Srikar's request. See
[development log](docs/development_log.md) for actual work and limitations.

The household pilot is archived development history, not the current application:
[archived household documentation](docs/archived_household_readme.md).

## Submission

Submit the public repository URL in Canvas:

**https://github.com/SrikarKovuri/solarshift-ai**

Ask the marker to follow this README or `docs/marker_guide.md`. A hosted-app link is
optional and separate; no live hosted URL is claimed here. The project includes a
Codespaces configuration and Streamlit deployment dependencies, but deployment
requires the hosting account owner's setup.
