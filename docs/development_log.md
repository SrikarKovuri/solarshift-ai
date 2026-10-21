# Development log

## Day 1 — authorised 21 October; completed 22 October 2026 (Australia/Sydney)

The brief scheduled Day 1 for 22 October. Work began after explicit user approval
on 21 October and continued on 22 October. Source acquisition and initial test
timestamps reflect the actual earlier execution; no timestamps or commits are backdated.

### Delivered

- Separate Python package and Git repository; the pre-existing study website was untouched.
- Complete archive validation and original annual CSV ingestion with provenance hashes.
- Conservative validation, explicit exclusion ledger, missing primary-channel coverage.
- Three interval Parquet files, daily summaries and household metadata.
- Offline interactive Plotly historical chart with channel toggles and zoom.
- Pinned dependencies, setup instructions, methodology and AI-assistance disclosure.
- Public repository: https://github.com/SrikarKovuri/solarshift-ai

### Executed data evidence

| Source year | Input channel-days | Accepted channel-days | Excluded channel-days | Accepted intervals |
|---|---:|---:|---:|---:|
| 2010–2011 | 269,735 | 268,257 | 1,478 | 12,876,336 |
| 2011–2012 | 270,304 | 268,727 | 1,577 | 12,898,896 |
| 2012–2013 | 268,557 | 266,651 | 1,906 | 12,799,248 |
| Total | 808,596 | 803,635 | 4,961 | 38,574,480 |

All 300 households appear in the accepted data. Counts include GC, GG and CL;
they are channel readings, not 38 million distinct household-time points.
4,268 expected GC/GG channel-days are unavailable after validation, including
missing source days and excluded records. No target values were imputed.

The primary exclusions were DST transition days and non-actual/unknown quality.
Reasons can overlap, so their counts need not sum to distinct excluded days.
High PV readings were flagged for investigation without automatically deleting them.

### Verification

- 29 Pytest cases cover acquisition failures, CSV variants, literal quality flags,
  invalid readings, duplicates, metadata conflicts, DST, midnight, energy units,
  missing CL and end-to-end chart generation. Final summary: `results/evidence/tests.json`.
- Independent standard-library CSV summation matched Parquet energy totals for
  each annual file/channel; physical invariants checked all 38,574,480 accepted readings.
  Evidence: `results/evidence/real_data_audit.json`.
- Complete ZIP CRC and file hashes: `results/evidence/acquisition.json`.
- Actual parser decisions and versions: `results/evidence/quality_report.json`.
- Historical chart inspected in a browser; power and daily energy were visibly plotted.
- Installed dependency consistency checked with `python -m pip check`.

The first test run had two incorrect expectations about cross-row metadata
inconsistency. Tests were corrected to isolate invalid-value checks; the separate
metadata-conflict test retains the conservative rejection expectation.
Editable installation hooks did not load reliably in the execution sandbox;
the documented setup uses a regular package installation, which was verified.

### Stage boundary and next work

Day 2 has not started. Next: forecast availability cutoff, leakage-safe features,
chronological split and seasonal persistence. DST lag dependencies, licence
corroboration and the dataset's historical sampling limitations remain explicit.
No forecast performance, simulated savings or trained models are claimed.

Commit purpose: `feat(data): establish Ausgrid ingestion and validation pipeline`.
Human team review is pending; planned ownership is not claimed as completed contribution.
