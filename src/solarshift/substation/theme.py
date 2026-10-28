"""Apple-inspired local preview: system type, light surfaces and restrained motion."""

CSS = """
<style>
:root {--ink:#1d1d1f;--muted:#6e6e73;--accent:#0071e3;--line:#d9dce2;--surface:#f5f5f7}
html {scroll-behavior:smooth;scroll-padding-top:90px}
.stApp {background:#f5f5f7;color:var(--ink)}
[data-testid="stHeader"] {background:transparent;height:0}
[data-testid="stToolbar"] {display:none}
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"], [data-testid="stMetric"],
[data-baseweb="select"], button p {font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif!important;-webkit-font-smoothing:antialiased}
.block-container {max-width:1200px;padding:80px 40px 32px}
h1,h2,h3 {font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif!important;color:var(--ink);font-weight:600!important;line-height:1.12!important;letter-spacing:-.025em!important}
h2 {font-size:28px!important} h3 {font-size:21px!important}
[data-testid="stMarkdownContainer"] p {font-size:15px;line-height:1.65}
[data-testid="stCaptionContainer"] p {font-size:13px;line-height:1.6;color:#63636a}
[data-testid="stWidgetLabel"] p {font-size:14px!important;font-weight:500}
a:focus-visible,button:focus-visible {outline:3px solid #0071e3!important;outline-offset:4px}
.apple-nav {position:fixed;z-index:999;top:0;left:0;right:0;height:60px;border-bottom:1px solid #00000012;background:rgba(250,250,252,.86);backdrop-filter:blur(20px) saturate(160%);-webkit-backdrop-filter:blur(20px) saturate(160%)}
.apple-nav-inner {max-width:1120px;margin:auto;height:100%;display:flex;align-items:center;justify-content:space-between;padding:0 24px;gap:20px}
.apple-nav a {color:#303035;text-decoration:none;font-size:13px}
.apple-nav .wordmark {font-size:19px;font-weight:600;letter-spacing:-.035em;white-space:nowrap}
.wordmark span {color:#0071e3}
.nav-links {display:flex;gap:26px;align-items:center}
.apple-nav .nav-cta {background:#0071e3;color:white;border-radius:30px;padding:7px 15px}
.apple-hero {text-align:center;max-width:850px;margin:34px auto 42px;animation:arrive .8s cubic-bezier(.2,.8,.2,1) both}
.apple-hero .eyebrow {font-size:13px;font-weight:600;color:#6e6e73;margin-bottom:18px}
.apple-hero h1 {font-size:clamp(42px,6.1vw,72px)!important;letter-spacing:-.055em!important;line-height:1.04!important;margin:0;padding:0}
.apple-hero h1 span {color:#0071e3}
.apple-hero .intro {max-width:580px;margin:24px auto;color:#6e6e73;font-size:19px;line-height:1.5}
.hero-actions {display:flex;justify-content:center;align-items:center;gap:24px;margin:26px 0 18px}
.pill {display:inline-block;background:#0071e3;color:white!important;border-radius:999px;padding:12px 24px;text-decoration:none;font-size:15px;transition:transform .25s cubic-bezier(.2,.8,.2,1),background .2s,box-shadow .2s}
.pill:hover {background:#0077ed;transform:translateY(-2px);box-shadow:0 6px 18px #0071e325}
.text-link {color:#0066cc!important;text-decoration:none;font-size:15px}
.hero-note {font-size:12px!important;color:#6e6e73}
.bento {display:grid;grid-template-columns:1.3fr 1fr 1fr;gap:16px;margin:0 0 44px}
.bento article {background:#fff;border:1px solid #00000007;border-radius:24px;padding:26px;box-shadow:0 5px 20px #00000003;transition:transform .3s cubic-bezier(.2,.8,.2,1),box-shadow .3s}
.bento article:hover {transform:translateY(-3px);box-shadow:0 12px 30px #00000008}
.bento article:first-child {background:#eaf3fd}
.bento .step {font-size:12px;color:#0066cc;font-weight:600;margin-bottom:18px;display:block}
.bento h2 {font-size:23px!important;margin:0 0 10px;padding:0}
.bento p {color:#63636a;margin:0;font-size:14px;line-height:1.6}
.workspace-label {font-size:12px;letter-spacing:.08em;font-weight:600;color:#6e6e73;text-transform:uppercase;margin:6px 0 14px;scroll-margin-top:85px}
[data-testid="stVerticalBlockBorderWrapper"]>div {border-color:#e3e5e9!important;border-radius:22px!important;background:#fff}
.selection-heading {padding:22px 0 6px}
.selection-heading h2 {margin:0;padding:0;overflow-wrap:anywhere}
.selection-heading p {color:#6e6e73;margin:9px 0 14px;font-size:14px}
[data-testid="stMetric"] {background:#fff;border:1px solid #e5e7eb;border-radius:20px;padding:22px}
[data-testid="stMetricLabel"] p {color:#63636a;font-size:13px!important}
[data-testid="stMetricValue"] {color:#1d1d1f;font-weight:600;font-size:30px;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
[data-baseweb="tab-list"] {gap:6px;background:#e9eaee;border-radius:12px;padding:5px;margin-bottom:24px;overflow-x:auto}
[data-baseweb="tab"] {padding:10px 20px;border-radius:8px;white-space:nowrap;height:auto}
[data-baseweb="tab"] p {font-size:14px!important;font-weight:500}
[data-baseweb="tab"][aria-selected="true"] {color:#1d1d1f;background:white;box-shadow:0 2px 6px #0000000c}
[data-baseweb="tab-highlight"],[data-baseweb="tab-border"] {display:none}
[data-testid="stPlotlyChart"] {border:1px solid #e5e7eb;border-radius:24px;overflow:hidden;box-shadow:0 12px 40px #15283b06}
[data-testid="stExpander"] {border-color:#d9dce2;border-radius:14px;background:#fff}
[data-testid="stDownloadButton"] button {background:#0071e3;color:#fff;border:0;border-radius:999px;min-height:44px;padding:8px 20px}
.apple-footer {border-top:1px solid #d9dce2;margin-top:56px;padding:30px 0 12px;display:grid;grid-template-columns:2fr 1fr 1fr;gap:30px;font-size:12px;color:#6e6e73}
.apple-footer strong {color:#1d1d1f;display:block;margin-bottom:12px;font-size:13px}
.apple-footer a {display:block;color:#515157;text-decoration:none;margin:8px 0}
.apple-footer p {font-size:12px!important;max-width:360px}
@keyframes arrive {from {opacity:0;transform:translateY(16px)} to {opacity:1;transform:translateY(0)}}
@supports (animation-timeline:view()) {.bento article {animation:arrive linear both;animation-timeline:view();animation-range:entry 0% entry 25%}}
@media(max-width:760px) {
 .block-container {padding:72px 20px 24px}.apple-nav-inner {padding:0 20px}.nav-links {gap:14px}.nav-links .optional {display:none}
 .apple-hero {margin:30px auto}.apple-hero .intro {font-size:17px}.bento {grid-template-columns:1fr;margin-bottom:28px;gap:12px}.bento article {padding:22px}.bento .step {margin-bottom:10px}
 .apple-footer {grid-template-columns:1fr 1fr}.apple-footer>div:first-child {grid-column:1/-1}
 [data-baseweb="tab"] {padding:10px 11px}[data-baseweb="tab"] p {font-size:13px!important}
}
@media(prefers-reduced-motion:reduce) {html {scroll-behavior:auto}*,*::before,*::after {animation:none!important;transition:none!important}}
</style>
"""


def style_chart(fig):
    fig.update_layout(template='plotly_white', paper_bgcolor='#ffffff', plot_bgcolor='#ffffff',
                      font=dict(family='-apple-system, BlinkMacSystemFont, Segoe UI, Arial, sans-serif',color='#1d1d1f',size=13),
                      colorway=['#0071e3','#86868b','#5c7086'],
                      hoverlabel=dict(bgcolor='#ffffff',font_color='#1d1d1f',bordercolor='#d9dce2'),
                      legend=dict(font=dict(color='#63636a',size=12)))
    fig.update_xaxes(gridcolor='#eef0f3',zerolinecolor='#d9dce2',automargin=True)
    fig.update_yaxes(gridcolor='#eef0f3',zerolinecolor='#d9dce2',automargin=True)
    return fig
