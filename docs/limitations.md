# Known limitations and open decisions

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
- Initial preparation hashes and validates observations across years, but does not
  inspect holdout model performance or tune on test errors.
- No weather forecast archive covering these dates has been established.
- No customer elasticity, appliance constraints, network topology or demographic
  ground truth is available. Later simulation must state these assumptions.
- No software redistribution licence has been chosen by the team.
- Only Day 1 functionality is implemented. A historical chart is not a finished app.
