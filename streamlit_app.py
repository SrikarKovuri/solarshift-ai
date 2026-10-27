"""Run with PYTHONPATH=src python -m streamlit run streamlit_app.py."""
import json
import os
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from solarshift.substation.dashboard import catalog, curve_figure
from solarshift.substation.theme import CSS, style_chart
from solarshift.substation.response import Scenario
from solarshift.substation.scenario_replay import replay_scenario

ROOT = Path(__file__).resolve().parent
GENERATED = Path(os.environ.get('SOLARSHIFT_RESULTS', ROOT / 'results/generated'))
D4, D5 = GENERATED / 'substation_day4', GENERATED / 'substation_day5'
st.set_page_config(page_title='Closing the Peak', page_icon='☀️', layout='wide')
st.markdown(CSS, unsafe_allow_html=True)
st.markdown('<div class="atlas-topline">ENG2112 / CLOSING THE PEAK · RESEARCH WORKSPACE</div>'
            '<div class="atlas-hero"><div class="atlas-eyebrow">ENERGY SYSTEMS / VALIDATION REPLAY</div>'
            '<h1>Understand the peak.<br><span>Explore the response.</span></h1>'
            '<p>Trace a substation forecast from uncertainty to peak risk, then explore how voluntary '
            'load shifting changes the evening curve.</p></div>', unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def available_days(directory4, directory5, stamp):
    return catalog(directory4, directory5)

try:
    days = available_days(str(D4), str(D5), ((D4/'validation_forecasts.parquet').stat().st_mtime_ns,
                                           (D5/'calibration.json').stat().st_mtime_ns))
    summary = json.loads((D4/'summary.json').read_text())
    cohort = pd.read_csv(D4/'cohort.csv').set_index('substation')
except (OSError, ValueError, KeyError) as exc:
    st.error(f'Validation data unavailable: {exc}')
    st.code('PYTHONPATH=src .venv/bin/python -m solarshift.substation.pipeline --help\n'
            'PYTHONPATH=src .venv/bin/python -m solarshift.substation.day5')
    st.caption('Follow docs/substation_forecasting.md to rebuild local artifacts. Raw datasets are not bundled with Git.')
    st.stop()

with st.sidebar:
    st.markdown('<div class="atlas-brand"><span>◉</span> Closing the Peak<small>ENG2112 · ENERGY ATLAS</small></div>', unsafe_allow_html=True)
    st.header('Choose a historical day')
    site = st.selectbox('Substation', days.site.unique(), key='site')
    dates = days.loc[days.site.eq(site), 'date'].tolist()
    date = st.selectbox('Validation date', dates, key=f'date_{site}')
    st.caption(f'{len(dates)} complete days available for this site. Missing or excluded days cannot be selected.')
    st.caption('Replay: November 2023–April 2024. Reserved test disabled.')
    st.header('Scenario assumptions')
    response = st.slider('Response at maximum uplift (%)', 0, 30, 10, key='response') / 100
    flexible = st.slider('Movable residential load (%)', 5, 25, 15) / 100
    exempt = st.slider('Exempt households (%)', 0, 100, 10, key='exempt') / 100
    residential = st.slider('Residential share of positive imports (%)', 0, 100, 60) / 100
    with st.expander('Solar, battery and destination assumptions'):
        solar = st.slider('Solar households (%)', 0, 100, 21) / 100
        battery = st.slider('Solar + battery households (%)', 0, 100, 2) / 100
        factor = st.slider('Battery response factor', 0., 5., 2., .1)
        midday = st.slider('Shifted energy sent to 10:00–15:00 (%)', 0, 100, 50) / 100
        capacity_factor = st.slider('Import ceiling × training proxy', 0., 2., 1., .05)
        st.caption('Remaining energy goes to 21:00–23:00 with equal slot weights and capacity constraints.')
try:
    cap = float(pd.read_csv(D5/'scenario_capacity.csv').set_index('substation').loc[site].iloc[0]) * capacity_factor
    result = replay_scenario(D4, D5, site, date,
                             Scenario(residential, flexible, response, exempt, solar, battery, factor, midday), cap)
except (OSError, ValueError, KeyError) as exc:
    st.error(f'Cannot run this scenario: {exc}')
    st.stop()
f, metrics = result['intervals'], result['metrics']
st.subheader(f'{site} · {date}')
zone = cohort.loc[site].get('weather_zone', 'Unavailable')
st.caption(f'Weather zone: {zone} · Issue time: {f.issue_time.iloc[0]} · 48 half-hour intervals · Evening: 16:00–21:00')
forecast, scenario, evidence = st.tabs(['Forecast & warning', 'Response scenario', 'Evidence & explanations'])
with forecast:
    a,b,c = st.columns(3)
    a.metric('Calibrated peak probability', f"{result['calibrated_probability']:.1%}")
    b.metric('Peak warning', 'Active' if result['warning'] else 'Inactive')
    c.metric('Evening multiplier (non-exempt)', f"{result['multiplier']:.3f}×")
    st.caption('Warning at probability ≥30%; uplift starts above 30%, capped at 1.5×. Exempt households remain at 1×.')
    reveal = st.checkbox('Reveal measured magnitude for historical comparison', key='actuals')
    st.plotly_chart(curve_figure(f, actuals=reveal, threshold=result['threshold_evening_magnitude_mw']), use_container_width=True)
    st.caption('The threshold applies to the evening mean, not each interval. The q10–q90 band is a nominal 80% magnitude range; '
               f"observed evening coverage across validation is {summary['evening_raw_80pct_coverage']:.1%}. It is not a calibrated guarantee.")
    st.write('Peak risk is a heuristic derived from evening interval quantiles, then calibrated on May–October 2023. '
             'It assumes shared quantile ranks across intervals; three quantiles do not uniquely determine evening-mean risk.')
    st.caption(f"Raw risk: {result['raw_probability']:.1%}. Forecasts use historical load, forecast temperature, calendar, sun position and training-derived site attributes.")
with scenario:
    st.write('Retrospective simulation using measured signed flow and known headroom. Positive net imports approximate residential demand; '
             'exports are never treated as movable consumption. No measured energy or bill saving is claimed.')
    a,b,c = st.columns(3)
    a.metric('Displaced energy', f"{metrics['total_displaced_mwh']:.4f} MWh")
    def pct(value):
        return 'Not defined' if value is None else f'{0.0 if abs(value) < 0.0005 else value:.3f}%'
    b.metric('Evening mean reduction', pct(metrics['evening_mean_reduction_pct']))
    c.metric('Whole-day maximum reduction', pct(metrics['whole_day_max_reduction_pct']))
    st.plotly_chart(curve_figure(f, scenario=True, capacity=cap), use_container_width=True)
    st.caption(f"Evening maximum reduction: {pct(metrics['evening_max_reduction_pct'])}. Energy balance error: {metrics['max_energy_error_mwh']:.2e} MWh.")
    if metrics['capacity_limited_days']:
        st.warning('Destination headroom limits the shift. Unshiftable energy remains in the evening.')
    if metrics['increased_whole_day_max_days']:
        st.warning('Rebound: the simulated whole-day maximum is higher than the measured maximum.')
    elif metrics['late_window_peak_increased_days']:
        st.info('The late-window maximum increases, without increasing the whole-day maximum.')
    if (f.signed_actual_mw > cap).any():
        st.warning('Measured flow already exceeds the assumed ceiling in some intervals; the scenario does not repair existing exceedances.')
    st.caption('The ceiling is a training 99th-percentile magnitude proxy, not a transformer rating. Battery response is a participation assumption, not storage dispatch.')
    st.write('Participation is voluntary. Renters, households without solar and people with inflexible essential use may have fewer options. '
             'Exemptions and a price cap are explicit safeguards, but do not establish equity. Solar+battery households are a subset of solar households.')
    st.download_button('Download this replay (CSV)', f.to_csv(index=False), f'{site}_{date}_scenario.csv', 'text/csv')
    st.download_button('Download scenario assumptions (JSON)', json.dumps(dict(site=site,date=date,scenario=Scenario(residential,flexible,response,exempt,solar,battery,factor,midday).__dict__,capacity_mw=cap,metrics=metrics),indent=2), 'scenario_assumptions.json', 'application/json')
with evidence:
    st.subheader('Validation evidence')
    st.write('Training: May 2021–April 2023. Forecast validation: May 2023–April 2024. '
             'Probability fitting: May–October 2023; warning evaluation: November 2023–April 2024. '
             'Final-test evaluation and method sign-off remain outstanding.')
    for title, path in [('Forecast comparison — errors in MW; nMAE in percent', D4/'metrics.csv'),
                        ('Warning comparison — later validation', D5/'warning_metrics.csv'),
                        ('Probability reliability — later validation', D5/'reliability.csv')]:
        with st.expander(title):
            if path.exists():
                st.dataframe(pd.read_csv(path), hide_index=True, use_container_width=True)
            else:
                st.warning(f'Evidence unavailable: {path.name}')
    evaluation_path = GENERATED/'substation_day7'/'evaluation.json'
    if evaluation_path.exists():
        evaluation = json.loads(evaluation_path.read_text())
        st.subheader('Chronological validation checks')
        a,b,c = st.columns(3)
        a.metric('Evening MAE improvement', f"{evaluation['bootstrap']['improvement_pct']:.1f}%")
        b.metric('CQR interval coverage', f"{evaluation['evaluation']['cqr_coverage']:.1%}")
        c.metric('Later-validation intervals', f"{evaluation['evaluation']['rows']:,}")
        low, high = evaluation['bootstrap']['ci95_pct']
        st.caption(f'Against weekly persistence · 95% week-block bootstrap interval: {low:.1f}–{high:.1f}% · 500 resamples. '
                   'CQR fitted May–October 2023; evaluated November 2023–April 2024. The forecast chart retains its raw quantile band.')
        with st.expander('Evaluation methods and sensitivity checks'):
            st.json(evaluation)
            sensitivity = evaluation_path.parent/'robustness.csv'
            if sensitivity.exists():
                st.dataframe(pd.read_csv(sensitivity), hide_index=True)
    st.subheader('What does the model rely on?')
    importance = GENERATED/'substation_day6'/'importance.csv'
    if importance.exists():
        imp = pd.read_csv(importance)
        labels = {'historical_load':'Historical load', 'forecast_weather':'Forecast temperature',
                  'calendar':'Calendar', 'sun_position':'Sun position', 'training_attributes':'Site attributes'}
        chart = go.Figure(go.Bar(x=imp.mae_increase_mw, y=imp.group.map(labels), orientation='h',
                                error_x=dict(type='data',array=imp.repeat_sd_mw), marker_color='#c0e994'))
        chart.update_layout(template='plotly_white', height=300, margin=dict(l=10,r=20,t=15,b=35),
                            xaxis_title='Evening MAE increase (MW)', yaxis=dict(autorange='reversed'))
        st.plotly_chart(style_chart(chart), use_container_width=True)
        st.dataframe(imp, hide_index=True)
        st.caption('Grouped permutation importance: increase in evening MAE after jointly shuffling a feature family across sampled later-validation rows. '
                   'Five repeats, fixed seed; reported SD is repeat variability, not confidence intervals. Correlated features and implausible shuffled combinations limit interpretation. '
                   'These are global predictive associations, not causal effects or explanations of this selected day.')
    else:
        st.warning('Feature explanation artifact unavailable. Run python -m solarshift.substation.explain.')
    with st.expander('Provenance, exclusions and limitations'):
        st.write(f"Training-selected cohort: {summary['sites']} sites. Source: Ausgrid FY2021–FY2025 handover; only development data are used here.")
        st.write(summary['availability_contract'])
        st.write('Missing history, gaps, ambiguous DST dates and quality flags exclude rows; scenarios require complete 48-slot days. '
                 'Published signed flow is preserved; the model predicts its magnitude. Genuine temperature-only forecasts replace synthetic future-error donors. '
                 'Weather coverage limits the evaluation period. Forecasts and policy settings are research assumptions, not operational advice.')
        st.write('Substation training carbon has not yet been instrumented. The archived household carbon estimate does not apply. '
                 'Chronological CQR and weekly bootstrap diagnostics are in the validation evidence below. Frozen final-test evaluation remains outstanding.')
        st.write('Theo supplied source data/code and scenario concepts. Codex adapted the local pipeline and dashboard at Srikar’s request. Human team review remains pending.')
        st.json({'weather_provenance':f.weather_provenance.iloc[0], 'quality_flags':f.quality_flags.unique().tolist(), 'anomaly_day':bool(f.anomaly.any())})

st.markdown('<div class="atlas-footer">Ausgrid historical data · Model forecasts · Simulated responses · Validation only</div>', unsafe_allow_html=True)
