"""Generate two saved-model 48-slot forecasts for a supported validation day."""

import argparse
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from solarshift.data.common import sha256, write_json
from solarshift.evaluation.baseline import metric_rows
from .boosted import read_config, load_development, select_day, load_model, predict_nonnegative, KEYS


def forecast_day(path, customer, day):
    config = read_config(path)
    experiment = config['experiment']
    frame, _, forecast = load_development(experiment['forecast_config'])
    chosen = select_day(frame, customer, day)
    output = experiment['output_dir']
    training = json.loads((output / 'training_summary.json').read_text())
    feature_hash = sha256(forecast['output_dir'] / 'manifest.json')
    if training['config_sha256'] != sha256(Path(path)) or training['feature_manifest_sha256'] != feature_hash:
        raise ValueError('Experiment config/features changed since training')
    parts = []
    figure = make_subplots(rows=2, cols=1, subplot_titles=['Demand (GC; excludes controlled load)', 'Gross solar generation (GG)'])
    for row, channel in enumerate(['GC', 'GG'], 1):
        features = chosen[chosen.channel.eq(channel)]
        model, metadata = load_model(output / channel, channel)
        if metadata != training['selected'][channel]:
            raise ValueError('Model metadata differs from saved experiment')
        result = features[KEYS + ['interval_start', 'issued_at', 'energy_kwh']].rename(columns={'energy_kwh': 'actual_kwh'})
        result['baseline_kwh'] = features.lag_7d_kwh.to_numpy()
        result['predicted_kwh'] = predict_nonnegative(model, features)
        parts.append(result)
        for label, field, colour in [('Observed', 'actual_kwh', '#dce4f6'), ('Weekly persistence', 'baseline_kwh', '#f6b96a'), ('XGBoost', 'predicted_kwh', '#9b91ff')]:
            figure.add_trace(go.Scatter(x=(result.slot - 1) / 2, y=result[field] * 2, name=label,
                legendgroup=label, showlegend=row == 1, line_color=colour), row=row, col=1)
        figure.update_yaxes(title_text='Average power (kW)', row=row, col=1)
        figure.update_xaxes(title_text='Local hour (Australia/Sydney)', row=row, col=1)
    prediction = pd.concat(parts, ignore_index=True)
    directory = output / 'forecasts'
    directory.mkdir(exist_ok=True)
    stem = f'household_{customer}_{pd.Timestamp(day).date()}'
    prediction.to_csv(directory / f'{stem}.csv', index=False)
    metrics = metric_rows(prediction, 'selected_day_only')
    write_json(directory / f'{stem}.json', {'customer': customer, 'date': day, 'partition': 'validation',
               'rows_per_target': 48, 'metrics': metrics, 'test_evaluated': False,
               'model_hashes': {ch: training['selected'][ch]['model_sha256'] for ch in ['GC', 'GG']}})
    figure.update_layout(template='plotly_dark', height=760,
        title=f'Household {customer} · {pd.Timestamp(day).date()}<br><sup>Validation example · selected using models tuned on this validation period</sup>',
        paper_bgcolor='#10131e', plot_bgcolor='#171d2d', margin={'t': 110}, legend={'orientation': 'h', 'y': -0.1})
    figure.write_html(directory / f'{stem}.html', include_plotlyjs=True, config={'displaylogo': False})
    print(prediction[['channel', 'slot', 'actual_kwh', 'baseline_kwh', 'predicted_kwh']].to_string(index=False))
    print(f'CSV, metrics and interactive chart: {directory / stem}')
    return prediction


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='configs/models.toml')
    parser.add_argument('--customer', type=int)
    parser.add_argument('--date')
    parser.add_argument('--list', action='store_true', help='List eligible dates and cohort households')
    args = parser.parse_args()
    if args.list:
        config = read_config(args.config)
        frame, manifest, _ = load_development(config['experiment']['forecast_config'])
        print('Households:', ', '.join(map(str, manifest['cohort'])))
        customer = args.customer if args.customer is not None else manifest['cohort'][0]
        frame = frame[frame.customer.eq(customer) & frame.split.eq('validation')]
        if frame.empty:
            parser.error('Household is not in the fixed cohort')
        counts = frame.groupby(['source_date', 'channel']).size().unstack(fill_value=0)
        print(f'Eligible dates for household {customer}:')
        print(', '.join(str(day.date()) for day in counts.index[(counts == 48).all(axis=1)]))
    elif args.customer is None or args.date is None:
        parser.error('Provide --customer and --date, or --list')
    else:
        forecast_day(args.config, args.customer, args.date)


if __name__ == '__main__':
    main()
