"""Evaluate weekly persistence on validation dates; final-test evaluation is unavailable."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from solarshift.data.common import sha256, write_json
from solarshift.features.build import read_config
from solarshift.models.persistence import predict
from .metrics import errors, evening_mask, aggregate_complete_days


def metric_rows(frame, scope):
    records = []
    for channel, group in frame.groupby('channel'):
        for window in ['full_day', 'evening_16_21']:
            selected = group if window == 'full_day' else group[evening_mask(group)]
            if selected.empty:
                continue
            values = errors(selected.actual_kwh, selected.predicted_kwh)
            records.append({'scope': scope, 'channel': channel, 'window': window, **values,
                            'mae_kw': values['mae_kwh'] * 2, 'rmse_kw': values['rmse_kwh'] * 2})
    return records


def report_chart(predictions, records, output, cohort):
    first = cohort[0]
    sample = predictions[predictions.customer == first]
    dates = sample.groupby(['source_date', 'channel']).size().unstack(fill_value=0)
    shared = dates.index[(dates == 48).all(axis=1)]
    if shared.empty:
        raise ValueError('No shared complete demand/PV day for the example chart')
    day = shared[0]
    sample = sample[sample.source_date == day].sort_values('slot')
    figure = make_subplots(rows=2, cols=2, subplot_titles=[
        f'Household {first} · general consumption', f'Household {first} · gross PV',
        'Validation MAE by local interval', 'Validation MAE by household'])
    for channel, col, color in [('GC', 1, '#b7a1ff'), ('GG', 2, '#56dfb0')]:
        selected = sample[sample.channel == channel]
        for name, column, dash in [('Observed', 'actual_kwh', 'solid'), ('Weekly persistence', 'predicted_kwh', 'dot')]:
            figure.add_trace(go.Scatter(x=selected.interval_start, y=selected[column] * 2,
                name=f'{channel} · {name}', line={'color': color, 'dash': dash}), row=1, col=col)
        all_rows = predictions[predictions.channel == channel].copy()
        all_rows['absolute_error'] = (all_rows.predicted_kwh - all_rows.actual_kwh).abs()
        hourly = all_rows.groupby('slot').absolute_error.mean()
        figure.add_trace(go.Scatter(x=(hourly.index - 1) / 2, y=hourly.values,
                                   name=f'{channel} MAE', line_color=color), row=2, col=1)
        household = all_rows.groupby('customer').absolute_error.mean()
        figure.add_trace(go.Bar(x=household.index.astype(str), y=household.values,
                               name=f'{channel} household MAE', marker_color=color), row=2, col=2)
        figure.update_yaxes(title_text='Average power (kW)', row=1, col=col)
    figure.update_yaxes(title_text='MAE (kWh / half-hour)', row=2)
    figure.update_xaxes(title_text='Local hour', row=2, col=1)
    figure.update_xaxes(title_text='Household ID', type='category', row=2, col=2)
    figure.update_layout(template='plotly_dark', height=840, paper_bgcolor='#10131e', plot_bgcolor='#151b29',
                        title=f'SolarShift · Weekly persistence benchmark<br><sup>Validation only · example {day.date()} · {len(cohort)} households</sup>',
                        margin={'t': 100, 'b': 100}, legend={'orientation': 'h', 'y': -0.15}, font={'family': 'Arial'})
    display = pd.DataFrame(records).replace({
        'scope': {'household_interval_weighted': 'Household intervals', 'complete_cohort_sum': 'Community total'},
        'channel': {'GC': 'Demand (GC)', 'GG': 'PV (GG)'},
        'window': {'full_day': 'Full day', 'evening_16_21': '16:00–21:00'}})
    display = display.rename(columns={'scope': 'Aggregation', 'channel': 'Target', 'window': 'Window',
        'n': 'Intervals', 'mae_kwh': 'MAE (kWh)', 'rmse_kwh': 'RMSE (kWh)',
        'mae_kw': 'MAE (kW)', 'rmse_kw': 'RMSE (kW)'})
    table = display.to_html(index=False, float_format=lambda x: f'{x:.6f}')
    chart = figure.to_html(full_html=False, include_plotlyjs=True, config={'displaylogo': False, 'responsive': True})
    html = '<!doctype html><html><head><meta charset="utf-8"><title>SolarShift · Forecast benchmark</title>'
    html += '<meta name="viewport" content="width=device-width, initial-scale=1"><style>body{margin:0;background:#10131e;color:#e8edf5;font:15px Arial}main{max-width:1400px;margin:auto;padding:24px}h1{font-size:28px}p{line-height:1.6;color:#bac4d6}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:12px;border:1px solid #303a50;text-align:right}.table{overflow-x:auto}th{color:#b7a1ff}</style></head><body><main>'
    html += '<h1>Forecasting foundation</h1><p>Measured validation performance, January–June 2012. GC excludes controlled load; GG is gross PV. The final test year is reserved. Prices, response simulations and XGBoost are not part of this benchmark.</p>'
    html += '<style>.chart{overflow-x:auto}.chart .plotly-graph-div{min-width:1000px}.chart-hint{font-size:13px}</style>'
    html += '<p class="chart-hint">Hover for values, drag to zoom, and click legend entries to toggle series. On narrow screens, scroll the chart sideways.</p>'
    html += '<div class="chart" tabindex="0" role="region" aria-label="Interactive forecast charts; scroll horizontally on narrow screens">' + chart + '</div>'
    html += '<h2>Validation metrics</h2><p>Household rows weight each eligible interval equally. Community metrics require every selected household for all 48 intervals of a day. kW errors are twice interval-kWh errors.</p><div class="table">' + table
    html += '</div><p>This is a deterministic pilot cohort selected using training coverage only. It is not a representative population sample. Missing required history excludes complete forecast days; coverage is recorded separately.</p></main></body></html>'
    (output / 'baseline_report.html').write_text(html)


def evaluate(path):
    config = read_config(path)
    root = config['output_dir']
    manifest = json.loads((root / 'manifest.json').read_text())
    if manifest['config_sha256'] != sha256(Path(path)):
        raise ValueError('Forecast configuration changed; rebuild the feature dataset')
    parts = []
    for record in manifest['files']:
        source = root / record['filename']
        if sha256(source) != record['sha256']:
            raise ValueError(f'Feature file hash mismatch: {source.name}')
        frame = pd.read_parquet(source, filters=[('split', '==', 'validation')])
        if frame.empty or not frame.source_date.between(config['validation_start'], config['validation_end']).all():
            raise ValueError('Evaluation requires nonempty validation-only dates')
        result = frame[['customer', 'channel', 'source_date', 'slot', 'interval_start', 'issued_at', 'energy_kwh']].rename(columns={'energy_kwh': 'actual_kwh'})
        result['predicted_kwh'] = predict(frame)
        parts.append(result)
    predictions = pd.concat(parts, ignore_index=True)
    output = config['results_dir']; output.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(output / 'validation_predictions.parquet', index=False)
    aggregate = aggregate_complete_days(predictions, len(manifest['cohort']))
    records = metric_rows(predictions, 'household_interval_weighted') + metric_rows(aggregate, 'complete_cohort_sum')
    pd.DataFrame(records).to_csv(output / 'metrics.csv', index=False)
    per_household = []
    for customer, frame in predictions.groupby('customer'):
        per_household.extend([{'customer': int(customer), **row} for row in metric_rows(frame, 'household')])
    pd.DataFrame(per_household).to_csv(output / 'household_metrics.csv', index=False)
    expected_days = len(pd.date_range(config['validation_start'], config['validation_end']))
    coverage = predictions.groupby(['customer', 'channel']).source_date.nunique().rename('eligible_days').reset_index()
    coverage['expected_calendar_days'] = expected_days
    coverage['coverage_fraction'] = coverage.eligible_days / expected_days
    coverage.to_csv(output / 'validation_coverage.csv', index=False)
    summary = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'model': 'weekly_seasonal_persistence',
               'partition': 'validation', 'test_evaluated': False, 'cohort': manifest['cohort'],
               'feature_manifest_sha256': sha256(root / 'manifest.json'), 'metrics': records,
               'validation_predictions': len(predictions), 'validation_calendar_days': expected_days,
               'eligible_channel_days': len(predictions) // 48,
               'complete_cohort_days_by_channel': {k: int(v) for k, v in aggregate.groupby('channel').source_date.nunique().items()},
               'weighting': 'Pooled: equal weight per eligible household interval. Community: sum across fixed cohort on complete days.',
               'eligibility': 'Both baseline and later learned-model comparisons must use these identical complete-day masks.',
               'feature_policy': 'Previous-day observations only when available; otherwise 2-day lag. Rolling mean uses days -2 through -8.'}
    write_json(output / 'summary.json', summary)
    report_chart(predictions, records, output, manifest['cohort'])
    print(pd.DataFrame(records).to_string(index=False))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='configs/forecast.toml')
    args = parser.parse_args()
    evaluate(args.config)


if __name__ == '__main__':
    main()
