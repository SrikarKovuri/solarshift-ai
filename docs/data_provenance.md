# Data provenance

This document describes the archived household experiment. For the active
substation prototype, see [Day 4 integration](substation_day4.md).

## Source chain

Original publisher: Ausgrid, Solar Home Electricity Data, July 2010–June 2013.
Original page checked during review:
https://www.ausgrid.com.au/Industry/Our-Research/Data-to-share/Solar-home-electricity-data
(returned 404).

Research archive documentation: https://github.com/pierre-haessig/ausgrid-solar-data
Archive: https://pierreh.eu/downloads/Ausgrid_solar_home_data.zip
Supporting schema description: https://unsw-ceem.github.io/DARTH-docs/ausgrid300/

The archive includes the original `Ausgrid solar home electricity data notes
(Aug 2014).pdf` and three annual CSVs. It also contains unrelated monthly data,
which is checked as part of archive integrity but not extracted for this project.

The first feasibility-review download was incomplete. During Day 1, the remaining
bytes were downloaded and the entire archive was checked with Python ZipFile's
CRC verification. No partially recovered member is accepted by the acquisition
module. Exact hashes and verification time appear in `results/evidence/acquisition.json`.
Checksums provide reproducibility and integrity, not proof against independent
publisher-held copies, which were unavailable.

## Licensing

The mirror README states Creative Commons Attribution 3.0 Australia for the
original 2014 release. The original included notes describe research and other
uses but do not reproduce that licence grant. This distinction remains explicit.
No raw measurements or original PDF are published in this repository. Retain
Ausgrid attribution and the source chain when discussing results.

## What the dataset measures

300 domestic gross-metered solar customers, not a representative household survey.
Ausgrid selected customers with complete actual first-year records and excluded
extreme first-year consumption/generation performers. Household characteristics
were not surveyed. This affects representativeness and equity inference.

GC = general consumption excluding CL; CL = controlled load; GG = gross generation.
Capacity is nameplate kWp; interval values are kWh and positive for consumption
and generation. Later CSVs include `Row Quality`: blank means actual; `NA` means
some or all values were estimated/substituted. The parser preserves this literal
flag instead of allowing pandas to turn it into generic missing data.

Observed dates use both `d-Mon-yy` and `d/mm/yyyy`. Interval columns run from
`0:30` through `23:30`, then `0:00`. The source notes describe EST/EDT local time,
but retain 48 readings per source date. DST transition days are quarantined;
their physical interval correspondence has not been resolved.

## Audit outputs

`quality_report.json` records actual counts, periods, channels, file hashes,
versions, configuration hash and output hashes. The excluded-row ledger records
source filename/line, original date, customer, channel and all reasons. A separate
coverage table records missing accepted GC/GG days (including exclusions).
Controlled-load absence is not automatically a defect or a zero reading.
