"""Reload selected models and compare on exactly the saved persistence benchmark."""

import argparse
from datetime import datetime, timezone
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from solarshift.data.common import sha256, write_json
from solarshift.models.boosted import KEYS, read_config, load_development, load_model, predict_nonnegative
from .baseline import metric_rows
from .metrics import aggregate_complete_days


def improvement(baseline, learned):
    return None if baseline == 0 else 100 * (baseline - learned) / baseline


def check_baseline(predictions, baseline, expected_manifest_hash, baseline_summary):
    if baseline_summary['feature_manifest_sha256'] != expected_manifest_hash:
        raise ValueError('Baseline used a different feature manifest; rerun baseline')
    if baseline.duplicated(KEYS).any() or predictions.duplicated(KEYS).any():
        raise ValueError('Duplicate comparison keys')
    a, b = predictions.sort_values(KEYS).reset_index(drop=True), baseline.sort_values(KEYS).reset_index(drop=True)
    if not a[KEYS].equals(b[KEYS]):
        raise ValueError('Baseline and model eligibility masks differ')
    if not np.array_equal(a.actual_kwh, b.actual_kwh) or not np.array_equal(a.baseline_kwh, b.predicted_kwh):
        raise ValueError('Baseline or actual values changed')


def comparison_rows(predictions, cohort):
    records = []
    for name, column in [('weekly_persistence', 'baseline_kwh'), ('xgboost', 'predicted_kwh')]:
        frame = predictions.drop(columns=['predicted_kwh']).rename(columns={column: 'predicted_kwh'}) if column == 'baseline_kwh' else predictions
        rows = metric_rows(frame, 'household_interval_weighted')
        rows += metric_rows(aggregate_complete_days(frame, len(cohort)), 'complete_cohort_sum')
        records.extend([{'model': name, **row} for row in rows])
    lookup = {(r['scope'], r['channel'], r['window']): r for r in records if r['model'] == 'weekly_persistence'}
    for record in records:
        baseline = lookup[record['scope'], record['channel'], record['window']]
        record['mae_improvement_percent'] = improvement(baseline['mae_kwh'], record['mae_kwh'])
        record['rmse_improvement_percent'] = improvement(baseline['rmse_kwh'], record['rmse_kwh'])
    return records


def write_report(predictions, summary, output):
    cohort = summary['cohort']
    first = cohort[0]
    chosen = predictions[predictions.customer.eq(first)]
    dates = chosen.groupby(['source_date', 'channel']).size().unstack(fill_value=0)
    day = dates.index[(dates == 48).all(axis=1)][0]
    sample = chosen[chosen.source_date.eq(day)]
    fig = make_subplots(rows=4, cols=2, vertical_spacing=0.09, horizontal_spacing=0.12,
        subplot_titles=['Demand · example day', 'Solar · example day', 'Demand · error by time', 'Solar · error by time',
                        'Demand · error by household', 'Solar · error by household', 'Demand · residual distribution', 'Solar · residual distribution'])
    styles = [('Actual', 'actual_kwh', '#e4eaf6', 'solid'), ('Weekly persistence', 'baseline_kwh', '#f6b96a', 'dot'),
              ('XGBoost', 'predicted_kwh', '#9b91ff', 'solid')]
    residual_rows = []
    for col, channel in enumerate(['GC', 'GG'], 1):
        example = sample[sample.channel.eq(channel)].sort_values('slot')
        all_rows = predictions[predictions.channel.eq(channel)]
        for name, field, color, dash in styles:
            fig.add_trace(go.Scatter(x=(example.slot - 1) / 2, y=example[field] * 2, name=name,
                legendgroup=name, showlegend=col == 1, line={'color': color, 'dash': dash}), row=1, col=col)
            if field == 'actual_kwh':
                continue
            residual = all_rows[field] - all_rows.actual_kwh
            detail = all_rows.assign(absolute_error=residual.abs())
            slot = detail.groupby('slot').absolute_error.mean()
            household = detail.groupby('customer').absolute_error.mean()
            fig.add_trace(go.Scatter(x=(slot.index - 1) / 2, y=slot, name=name, legendgroup=name,
                showlegend=False, line={'color': color, 'dash': dash}), row=2, col=col)
            fig.add_trace(go.Bar(x=household.index.astype(str), y=household, name=name, legendgroup=name,
                showlegend=False, marker_color=color), row=3, col=col)
            # Fixed shared 0.1-kWh bins with explicit overflow. Every residual is counted.
            edges = np.r_[-np.inf, np.arange(-2, 2.01, 0.1), np.inf]
            counts, _ = np.histogram(residual, bins=edges)
            centres = np.r_[-2.05, (edges[1:-2] + edges[2:-1]) / 2, 2.05]
            labels = ['< −2'] + [f'{a:.1f} to {b:.1f}' for a, b in zip(edges[1:-2], edges[2:-1])] + ['≥ 2']
            fig.add_trace(go.Bar(x=centres, y=counts / len(residual), text=labels, textposition='none', name=name, legendgroup=name,
                showlegend=False, marker_color=color, opacity=0.7,
                hovertemplate='%{text} kWh<br>Fraction: %{y:.3%}<extra>%{fullData.name}</extra>'), row=4, col=col)
            residual_rows.append({'channel': channel, 'model': name, 'n': len(residual),
                                  'mean_error_kwh': float(residual.mean()),
                                  **{f'p{p}_kwh': float(residual.quantile(p / 100)) for p in [1, 5, 50, 95, 99]}})
        fig.update_yaxes(title_text='Average power (kW)', row=1, col=col)
        for row in [2, 3]:
            fig.update_yaxes(title_text='MAE (kWh / half-hour)', row=row, col=col)
        fig.update_xaxes(title_text='Local hour', row=2, col=col)
        fig.update_xaxes(title_text='Household ID', type='category', row=3, col=col)
        fig.update_xaxes(title_text='Predicted − observed (kWh)', row=4, col=col)
        fig.update_yaxes(title_text='Fraction of all intervals', row=4, col=col)
    fig.update_layout(template='plotly_dark', height=1450, paper_bgcolor='#10131e', plot_bgcolor='#171d2d',
                      margin={'t': 70, 'b': 80}, legend={'orientation': 'h', 'y': 1.04}, barmode='group', font={'family': 'Arial'})
    pd.DataFrame(residual_rows).to_csv(output / 'residual_summary.csv', index=False)
    metrics = pd.DataFrame(summary['metrics'])
    display = metrics[['model', 'scope', 'channel', 'window', 'n', 'mae_kwh', 'rmse_kwh', 'mae_improvement_percent']]
    display = display.replace({'model': {'weekly_persistence': 'Weekly persistence', 'xgboost': 'XGBoost'},
        'scope': {'household_interval_weighted': 'Household intervals', 'complete_cohort_sum': 'Community total'},
        'channel': {'GC': 'Demand (GC)', 'GG': 'Solar (GG)'},
        'window': {'full_day': 'Full day', 'evening_16_21': '16:00–21:00'}})
    display = display.rename(columns={'model': 'Model', 'scope': 'Aggregation', 'channel': 'Target', 'window': 'Window',
        'n': 'Intervals', 'mae_kwh': 'MAE (kWh)', 'rmse_kwh': 'RMSE (kWh)', 'mae_improvement_percent': 'MAE improvement (%)'})
    table = display.to_html(index=False, float_format=lambda v: f'{v:.6f}', na_rep='Undefined')
    cards = ''
    for channel, title in [('GC', 'Demand · evening'), ('GG', 'Solar · full day')]:
        window = 'evening_16_21' if channel == 'GC' else 'full_day'
        row = metrics[(metrics.model == 'xgboost') & (metrics.scope == 'household_interval_weighted') & (metrics.channel == channel) & (metrics.window == window)].iloc[0]
        value = 'Undefined' if pd.isna(row.mae_improvement_percent) else f'{row.mae_improvement_percent:.2f}%'
        cards += f'<article><span>{title}</span><strong>{value}</strong><span>MAE reduction vs weekly persistence</span></article>'
    carbon = summary['carbon']
    carbon_text = (f"{carbon['emissions'] * 1000:.4f} g CO₂e and {carbon['energy_consumed']:.6f} kWh estimated for the search. "
                   if carbon['status'] == 'estimated' else 'Training carbon estimate unavailable. ')
    if carbon['status'] == 'estimated':
        carbon_text += f"CodeCarbon uses an assumed {carbon['assumed_cpu_tdp_w']:g} W CPU TDP (effective {carbon['cpu_power']:g} W) and {carbon['ram_power']:g} W RAM, with an Australian country-average factor. "
    carbon_text += 'This is not measured wall power or an estimate of energy-system savings.'
    chart = fig.to_html(full_html=False, include_plotlyjs=True, config={'responsive': True, 'displaylogo': False})
    page = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SolarShift · Trained forecasts</title><style>
body{margin:0;background:#10131e;color:#e4eaf6;font:15px Arial}main{max-width:1400px;margin:auto;padding:28px}h1{font-size:34px}h2{margin-top:36px}p{max-width:1000px;color:#bcc7dc;line-height:1.6}.eyebrow{color:#a59aff;text-transform:uppercase;letter-spacing:.14em}.cards{display:flex;gap:20px;flex-wrap:wrap}article{background:#1b2235;padding:22px;border:1px solid #384360;border-radius:12px;flex:1;min-width:230px}article span{display:block;color:#c6cee0}strong{display:block;font-size:38px;margin:12px 0;color:#b7adff}.chart,.table{overflow-x:auto}.plotly-graph-div{min-width:1050px}table{border-collapse:collapse;font-size:13px;width:100%}td,th{border:1px solid #36405a;padding:10px;text-align:right}th{color:#b7adff}code{color:#b7adff}.note{padding:16px;border-left:3px solid #f6b96a;background:#1b2235}
</style></head><body><main><p class="eyebrow">SolarShift AI · Modelling milestone</p><h1>Trained forecasts, measured against persistence</h1>'''
    page += f'<p>Validation: {predictions.source_date.min().date()}–{predictions.source_date.max().date()} · {len(cohort)} training-selected households · {len(predictions):,} predictions across demand and solar.</p>'
    page += '<p class="note">These validation results were used to select the models. The final test year remains reserved. The 15% evening-demand improvement is an aspirational benchmark; passing it here does not establish final-test performance or simulated savings.</p>'
    demand = metrics[(metrics.model == 'xgboost') & (metrics.scope == 'household_interval_weighted') & (metrics.channel == 'GC') & (metrics.window == 'evening_16_21')].iloc[0].mae_improvement_percent
    if pd.notna(demand):
        outcome = 'meets' if demand >= 15 else 'falls short of'
        page += f'<p>Measured evening-demand MAE reduction: <b>{demand:.2f}%</b>. This {outcome} the 15% target on validation.</p>'
    page += '<div class="cards">' + cards + '</div>'
    page += f'<h2>Forecasts and error diagnostics</h2><p>Example: household {first}, {day.date()} (first shared eligible date, chosen without ranking errors). Hover, zoom and toggle series. Scroll charts sideways in narrow windows. Residual tails are included in the outer bins.</p><div class="chart" tabindex="0">' + chart + '</div>'
    page += '<h2>Full validation comparison</h2><p>Positive improvement means lower error; negative values mean worse. Household metrics weight intervals equally. Community errors sum the complete fixed cohort before calculating errors. GC excludes controlled load. Full-day PV includes night-time zeros.</p><div class="table">' + table + '</div>'
    page += '<h2>Training footprint estimate</h2><p>' + html.escape(carbon_text) + '</p>'
    page += '<h2>Generate a different day</h2><p>Use the saved models to create a 48-interval forecast for each target:</p><p><code>python -m solarshift.models.forecast --customer ' + str(first) + ' --date ' + str(day.date()) + '</code></p><p>The command lists supported dates with <code>--list</code>. Pricing, response simulation, SHAP and the integrated application follow in later milestones.</p></main></body></html>'
    (output / 'model_report.html').write_text(page)


def evaluate(path):
    config = read_config(path)
    experiment = config['experiment']
    output = experiment['output_dir']
    frame, manifest, forecast = load_development(experiment['forecast_config'])
    training = json.loads((output / 'training_summary.json').read_text())
    manifest_hash = sha256(forecast['output_dir'] / 'manifest.json')
    if training['config_sha256'] != sha256(Path(path)) or training['feature_manifest_sha256'] != manifest_hash:
        raise ValueError('Model experiment or feature manifest changed; retrain explicitly')
    parts = []
    for channel in ['GC', 'GG']:
        selected = frame[frame.channel.eq(channel) & frame.split.eq('validation')]
        model, metadata = load_model(output / channel, channel)
        if metadata != training['selected'][channel] or metadata['feature_manifest_sha256'] != manifest_hash:
            raise ValueError('Model metadata does not match experiment')
        result = selected[KEYS + ['interval_start', 'issued_at', 'energy_kwh']].rename(columns={'energy_kwh': 'actual_kwh'})
        result['baseline_kwh'] = selected.lag_7d_kwh.to_numpy()
        result['predicted_kwh'] = predict_nonnegative(model, selected)
        parts.append(result)
    predictions = pd.concat(parts, ignore_index=True).sort_values(KEYS).reset_index(drop=True)
    baseline = pd.read_parquet(forecast['results_dir'] / 'validation_predictions.parquet')
    baseline_summary = json.loads((forecast['results_dir'] / 'summary.json').read_text())
    check_baseline(predictions, baseline, manifest_hash, baseline_summary)
    records = comparison_rows(predictions, manifest['cohort'])
    predictions.to_parquet(output / 'validation_predictions.parquet', index=False)
    pd.DataFrame(records).to_csv(output / 'metrics.csv', index=False)
    households = []
    for customer, group in predictions.groupby('customer'):
        households.extend([{'customer': int(customer), **r} for r in comparison_rows(group, [customer])
                           if r['scope'] == 'household_interval_weighted'])
    pd.DataFrame(households).to_csv(output / 'household_metrics.csv', index=False)
    summary = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'partition': 'validation',
               'test_evaluated': False, 'cohort': manifest['cohort'], 'predictions': len(predictions),
               'feature_manifest_sha256': manifest_hash, 'training_summary_sha256': sha256(output / 'training_summary.json'),
               'predictions_sha256': sha256(output / 'validation_predictions.parquet'),
               'metrics': records, 'carbon': training['carbon'], 'selected_candidates': {k: v['selected']['candidate'] for k, v in training['selected'].items()},
               'validation_used_for_selection': True, 'prediction_policy': 'clip_lower_zero',
               'identical_baseline_mask_verified': True}
    write_json(output / 'summary.json', summary)
    write_report(predictions, summary, output)
    print(pd.DataFrame(records).to_string(index=False), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='configs/models.toml')
    args = parser.parse_args()
    evaluate(args.config)


if __name__ == '__main__':
    main()
