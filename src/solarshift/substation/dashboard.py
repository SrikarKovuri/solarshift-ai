"""Presentation helpers for validation replay; no training or test-period loading."""
import json
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go


def catalog(day4, day5):
    cal = json.loads((Path(day5) / 'calibration.json').read_text())
    f = pd.read_parquet(Path(day4) / 'validation_forecasts.parquet',
                        columns=['site', 'date', 'hh', 'split', 'quality_flags'],
                        filters=[('date', '>', pd.Timestamp(cal['fit_end'])),
                                 ('date', '<', pd.Timestamp('2024-05-01'))])
    f = f[f.split.eq('val') & f.quality_flags.eq(0)]
    days = f.groupby(['site', 'date']).hh.agg(list)
    days = days[days.map(lambda slots: sorted(slots) == list(range(48)))].reset_index()
    if days.empty:
        raise ValueError('No complete post-calibration validation days are available.')
    days['date'] = days.date.dt.strftime('%Y-%m-%d')
    return days[['site', 'date']].sort_values(['site', 'date']).reset_index(drop=True)


def curve_figure(frame, scenario=False, actuals=False, threshold=None, capacity=None):
    fig = go.Figure()
    x = frame.hh / 2
    if scenario:
        traces = [('signed_actual_mw', 'Measured signed flow', '#64748b'),
                  ('simulated_signed_mw', 'Simulated signed flow', '#0d9488')]
    else:
        fig.add_trace(go.Scatter(x=x, y=frame.q90_mw, mode='lines', line_width=0,
                                name='q90 magnitude', showlegend=False))
        fig.add_trace(go.Scatter(x=x, y=frame.q10_mw, mode='lines', line_width=0,
                                fill='tonexty', fillcolor='rgba(13,148,136,0.18)', name='q10–q90 magnitude range'))
        traces = [('q50_mw', 'Forecast median magnitude', '#0d9488'),
                  ('weekly_mw', 'Weekly persistence magnitude', '#a78bfa')]
        if actuals:
            traces += [('actual_magnitude_mw', 'Measured magnitude', '#334155')]
    for col, label, color in traces:
        fig.add_trace(go.Scatter(x=x, y=frame[col], mode='lines', name=label,
                                line=dict(color=color, width=2), hovertemplate='%{y:.3f} MW<extra>%{fullData.name}</extra>'))
    fig.add_vrect(x0=16, x1=21, fillcolor='#f59e0b', opacity=.12, line_width=0)
    if threshold is not None:
        fig.add_hline(y=threshold, line_dash='dot', annotation_text='Training evening-mean threshold')
    if capacity is not None:
        fig.add_hline(y=capacity, line_dash='dot', annotation_text='Assumed import ceiling')
    fig.update_layout(template='plotly_white', height=420, margin=dict(l=20,r=20,t=35,b=20),
                      legend=dict(orientation='h', y=-.22), hovermode='x unified',
                      yaxis_title='Signed power (MW)' if scenario else 'Flow magnitude (MW)',
                      xaxis=dict(title='Local interval start (half-hour average)', range=[0,24],
                                 tickvals=list(range(0,25,3)), ticktext=[f'{h:02}:00' for h in range(0,25,3)]))
    return fig
