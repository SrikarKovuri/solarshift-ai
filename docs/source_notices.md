# Source notices and redistribution boundaries

Checked against primary sources on 28 October 2026.

## Ausgrid

[Distribution zone substation data](https://www.ausgrid.com.au/about-us/about-ausgrid/research-data-sets/distribution-zone-substation-data)
provides public historical demand archives. The source says Ausgrid retains
copyright/IP and warns that the SCADA/metering data can contain errors, gaps and
switching effects. We do not turn a catalogue licence label into a new licence grant.

Raw archives and reconstructed original flow values are not shipped in Git. The
marker setup retrieves the archive directly from Ausgrid, verifies its exact hash,
and stores it and derived replay readings only under ignored results/generated.
Bundled walkthrough files contain model predictions and fitted research artifacts;
aggregate study metrics are attributed to the local experiment using Ausgrid data.
Do not assume the repository grants permission to relicense the source dataset.

## Open-Meteo

[Open-Meteo terms](https://open-meteo.com/en/terms) describe CC BY 4.0 weather data
and non-commercial API conditions. Development used genuine GFS previous-day1
cached temperature, not live observed weather or synthetic future-error donors.
[Previous Runs documentation](https://open-meteo.com/en/docs/previous-runs-api)
describes forecast lead times. No API keys are stored in this project.

## Code and contributions

Theo supplied reference code, data/features assets and scenario concepts. The local
pipeline adapted those assets; Codex implemented and checked local changes at
Srikar's request. No open-source licence is assigned on behalf of all contributors.
A public repository enables assessment access; it does not by itself establish an
unrestricted redistribution licence for all included material.

The demonstration does not depend on the Deakin percentage analogy, AEMO price
context or CER uptake claims. Those contextual sources are not treated as measured
response effects or as inputs to the frozen final-test model.
