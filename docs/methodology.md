# Day 1 methodology

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

No interpolation, forward filling, target clipping, forecasting, model selection,
price response or simulated results are performed. Counts include controlled-load
rows where present; they are not all demand/PV target pairs.

Data-quality eligibility is independent of future model errors. Later feature
construction must also reject cases whose lag histories are unavailable, including
lags crossing excluded transition days. Day 1 does not certify future leakage safety.

The proposed downstream split is training July 2010–December 2011, validation
January–June 2012, test July 2012–June 2013. The 18:00 previous-day forecast cutoff
requires availability checks, not unrestricted previous-day same-interval values.
These are recorded plans, not implemented capabilities.
