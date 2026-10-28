# Marker guide

## Start here

The Canvas link is the public code repository, not a live server. Read the README
for Python 3.12 setup, then run `python run.py`. Open http://localhost:8501.
The launcher downloads and checks the official Ausgrid FY2024 archive, reconstructs
measured flow and baselines, and opens the genuine-data walkthrough. No training,
API key, hidden folder or paid model service is required.

For browser-only use, choose Code → Codespaces → Create codespace on main.
The included dev container installs dependencies. Run `python run.py` in the
terminal, then open forwarded port 8501. Codespaces requires your own GitHub account
and is subject to its usage allowance. The project does not make the port public.

## Two-minute walkthrough

1. The default is **Aberdeen 66_11kV, 12 November 2023**, an active-warning example.
   Read the evening risk and capped non-exempt price multiplier. Reveal measured
   magnitude to compare the forecast with the historical outcome.
2. Open **Explore a response**. Set response to 0%: displaced energy becomes zero.
   Restore 10%, then set exempt households to 100%: it is zero again. Restore 10%.
   Compare before/after signed flow and read any rebound/capacity warnings.
3. Open **Evidence**. Final-test results are distinct from validation metrics.
   Read coverage, weekly bootstrap uncertainty, warning performance and the
   instrumented-training carbon scope. Forecasting gains do not imply causal savings.
4. Download the replay CSV and scenario JSON. They record this selected day and
   the assumptions, not the full research dataset.

The walkthrough provides 42 complete historical days across three sites. The
full-study evidence describes 63 sites. The app clearly labels this difference.

## If the automatic download fails

Go to the [official Ausgrid data page](https://www.ausgrid.com.au/about-us/about-ausgrid/research-data-sets/distribution-zone-substation-data)
and download **2024 Distribution zone substation data**. Keep it as a ZIP.

```sh
python run.py --archive /path/to/the/downloaded.zip
```

The original archive SHA-256 must be:
`30be21ff0222b7398e225964b713f7827ca0f1f5c39f348f476b7540335cb045`.
A mismatch means the source changed; do not bypass the check. The repository retains
screenshots and aggregate evidence for inspection if the provider is unavailable.
The setup never extracts arbitrary archive paths or executes downloaded files.

## Troubleshooting

- **Port in use:** stop the other Streamlit process, or prepare first and run
  `python -m streamlit run streamlit_app.py --server.port 8502`.
- **XGBoost/OpenMP error:** install libomp on macOS or libgomp1 on Debian/Ubuntu.
- **Wrong Python:** use a fresh Python 3.12 virtual environment.
- **Missing data:** run `python run.py --prepare-only`; the app also offers an
  explicit setup button. A bare `streamlit run` cannot access another person's files.
- **Offline:** supply the verified ZIP with `--archive`; dependencies must already
  be installed. Once prepared, the walkthrough itself makes no data API requests.
- **Theme:** use the app-configured theme in Streamlit settings if your browser
  has saved a manual override.

## Optional hosting

Streamlit Community Cloud can run `streamlit_app.py` from this repository's main
branch with Python 3.12 and the supplied requirements/packages files. The first
visitor uses the setup button to fetch the public archive into the app's local
runtime. The host may discard that cache after a reboot. This is a deployment-ready
path, not a claim that an app has been deployed. Account setup and any third-party
terms are handled by the hosting account owner.

Reference: [official Streamlit deployment instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).
