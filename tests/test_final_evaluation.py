import numpy as np
import pandas as pd
import pytest
from solarshift.substation.final_evaluation import clean_test, assess
from solarshift.substation.pipeline import site_features, _site_features


def test_frozen_cleaning_preserves_sign_excludes_dst_and_does_not_fit_test():
    w=pd.DataFrame([dict(substation='A',date=pd.Timestamp(date),unit='MW',**{}) for date in ['2024-05-01','2024-10-06']])
    for j in range(96):w[j]=-(2+j/96)
    scales=pd.DataFrame([dict(substation='A',change_median=0.,change_scale=1.)])
    result=clean_test(w,scales)
    assert result[result.date.eq('2024-05-01')].mw_published.lt(0).all()
    assert result[result.date.eq('2024-10-06')].mw.isna().all()
    assert result.iloc[0].mw_published==pytest.approx(-(2+.5/96))
    with pytest.raises(ValueError):clean_test(w,scales.assign(substation='B'))


def test_test_cleaning_rejects_wrong_split():
    w=pd.DataFrame([dict(substation='A',date=pd.Timestamp('2023-11-01'),unit='MW')])
    with pytest.raises(ValueError):clean_test(w,pd.DataFrame())


def test_shared_features_preserve_validation_and_future_target_cannot_change_past():
    days=pd.date_range('2021-04-01','2024-05-03')
    g=pd.DataFrame(dict(date=np.repeat(days,48),hh=np.tile(np.arange(48),len(days))))
    g['mw']=10+g.hh/48;g['mw_published']=g.mw;g['quality_flags']=0;g['sign_available']=True
    site=dict(substation='A',lat=-33.,lon=151.)
    weather=pd.DataFrame(dict(date=np.repeat(days,24),hour=np.tile(np.arange(24),len(days)),temp=20.,tmax=25.,tmin=15.,tmean=20.))
    old=site_features(g[g.date<'2024-05-01'],site,weather)
    new=_site_features(g,site,weather,'2024-05-03')
    pd.testing.assert_frame_equal(old.reset_index(drop=True),new[new.date<'2024-05-01'].reset_index(drop=True))
    g.loc[g.date.eq('2024-05-03'),'mw']=999
    changed=_site_features(g,site,weather,'2024-05-03')
    from solarshift.substation.pipeline import FEATURES
    pd.testing.assert_frame_equal(new[FEATURES],changed[FEATURES])


def test_existing_final_run_cannot_be_overwritten(tmp_path,monkeypatch):
    from solarshift.substation import final_evaluation as final
    monkeypatch.setattr(final,'frozen_files',lambda root:[])
    out=tmp_path/'final'
    final.freeze(tmp_path,out,'Synthetic test approval; not a real run')
    with pytest.raises(FileExistsError):final.freeze(tmp_path,out,'Second record')
    (out/'run_started.json').write_text('{}')
    with pytest.raises(FileExistsError):final.run(tmp_path,tmp_path/'no_source',out)
