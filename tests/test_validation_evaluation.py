import numpy as np
import pandas as pd
import pytest
from solarshift.substation.evaluate import validate, cqr_adjustment, bootstrap


def fixture():
    n=28
    return pd.DataFrame(dict(site=['A']*n,date=pd.date_range('2023-11-01',periods=n),hh=[32]*n,
        split=['val']*n,actual_magnitude_mw=np.ones(n)*10,q10_mw=np.ones(n)*9,
        q50_mw=np.ones(n)*11,q90_mw=np.ones(n)*12,weekly_mw=np.ones(n)*12))


def test_reserved_and_duplicate_rejected():
    f=fixture();f.loc[0,'date']=pd.Timestamp('2024-05-01')
    with pytest.raises(ValueError):validate(f)
    with pytest.raises(ValueError):validate(pd.concat([fixture(),fixture()]))


def test_calibration_widens_for_misses_and_never_shrinks():
    f=fixture();assert cqr_adjustment(f)==0
    f['actual_magnitude_mw']=15
    assert cqr_adjustment(f)==3


def test_paired_bootstrap_known_improvement():
    result=bootstrap(fixture())
    assert result['improvement_pct']==50
    assert result['ci95_pct']==[50,50]
    assert result==bootstrap(fixture())
