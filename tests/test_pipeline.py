import json
from pathlib import Path

import pandas as pd

from solarshift.data.prepare import prepare
from solarshift.data.explore import explore


def test_pipeline_writes_traceable_outputs_and_real_chart(write_csv, tmp_path):
    source = write_csv()
    config_dir = tmp_path / 'configs'
    config_dir.mkdir()
    config = config_dir / 'data.toml'
    config.write_text(f'''[data]
raw_dir = "."
output_dir = "processed"
results_dir = "results"
files = ["{source.name}"]
source_url = "synthetic-test-fixture"
timezone = "Australia/Sydney"
exclude_dst_transition_days = true
primary_demand_channel = "GC"
[explore]
customer = 1
start = "2010-07-01"
days = 1
''')
    result = prepare(config)
    assert result['accepted_intervals'] == 96
    rows = pd.read_parquet(tmp_path / 'processed' / 'intervals_2010_2011.parquet')
    assert rows.energy_kwh.sum() == 48
    assert set(rows.channel) == {'GC', 'GG'}
    assert (tmp_path / 'processed' / 'quality_report.json').exists()
    # A leftover file from an older configuration must not contaminate the chart.
    rows.to_parquet(tmp_path / 'processed' / 'intervals_stale.parquet', index=False)
    chart = explore(config)
    html = chart.read_text()
    assert 'Historical measurements' in html
    assert 'plotly.js' in html
    stats = json.loads((tmp_path / 'results' / 'exploration_summary.json').read_text())
    assert stats['energy_kwh_by_channel'] == {'GC': 24.0, 'GG': 24.0}
