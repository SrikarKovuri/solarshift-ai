"""Day 6 integration API: calibrated warning plus editable historical scenario."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .forecast import validation_forecast
from .response import Scenario, prob_exceed, price_multiplier, simulate, EVENING
from .day5 import scenario_metrics


def replay_scenario(day4, day5, site, date, params=Scenario(), capacity_mw=None):
    """No early-fit or reserved-test dates; incomplete days fail explicitly.

    Returns warning metadata, before/after interval table and scenario metrics.
    Capacity may be overridden with an explicit assumed MW value.
    """
    day4,day5=Path(day4),Path(day5)
    cal=json.loads((day5/'calibration.json').read_text())
    if pd.Timestamp(date)<=pd.Timestamp(cal['fit_end']):
        raise ValueError('Date must follow the calibration fit period')
    f=validation_forecast(day4,site,date)
    threshold=float(pd.read_csv(day4/'peak_thresholds_training.csv').set_index('substation').loc[site].iloc[0])
    q=f.loc[f.hh.isin(EVENING),['q10_mw','q50_mw','q90_mw']].mean().to_numpy()[None,:]
    raw=float(prob_exceed(q,[threshold])[0]); p=float(np.interp(raw,cal['x'],cal['y']))
    m=float(price_multiplier(p))
    if capacity_mw is None:
        capacity_mw=float(pd.read_csv(day5/'scenario_capacity.csv').set_index('substation').loc[site].iloc[0])
    x=f.signed_actual_mw.to_numpy()[None,:]
    y,info=simulate(x,[m],[capacity_mw],params)
    f['simulated_signed_mw']=y[0]
    f['nonexempt_multiplier']=np.where(f.hh.isin(EVENING),m,1.)
    f['exempt_multiplier']=1.
    return {'site':site,'date':date,'raw_probability':raw,'calibrated_probability':p,
            'warning':p>=.3,'multiplier':m,'threshold_evening_magnitude_mw':threshold,
            'assumed_import_ceiling_mw':capacity_mw,'metrics':scenario_metrics(x,y,info),'intervals':f}
