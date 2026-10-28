"""Run with PYTHONPATH=src python -m streamlit run streamlit_app.py."""
import json
import os
import html
import sys
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from solarshift.substation.dashboard import catalog, curve_figure
from solarshift.substation.theme import CSS, style_chart
from solarshift.substation.response import Scenario
from solarshift.substation.scenario_replay import replay_scenario

ROOT = Path(__file__).resolve().parent
DEFAULT_RESULTS = ROOT / 'results/generated'
if not (DEFAULT_RESULTS / 'substation_day4/validation_forecasts.parquet').exists():
    DEFAULT_RESULTS = DEFAULT_RESULTS / 'marker_demo'
GENERATED = Path(os.environ.get('SOLARSHIFT_RESULTS', DEFAULT_RESULTS))
EVIDENCE = ROOT / 'results/evidence'
FINAL_PATH = EVIDENCE / 'final_evaluation/summary.json'
FINAL = json.loads(FINAL_PATH.read_text()) if FINAL_PATH.exists() else None
D4, D5 = GENERATED / 'substation_day4', GENERATED / 'substation_day5'
st.set_page_config(page_title='SolarShift AI | Closing the Peak', page_icon='◒', layout='wide')
st.markdown(CSS, unsafe_allow_html=True)
st.markdown('<nav class="apple-nav" aria-label="Main navigation"><div class="apple-nav-inner"><a class="wordmark" href="#overview">SolarShift <span>AI</span></a><div class="nav-links"><a class="optional" href="#approach">The approach</a><a href="#about">About</a><a class="nav-cta" href="#workspace">Explore the model</a></div></div></nav>\n<section class="apple-hero" id="overview"><p class="eyebrow">Closing the Peak · An ENG2112 research project</p><h1>A clearer view of demand.<br><span>A smarter way to shift it.</span></h1><p class="intro">Explore tomorrow’s peak through historical forecasts. See what changes when electricity demand moves to a different time.</p><div class="hero-actions"><a class="pill" href="#workspace">Explore the forecast</a><a class="text-link" href="#approach">How it works <span aria-hidden="true">↗</span></a></div><p class="hero-note">Historical validation. Real Ausgrid data. Simulated responses.</p></section>\n<section class="bento" id="approach" aria-label="How SolarShift works"><article><span class="step">01 / FORECAST</span><h2>See the day ahead.</h2><p>Explore half-hourly demand forecasts, with uncertainty kept in view.</p></article><article><span class="step">02 / EXPLORE</span><h2>Make room at the peak.</h2><p>Adjust voluntary participation. Compare how the daily curve changes.</p></article><article><span class="step">03 / UNDERSTAND</span><h2>Follow the evidence.</h2><p>Inspect validation results, assumptions and the limits of the model.</p></article></section>\n<div class="workspace-label" id="workspace">Your research workspace</div>', unsafe_allow_html=True)

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
    st.write('First visit? Prepare the marker walkthrough from the official Ausgrid archive.')
    st.code('python -m pip install -r requirements.txt\npython run.py')
    st.caption('See docs/marker_guide.md. Setup downloads about 17 MB once; no training or private files are required.')
    if st.button('Download official data and prepare walkthrough'):
        from scripts.prepare_demo import prepare
        try:
            with st.spinner('Downloading and verifying the official archive…'):
                prepare(ROOT / 'results/generated/marker_demo')
            st.rerun()
        except Exception as setup_error:
            st.error(f'Setup failed: {setup_error}. Use the manual archive option in the marker guide.')
    st.stop()

if (GENERATED/'demo_manifest.json').exists():
    st.info('Marker walkthrough: 42 historical site-days across 3 substations. Evidence tables describe the full 63-site study. These are saved model forecasts; changing scenario controls does not retrain the model.')

with st.container(border=True):
    st.subheader('Choose a location and date')
    location_column, date_column = st.columns([2, 1])
    with location_column:
        site = st.selectbox('Substation', days.site.unique(), key='site')
    dates = days.loc[days.site.eq(site), 'date'].tolist()
    with date_column:
        date = st.selectbox('Validation date', dates, key=f'date_{site}', index=dates.index('2023-11-12') if '2023-11-12' in dates else 0)
    st.caption(f'{len(dates)} complete days available · {pd.Timestamp(min(dates)).strftime("%d %b %Y")}–{pd.Timestamp(max(dates)).strftime("%d %b %Y")} · Historical data')

st.markdown(f'<div class="selection-heading"><h2>{html.escape(site.replace("_", "/"))}</h2>'
            f'<p>{pd.Timestamp(date).strftime("%A, %d %B %Y")} · Evening peak: 4–9 pm</p></div>', unsafe_allow_html=True)
forecast, scenario, evidence = st.tabs(['1. Forecast', '2. Explore a response', '3. Evidence'])
with scenario:
    st.subheader('Adjust the response')
    st.write('Change participation and exemptions to compare a simulated day with measured flow.')
    with st.container(border=True):
        left, right = st.columns(2)
        with left:
            response = st.slider('Response at maximum uplift (%)', 0, 30, 10, key='response',
                                 help='Response assumed when the price multiplier reaches its 1.5× cap.') / 100
            flexible = st.slider('Movable residential load (%)', 5, 25, 15,
                                 help='Share of residential demand that can move to another time.') / 100
        with right:
            exempt = st.slider('Exempt households (%)', 0, 100, 10, key='exempt',
                               help='Exempt households keep the base price and do not shift demand in this scenario.') / 100
            residential = st.slider('Residential share of positive imports (%)', 0, 100, 60) / 100
        with st.expander('Advanced assumptions: solar, batteries and capacity'):
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
with forecast:
    st.subheader('Evening outlook')
    if result['warning']:
        st.write('A peak warning is active. Explore the response tab to see how shifting demand could change the evening peak.')
    else:
        st.write('No peak warning for this day. The price stays at its base level, so this scenario shifts no demand.')
    a,b,c = st.columns(3)
    a.metric('Calibrated peak probability', f"{result['calibrated_probability']:.1%}")
    b.metric('Peak warning', 'Active' if result['warning'] else 'Inactive')
    c.metric('Evening multiplier (non-exempt)', f"{result['multiplier']:.3f}×")
    st.caption('Warning at probability ≥30%; uplift starts above 30%, capped at 1.5×. Exempt households remain at 1×.')
    st.subheader('Demand throughout the day')
    st.caption('Blue: forecast median · Grey: weekly baseline · Shaded band: forecast uncertainty')
    reveal = st.checkbox('Reveal measured magnitude for historical comparison', key='actuals')
    st.plotly_chart(curve_figure(f, actuals=reveal, threshold=result['threshold_evening_magnitude_mw']), use_container_width=True)
    st.caption('The threshold applies to the evening mean, not each interval. The q10–q90 band is a nominal 80% magnitude range; '
               f"observed evening coverage across validation is {summary['evening_raw_80pct_coverage']:.1%}. It is not a calibrated guarantee.")
    with st.expander('How the warning is calculated'):
        st.caption(f"Forecast issued: {f.issue_time.iloc[0]} · Weather zone: {cohort.loc[site].get('weather_zone', 'Unavailable')} · 48 half-hour intervals")
        st.write('Peak risk is a heuristic derived from evening interval quantiles, then calibrated on May–October 2023. '
                 'It assumes shared quantile ranks across intervals; three quantiles do not uniquely determine evening-mean risk.')
        st.caption(f"Raw risk: {result['raw_probability']:.1%}. Forecasts use historical load, forecast temperature, calendar, sun position and training-derived site attributes.")
with scenario:
    st.subheader('Scenario results')
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
    if FINAL:
        st.subheader('Final held-out evaluation')
        st.write('Frozen models evaluated once on 1 May 2024–29 April 2025, following team approval confirmed by Srikar. These results are separate from the validation replay.')
        a,b,c = st.columns(3)
        a.metric('Final evening MAE improvement', f"{FINAL['bootstrap']['improvement_pct']:.1f}%")
        b.metric('Final CQR coverage', f"{FINAL['intervals']['cqr_coverage']:.1%}")
        c.metric('Test intervals', f"{FINAL['rows']:,}")
        low,high = FINAL['bootstrap']['ci95_pct']
        st.caption(f'Weekly persistence comparison · 95% week-block interval: {low:.1f}–{high:.1f}%. Coverage remains below the nominal 80%.')
        with st.expander('Final metrics, warning performance and audit'):
            for name in ['metrics.csv','warning_metrics.csv','slices.csv']:
                st.dataframe(pd.read_csv(EVIDENCE/'final_evaluation'/name), hide_index=True)
            st.json(FINAL)
        carbon_path = EVIDENCE/'submission_robustness/carbon.json'
        if carbon_path.exists():
            carbon = json.loads(carbon_path.read_text())
            with st.expander('Training repeat, robustness and carbon estimate'):
                st.dataframe(pd.read_csv(carbon_path.parent/'metrics.csv'), hide_index=True)
                st.json(carbon)
                st.caption('This measures an instrumented training repeat and sensitivity run, not the original historical run. Fixed power assumptions are documented; it is not a wall-meter measurement.')
    st.subheader('Validation evidence')
    st.write('Training: May 2021–April 2023. Forecast validation: May 2023–April 2024. '
             'Probability fitting: May–October 2023; warning evaluation: November 2023–April 2024. '
             'See the separate final-evaluation section for held-out results.')
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
                                error_x=dict(type='data',array=imp.repeat_sd_mw), marker_color='#0071e3'))
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
        st.write('Chronological CQR, weekly bootstrap and final held-out diagnostics are reported separately. The instrumented substation training repeat has its own carbon estimate; the archived household estimate is not reused.')
        st.write('Theo supplied source data/code and scenario concepts. Codex adapted the local pipeline and dashboard at Srikar’s request. Team freeze approval was confirmed by Srikar before final testing.')
        st.json({'weather_provenance':f.weather_provenance.iloc[0], 'quality_flags':f.quality_flags.unique().tolist(), 'anomaly_day':bool(f.anomaly.any())})

st.markdown('<footer class="apple-footer" id="about"><div><strong>SolarShift AI</strong><p>Closing the Peak explores substation forecasting and voluntary demand response. Built for ENG2112 using historical Ausgrid data.</p></div><div><strong>Explore</strong><a href="#workspace">Research workspace</a><a href="#approach">How it works</a><a href="#overview">Back to overview</a></div><div><strong>Research notice</strong><p>Validation prototype. Simulated effects are not measured savings or operational advice. Final held-out results are available in the Evidence tab.</p></div></footer>', unsafe_allow_html=True)
