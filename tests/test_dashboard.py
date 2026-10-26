"""UI integration checks against local validation artifacts, plus isolated guards."""
from pathlib import Path
import json
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from solarshift.substation.dashboard import catalog, curve_figure

ROOT = Path(__file__).resolve().parents[1]
REAL = (ROOT/'results/generated/substation_day4/validation_forecasts.parquet').exists()


def test_catalog_excludes_incomplete_early_and_reserved_days(tmp_path):
    (tmp_path/'calibration.json').write_text(json.dumps({'fit_end':'2023-10-31'}))
    rows = []
    for date, n in [('2023-10-31',48),('2023-11-01',48),('2023-11-02',47),('2024-05-01',48)]:
        rows += [dict(site='A',date=pd.Timestamp(date),hh=h,split='val',quality_flags=0) for h in range(n)]
    pd.DataFrame(rows).to_parquet(tmp_path/'validation_forecasts.parquet')
    assert catalog(tmp_path,tmp_path).date.tolist() == ['2023-11-01']


def test_missing_data_has_actionable_error(monkeypatch,tmp_path):
    monkeypatch.setenv('SOLARSHIFT_RESULTS',str(tmp_path))
    app=AppTest.from_file(str(ROOT/'streamlit_app.py'),default_timeout=30).run()
    assert not app.exception
    assert 'Validation data unavailable' in app.error[0].value


@pytest.mark.skipif(not REAL,reason='Local generated validation artifacts required')
def test_real_replay_controls_and_units():
    app=AppTest.from_file(str(ROOT/'streamlit_app.py'),default_timeout=30).run()
    assert not app.exception
    assert not app.error
    # Select an actually activated, complete replay, not a zero-warning example.
    daily=pd.read_csv(ROOT/'results/generated/substation_day5/default_scenarios.csv')
    row=daily[daily.moved_mwh>0].iloc[0]
    app.selectbox(key='site').select(row.site).run()
    app.selectbox(key=f'date_{row.site}').select(row.date).run()
    assert not app.exception
    moved = next(m.value for m in app.metric if m.label=='Displaced energy')
    assert float(moved.split()[0]) > 0
    app.slider(key='response').set_value(0).run()
    assert next(m.value for m in app.metric if m.label=='Displaced energy')=='0.0000 MWh'
    app.slider(key='response').set_value(30).run()
    app.slider(key='exempt').set_value(100).run()
    assert next(m.value for m in app.metric if m.label=='Displaced energy')=='0.0000 MWh'
    app.checkbox(key='actuals').check().run()
    assert not app.exception
    # Overlapping shares must produce a user-facing validation error.
    next(s for s in app.slider if s.label=='Solar + battery households (%)').set_value(100).run()
    assert 'subset of solar' in app.error[0].value


@pytest.mark.skipif(not REAL,reason='Local generated validation artifacts required')
def test_chart_keeps_magnitude_and_signed_semantics_separate():
    from solarshift.substation.scenario_replay import replay_scenario
    r=replay_scenario(ROOT/'results/generated/substation_day4',ROOT/'results/generated/substation_day5', 'Aberdeen 66_11kV','2023-11-01')
    fig=curve_figure(r['intervals'],actuals=False)
    assert not any('Measured' in trace.name for trace in fig.data)
    assert fig.layout.yaxis.title.text=='Flow magnitude (MW)'
    signed=curve_figure(r['intervals'],scenario=True)
    assert signed.layout.yaxis.title.text=='Signed power (MW)'
    assert len(signed.data)==2
    assert list(signed.data[0].y)==r['intervals'].signed_actual_mw.tolist()
