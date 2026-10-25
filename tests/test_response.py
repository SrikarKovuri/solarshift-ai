from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from solarshift.substation.response import Scenario,prob_exceed,price_multiplier,effective_response,simulate,EVENING,MIDDAY,LATE
from solarshift.substation.day5 import fit_calibration,daily_table,check_scenario


def test_theo_probability_formula_and_tails():
    q=np.tile([10.,20.,30.],(5,1)); t=np.array([-100,10,20,30,100])
    np.testing.assert_allclose(prob_exceed(q,t),[.99,.9,.5,.1,.01])
    assert np.isfinite(prob_exceed([[1,1,1]],[1])).all()
    with pytest.raises(ValueError):prob_exceed([[2,1,3]],[1])


def test_price_boundaries_and_rejection():
    np.testing.assert_allclose(price_multiplier([0,.299999,.3,.65,1]),[1,1,1,1.25,1.5])
    for bad in [-.1,1.1,np.nan,np.inf]:
        with pytest.raises(ValueError):price_multiplier(bad)


def test_groups_exemptions_and_individual_caps():
    p=Scenario(response_rate=1,battery_factor=100)
    assert effective_response(1.5,p)==pytest.approx(.9)
    assert effective_response(1.5,replace(p,exempt_share=1))==0
    with pytest.raises(ValueError):Scenario(share_solar=.1,share_battery=.2).validate()
    for kw in [dict(response_rate=-1),dict(flexible_fraction=2),dict(battery_factor=np.inf)]:
        with pytest.raises(ValueError):Scenario(**kw).validate()


@pytest.mark.parametrize('params,m',[ (Scenario(response_rate=0),1.5),(Scenario(exempt_share=1),1.5),(Scenario(),1.) ])
def test_zero_response(params,m):
    x=np.arange(48,dtype=float)[None,:]-10
    y,info=simulate(x,m,100,params)
    np.testing.assert_array_equal(x,y)
    assert info['moved_mwh'][0]==0


def test_known_energy_split_and_signed_exports():
    x=np.full((1,48),10.);x[:,MIDDAY]=-4;x[:,32]=-2
    p=Scenario(residential_share=1,flexible_fraction=1,response_rate=1,exempt_share=0,share_battery=0)
    y,info=simulate(x,1.5,100,p)
    assert info['moved_mwh'][0]==pytest.approx(45)
    assert y[0,32]==-2
    assert (y[:,MIDDAY]-x[:,MIDDAY]).sum()*.5==pytest.approx(22.5)
    assert (y[:,LATE]-x[:,LATE]).sum()*.5==pytest.approx(22.5)
    assert abs(info['energy_error_mwh'][0])<1e-10


def test_capacity_limited_shift_leaves_unshiftable_load():
    x=np.full((1,48),10.);x[:,MIDDAY]=9;x[:,LATE]=9
    p=Scenario(residential_share=1,flexible_fraction=1,response_rate=1,exempt_share=0)
    y,info=simulate(x,1.5,10,p)
    assert info['moved_mwh'][0]==pytest.approx(4)
    assert info['capacity_limited'][0]
    assert y.max()<=10
    assert y[:,EVENING].sum()>0
    check_scenario(x,y,info,np.array([10.]))


def test_rebound_can_create_new_whole_day_peak():
    x=np.full((1,48),9.);x[:,EVENING]=10
    y,info=simulate(x,1.5,30,Scenario(residential_share=1,flexible_fraction=1,response_rate=1,exempt_share=0))
    assert y.max()>x.max()
    assert y[:,EVENING].max()<x[:,EVENING].max()
    check_scenario(x,y,info,np.array([30.]))


def test_random_signed_flows_all_sweep_boundaries():
    rng=np.random.default_rng(2112);x=rng.uniform(-10,40,(30,48));m=rng.uniform(1,1.5,30);cap=rng.uniform(0,50,30)
    for mid in [0,.5,1]:
        for r in [0,.1,.3,1]:
            for f in [.05,.25,1]:
                y,info=simulate(x,m,cap,Scenario(response_rate=r,flexible_fraction=f,to_midday=mid))
                check_scenario(x,y,info,cap)
                assert (info['effective_response']<=.9+1e-12).all()
                assert ((x[:,EVENING]<0)==(y[:,EVENING]<0)).all()


def test_weighted_destinations_and_invalid_inputs():
    x=np.full((1,48),10.)
    y,info=simulate(x,1.5,100,midday_weights=[1]+[0]*9,late_weights=[0,0,0,1])
    np.testing.assert_array_equal(y[:,MIDDAY[1:]],x[:,MIDDAY[1:]])
    check_scenario(x,y,info,np.array([100.]))
    for weights in [[0]*10,[-1]+[1]*9,[1,2]]:
        with pytest.raises(ValueError):simulate(x,1.5,100,midday_weights=weights)
    with pytest.raises(ValueError):simulate(np.full((1,48),np.nan),1.1,100)
    with pytest.raises(ValueError):simulate(x,1.1,-1)


def test_later_events_cannot_change_calibration():
    d=pd.DataFrame({'date':pd.to_datetime(['2023-05-01','2023-10-31','2023-11-01','2024-04-30']),
                    'event':[False,True,False,True],'p_raw':[.1,.8,.2,.9]})
    a=fit_calibration(d)
    d.loc[d.date>='2023-11-01','event']=True
    assert fit_calibration(d)==a
    assert a['fit_end']=='2023-10-31'


def test_incomplete_evening_and_reserved_dates_rejected():
    v=pd.DataFrame({'site':'S','date':pd.Timestamp('2023-06-01'),'hh':np.arange(48),'split':'val'})
    for c in ['actual_magnitude_mw','q10_mw','q50_mw','q90_mw','weekly_mw','yesterday_mw']:v[c]=1.
    assert len(daily_table(v,pd.Series({'S':1.})))==1
    assert daily_table(v[v.hh!=32],pd.Series({'S':1.})).empty
    v['date']=pd.Timestamp('2024-05-01')
    with pytest.raises(ValueError):daily_table(v,pd.Series({'S':1.}))


def test_warning_inputs_do_not_use_actual_target():
    v=pd.DataFrame({'site':'S','date':pd.Timestamp('2023-06-01'),'hh':np.arange(48),'split':'val'})
    for c in ['actual_magnitude_mw','q10_mw','q50_mw','q90_mw','weekly_mw','yesterday_mw']:v[c]=1.
    before=daily_table(v,pd.Series({'S':2.}))
    v['actual_magnitude_mw']=999.
    after=daily_table(v,pd.Series({'S':2.}))
    np.testing.assert_array_equal(before.p_raw,after.p_raw)
    assert before.event.iloc[0]!=after.event.iloc[0]
