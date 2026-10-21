"""Create a self-contained interactive historical chart and descriptive statistics."""

import argparse
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .common import read_config, write_json


def explore(config_path: str | Path, customer=None, start=None, days=None) -> Path:
    config = read_config(config_path)
    data, settings = config['data'], config['explore']
    customer = settings['customer'] if customer is None else customer
    start = pd.Timestamp(settings['start'] if start is None else start)
    days = settings['days'] if days is None else days
    if days < 1 or days > 366:
        raise ValueError('days must be between 1 and 366')
    end = start + pd.Timedelta(days=days)
    manifest_path = data['output_dir'] / 'quality_report.json'
    if not manifest_path.exists():
        raise FileNotFoundError('No quality manifest. Run solarshift.data.prepare first.')
    manifest = json.loads(manifest_path.read_text())
    paths = [data['output_dir'] / name for name in manifest['outputs']
             if name.startswith('intervals_') and name.endswith('.parquet')]
    if not paths:
        raise FileNotFoundError('No processed interval files. Run solarshift.data.prepare first.')
    frame = pd.concat([pd.read_parquet(p, filters=[('customer', '==', customer),
                      ('source_date', '>=', start), ('source_date', '<', end)]) for p in paths])
    if frame.empty:
        raise ValueError('No accepted readings for this household/date range; inspect the quality report.')
    frame = frame.sort_values('interval_start')
    chart = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.13,
                          subplot_titles=['Half-hour average power · kW', 'Daily measured energy · kWh'])
    names = {'GC': 'General consumption (excludes CL)', 'GG': 'Gross PV generation', 'CL': 'Controlled load'}
    colors = {'GC': '#b7a1ff', 'GG': '#56dfb0', 'CL': '#f4bd6b'}
    for channel in ['GC', 'GG', 'CL']:
        series = frame[frame.channel == channel].copy()
        if series.empty:
            continue
        # Reindex solely for visual gaps. Missing points remain NaN, never imputed.
        grid = pd.date_range(start.tz_localize('Australia/Sydney'),
                             end.tz_localize('Australia/Sydney'), freq='30min', inclusive='left')
        line = series.set_index('interval_start')['average_power_kw'].reindex(grid)
        chart.add_trace(go.Scatter(x=line.index, y=line.values, name=names[channel], mode='lines',
                                   line={'color': colors[channel], 'width': 1.5}, connectgaps=False,
                                   hovertemplate='%{x}<br>%{y:.3f} kW<extra>%{fullData.name}</extra>'), row=1, col=1)
        daily = series.groupby('source_date')['energy_kwh'].sum()
        chart.add_trace(go.Bar(x=daily.index, y=daily.values, name=names[channel],
                               marker_color=colors[channel], showlegend=False,
                               hovertemplate='%{x|%d %b %Y}<br>%{y:.3f} kWh<extra></extra>'), row=2, col=1)
    chart.update_layout(template='plotly_dark', paper_bgcolor='#10131e', plot_bgcolor='#151b29',
                         font={'family': 'Arial', 'color': '#e8edf5'}, height=800,
                         title={'text': f'SolarShift AI · Historical measurements<br><sup>Household {customer} · Australia/Sydney local time · no forecasts or simulated results</sup>'},
                         legend={'orientation': 'h', 'y': -0.15}, margin={'t': 110, 'b': 110},
                         hovermode='x unified', barmode='group')
    chart.update_yaxes(title_text='kW', row=1, col=1)
    chart.update_yaxes(title_text='kWh', row=2, col=1)
    destination = data['results_dir']
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / f'household_{customer}_{start.date()}.html'
    html = chart.to_html(include_plotlyjs=True, config={'displaylogo': False, 'responsive': True})
    html = html.replace('<head>', '<head><title>SolarShift AI · Historical data explorer</title>'
                        '<style>body{margin:0;background:#10131e}</style>')
    target.write_text(html)
    statistics = {'customer': customer, 'start': str(start.date()), 'end_exclusive': str(end.date()),
                  'accepted_intervals': len(frame), 'interpretation': 'Historical observations only; missing channels are not zero.',
                  'energy_kwh_by_channel': {k: float(v) for k, v in frame.groupby('channel').energy_kwh.sum().items()}}
    write_json(destination / 'exploration_summary.json', statistics)
    print(target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='configs/data.toml')
    parser.add_argument('--customer', type=int)
    parser.add_argument('--start')
    parser.add_argument('--days', type=int)
    args = parser.parse_args()
    explore(args.config, args.customer, args.start, args.days)


if __name__ == '__main__':
    main()
