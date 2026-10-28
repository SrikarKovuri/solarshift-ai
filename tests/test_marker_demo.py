from pathlib import Path
import importlib.util
import json
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prepare_demo',ROOT/'scripts/prepare_demo.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_bundled_forecasts_have_no_raw_readings_and_hashes_match():
    assets=ROOT/'demo/assets';manifest=json.loads((assets/'manifest.json').read_text())
    for name,h in manifest['hashes'].items():assert module.sha256(assets/name)==h
    f=pd.read_parquet(assets/'forecasts.parquet')
    assert len(f)==manifest['intervals']
    assert not {'signed_actual_mw','actual_magnitude_mw','weekly_mw','yesterday_mw'}&set(f.columns)
    assert f.groupby(['site','date']).hh.agg(lambda h:sorted(h)==list(range(48))).all()


def test_bad_archive_rejected_before_processing(tmp_path):
    archive=tmp_path/'invalid.zip';archive.write_text('not an archive')
    with pytest.raises(ValueError,match='checksum'):module.prepare(tmp_path/'out',archive)


@pytest.mark.skipif(not (ROOT/'results/generated/marker_demo/demo_manifest.json').exists(),reason='Run marker preparation first')
def test_marker_replay_matches_full_saved_predictions_and_ui(monkeypatch):
    marker=ROOT/'results/generated/marker_demo'
    if (ROOT/'results/generated/substation_day4/validation_forecasts.parquet').exists():
        f=pd.read_parquet(marker/'substation_day4/validation_forecasts.parquet')
        v=pd.read_parquet(ROOT/'results/generated/substation_day4/validation_forecasts.parquet')
        match=f.merge(v,on=['site','date','hh'],suffixes=('_demo','_full'),validate='one_to_one')
        assert len(match)==len(f)
        for col in ['actual_magnitude_mw','signed_actual_mw','weekly_mw','yesterday_mw','q50_mw']:
            np.testing.assert_allclose(match[col+'_demo'],match[col+'_full'],rtol=0,atol=1e-6)
    monkeypatch.setenv('SOLARSHIFT_RESULTS',str(marker))
    app=AppTest.from_file(str(ROOT/'streamlit_app.py'),default_timeout=30).run()
    assert not app.exception and not app.error
    assert len(app.selectbox(key='site').options)==3
    assert 'Marker walkthrough' in app.info[0].value
    assert float(next(m.value for m in app.metric if m.label=='Displaced energy').split()[0])>0
