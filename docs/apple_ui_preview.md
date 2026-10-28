# SolarShift AI — Apple-inspired UI preview

Status: design reviewed; user approved committing and pushing this implementation.
GitHub publication does not deploy the Streamlit application.

## Completed project brief

- Product: SolarShift AI / Closing the Peak.
- Purpose: an interactive research dashboard for historical substation demand forecasts,
  peak warnings, voluntary load-shifting scenarios and validation evidence.
- Audience: ENG2112 students, project teammates and research reviewers.
- Stack: existing Streamlit 1.50 + Plotly 6, with scoped HTML/CSS. No new dependencies,
  remote fonts, stock assets, authentication or hosting services.

## Design system

| Role | Value |
| --- | --- |
| Page | `#f5f5f7` |
| Cards and chart stage | `#ffffff` |
| Primary text | `#1d1d1f` |
| Secondary text | `#6e6e73` (chart captions use `#63636a`) |
| Accent and primary actions | `#0071e3` |
| Text links | `#0066cc` |
| Borders | `#d9dce2` |
| Typeface | `-apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif` |

The native system stack uses the platform's available UI font without downloading
or redistributing Apple's fonts. Headline size scales from 42 to 72 px. Body is
15 px, introductory copy 19 px (17 px on mobile), secondary copy 13 px. Tight
tracking is reserved for display headings; controls retain normal spacing.

The main width is capped at 1200 px, with 40 px desktop and 20 px mobile gutters.
Spacing follows a predominantly 4/8 px rhythm: 16 px card gaps, 24–26 px card
padding, 40–56 px section separation. Corners are 20–24 px on cards and fully
rounded on calls to action. A slim 60 px navigation remains available during scroll.

The page moves from purpose → three-step explanation → actual research workspace.
The live Plotly forecast is the product visual stage, not fabricated dashboard data.
Controls remain functional; evidence and provenance remain accessible. The footer
contains real anchor links and a research notice rather than invented legal pages.

## Code and implementation

- `src/solarshift/substation/theme.py`: shared CSS and Plotly theme.
- `.streamlit/config.toml`: native widget colours; run from the project directory.
- `streamlit_app.py`: semantic navigation, hero, bento introduction, working controls
  and footer. Dynamic site labels are HTML-escaped.
- `src/solarshift/substation/dashboard.py`: accessible contrasting chart traces.

Start from the solarshift-ai directory:

```sh
PYTHONPATH=src .venv/bin/python -m streamlit run streamlit_app.py --server.address=127.0.0.1 --browser.gatherUsageStats=false
```

Existing local validation artifacts are required; setup is documented in dashboard.md.
If an existing browser has a manually selected Streamlit theme, choose the app's
configured theme to see the light native controls.

## Blur and motion

The header uses `rgba(250,250,252,.86)` with `backdrop-filter: blur(20px)
saturate(160%)` and the WebKit prefix. Its near-opaque background remains readable
when blur is unsupported. A hairline bottom border separates it from the content.

The hero fades and translates 16 px over 800 ms. Buttons and cards use 200–300 ms
transitions with `cubic-bezier(.2,.8,.2,1)`, a spring-like easing rather than a
physical spring simulation. Hover elevation is limited to 2–3 px.

Bento cards progressively enhance with CSS view-timeline reveals when supported.
Unsupported browsers show the complete cards immediately. `prefers-reduced-motion`
disables animation, transitions and smooth scrolling. No script injection or
third-party animation runtime is required.

## Review and integration limits

The theme is implemented against the pinned Streamlit version. Internal `data-testid`
and Base Web selectors should be browser-checked when upgrading Streamlit. This is
a reviewable application implementation, not a claim of completed deployment QA.
The model, pricing rules and evaluation data are unchanged. All four existing
dashboard integration tests pass, including zero-response and exemption cases.
