"""Produce a standalone validation chart and compact evidence, after the audit."""
import json
import shutil
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from solarshift.substation.forecast import validation_forecast

d = Path('results/generated/substation_day4')
a = json.loads((d/'audit.json').read_text())
assert a['passed']
f = validation_forecast(d,a['example_site'],a['example_date'])
metrics = pd.read_csv(d/'metrics.csv')
summary = json.loads((d/'summary.json').read_text())
x = f.hh / 2
fig = make_subplots(rows=2,cols=1,shared_xaxes=True,subplot_titles=['Flow magnitude forecast and measured magnitude','Published signed flow (separate quantity)'],vertical_spacing=.13)
fig.add_trace(go.Scatter(x=x,y=f.q90_mw,name='q90',line=dict(width=0),showlegend=False),row=1,col=1)
fig.add_trace(go.Scatter(x=x,y=f.q10_mw,name='Raw q10–q90 range',fill='tonexty',fillcolor='rgba(40,110,200,.18)',line=dict(width=0)),row=1,col=1)
for col,name,color in [('actual_magnitude_mw','Measured magnitude','#192a3a'),('q50_mw','Median forecast','#2168bd'),('weekly_mw','Weekly persistence','#b55c1c')]:
    fig.add_trace(go.Scatter(x=x,y=f[col],name=name,line=dict(color=color)),row=1,col=1)
fig.add_trace(go.Scatter(x=x,y=f.signed_actual_mw,name='Signed actual',line=dict(color='#148477')),row=2,col=1)
fig.add_vrect(x0=16,x1=21,fillcolor='#f1b447',opacity=.14,line_width=0,row='all',col=1)
fig.update_yaxes(title_text='MW',row=1,col=1)
fig.update_yaxes(title_text='MW signed',row=2,col=1)
fig.update_xaxes(title_text='Local interval start hour • Australia/Sydney',row=2,col=1,range=[0,24],dtick=3)
fig.update_layout(template='plotly_white',height=760,title=f"Closing the Peak — validation replay<br><sup>{a['example_site']} · {a['example_date']} · first complete site/date, not selected by forecast accuracy</sup>",legend=dict(orientation='h',y=-.15),margin=dict(b=130))
table = metrics.round(4).to_html(index=False,border=0)
html = '''<!doctype html><html><head><meta charset="utf-8"><title>Closing the Peak — Day 4</title><style>body{max-width:1100px;margin:36px auto;padding:0 24px;font:16px/1.55 system-ui;color:#192a3a}h1{font-size:32px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:9px;border-bottom:1px solid #ddd}.note{background:#edf3f8;padding:18px;border-radius:10px}</style></head><body><h1>Closing the Peak: Day 4 validation</h1><p class="note">Historical substation replay. Measured values, magnitude forecasts and signed power are labelled separately. The amber window is 16:00–21:00. No response simulation, final-test evaluation or measured savings is included.</p>'''
html += fig.to_html(full_html=False,include_plotlyjs=True)
html += '<h2>Comparison on identical eligible validation intervals</h2>'+table
html += f"<p>{summary['sites']} training-selected sites; {summary['validation_rows']:,} validation intervals. Raw nominal 80% evening-band coverage: {summary['evening_raw_80pct_coverage']:.1%}. This band is not yet calibrated.</p>"
html += '<p>May 2021–April 2023 training; May 2023–April 2024 validation. Temperature-only genuine cached forecasts; complete DST transition days excluded. Cohort and weather changes mean these results do not reproduce Theo’s reported analysis. Source: Ausgrid and Open-Meteo caches supplied in Theo’s project. Adapted utilities and integration attribution are documented in the development log.</p></body></html>'
(d/'validation_report.html').write_text(html)
e = Path('results/evidence/substation_day4')
e.mkdir(parents=True,exist_ok=True)
for name in ['summary.json','source_manifest.json','audit.json','metrics.csv','cohort.csv','clustering.json','eligibility.csv','sign_audit.csv','peak_thresholds_training.csv','training_cleaning_scales.csv']:
    shutil.copy2(d/name,e/name)
print(d/'validation_report.html')
