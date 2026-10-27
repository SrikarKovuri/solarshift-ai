"""Study Atlas palette shared by the application and Plotly figures."""

CSS = """
<style>
.stApp {background:#101412;color:#eef1e9;font-family:Inter,'Helvetica Neue',Arial,sans-serif}
[data-testid="stHeader"] {background:#101412}
[data-testid="stSidebar"] {background:#131814;border-right:1px solid #2d3730}
[data-testid="stSidebar"] h2 {font-size:15px;letter-spacing:-.02em}
.block-container {max-width:1500px;padding:4.5rem 3rem 4rem}
h1,h2,h3 {font-weight:500!important;letter-spacing:-.045em!important}
[data-testid="stCaptionContainer"] {color:#99a59a}
.atlas-brand {font-size:19px;letter-spacing:-.04em;padding:8px 0 28px;color:#eef1e9}
.atlas-brand span {color:#c0e994}
.atlas-brand small {display:block;font-size:10px;letter-spacing:.17em;color:#99a59a;margin-top:7px}
.atlas-topline {font-size:10px;letter-spacing:.16em;color:#99a59a;border-bottom:1px solid #2d3730;padding-bottom:20px;margin-bottom:32px}
.atlas-hero {padding:0 0 26px}
.atlas-eyebrow {color:#c0e994;font-size:10px;letter-spacing:.18em;margin-bottom:16px}
.atlas-hero h1 {font-size:clamp(36px,4vw,58px);line-height:1.08;padding:0 0 18px}
.atlas-hero h1 span {color:#c0e994}
.atlas-hero p {color:#99a59a;max-width:630px;line-height:1.8;font-size:14px}
[data-testid="stMetric"] {border:1px solid #2d3730;background:#171c19;border-radius:14px;padding:19px 22px}
[data-testid="stMetricLabel"] {color:#99a59a;font-size:12px}
[data-testid="stMetricValue"] {color:#c0e994;font-weight:500;font-size:28px}
[data-baseweb="tab-list"] {gap:18px;border-bottom:1px solid #2d3730;margin-bottom:20px}
[data-baseweb="tab"] {font-size:12px;padding:12px 5px}
[data-baseweb="tab"][aria-selected="true"] {color:#c0e994}
[data-testid="stPlotlyChart"] {border:1px solid #2d3730;border-radius:14px;overflow:hidden}
[data-testid="stExpander"] {border-color:#2d3730;border-radius:10px}
[data-testid="stDownloadButton"] button {border:1px solid #435237;background:#202a20;color:#c0e994;border-radius:8px}
.atlas-footer {margin-top:32px;border-top:1px solid #2d3730;padding-top:20px;color:#99a59a;font-size:11px}
@media(max-width:760px) {.block-container {padding:4.5rem 1rem 2rem}.atlas-topline {margin-bottom:24px}}
</style>
"""


def style_chart(fig):
    fig.update_layout(template='plotly_dark', paper_bgcolor='#171c19', plot_bgcolor='#171c19',
                      font=dict(family='Inter, Helvetica Neue, Arial, sans-serif',color='#eef1e9',size=12),
                      colorway=['#c0e994','#edc48e','#99b9cc','#eea39d'],
                      hoverlabel=dict(bgcolor='#202a20',font_color='#eef1e9'),
                      legend=dict(font=dict(color='#99a59a')))
    fig.update_xaxes(gridcolor='#2d3730',zerolinecolor='#435237')
    fig.update_yaxes(gridcolor='#2d3730',zerolinecolor='#435237')
    return fig
