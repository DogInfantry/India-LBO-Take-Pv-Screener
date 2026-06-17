# Static Site Export → Vercel — Design

**Date:** 2026-06-17
**Branch:** `feat/static-site-export-vercel`
**Status:** Design — pending implementation

## Problem

The interactive LBO screener runs on Streamlit Community Cloud (live, websocket
server, stateful). For a recruiting-facing showcase we also want a **fast,
always-on, polished static site on Vercel** — the same pattern as the user's
other repos (`sellside-research-engine`, `capital-markets-intelligence`), where
Python generates static HTML that Vercel serves. Vercel cannot run a Streamlit
server, so this is a *static snapshot*, not a port of the live app.

## Scope (decided)

- **Option A — pure static snapshot.** Render screen results + tear sheets to
  static HTML at the current default assumptions. No client-side LBO math.
- **A1 — showcase pages only:** a landing/leaderboard page + the 6 passing
  candidates' tear sheets. Failing names are out of scope (they stay on the
  interactive Streamlit app).
- **A1a — Vega embed:** charts exported as Vega-Lite JSON and embedded with
  vega-embed.js, so in-chart interactivity (hover, tooltips) survives on an
  otherwise static page.
- **Manual refresh:** regeneration is a deliberate local command + commit; no
  scheduled CI job.
- **Chart reuse = 3b:** the exporter builds its own Altair chart specs. **No
  existing Python (`src/`) is modified.** Accepted cost: cosmetic chart-spec
  duplication (numbers are unaffected; only visual styling could drift).

## Non-goals

- No client-side LBO recomputation (that was Option B, deferred).
- No changes to `src/app.py`, `src/lbo_model.py`, `src/screener.py`,
  `src/statements.py`, `src/data_loader.py`, or any existing Python.
- No automated/scheduled rebuilds.
- No rendering of the 40 failing names.

## Architecture

```
data/fundamentals.csv ─┐
config/config.yaml ────┼─→ [existing src/ functions] ─→ 6 passers + per-name LBO
live yfinance market ──┘            │
                                    ▼
                        tools/export_site.py (orchestrator)
                                    │
                       ┌────────────┴────────────┐
                       ▼                          ▼
              Jinja2 templates            Vega-Lite chart specs
                       │                          │
                       └────────────┬─────────────┘
                                    ▼
                                  web/  (committed static output)
                                    │
                                    ▼
                          vercel.json → Vercel static serve
```

### Reuse boundary (what the exporter imports vs. rebuilds)

Imported and called **unchanged** from `src/`:
- `data_loader`: `load_config`, `load_fundamentals`, `load_universe`,
  `fetch_market_data`
- `screener`: `compute_metrics`, `apply_screen`, `build_rationale`
- `lbo_model`: `run_lbo`
- From `app.py` — the two already-pure helpers are imported directly:
  - `sources_uses_waterfall(su) -> alt.Chart` (app.py:36)
  - `base_case_returns(passed, cfg) -> pd.DataFrame` (app.py:81)

  > Note: importing from `app.py` executes its module-level Streamlit calls
  > (`st.set_page_config`, etc.). To avoid that coupling and to keep the
  > exporter import-safe, the exporter will **not** import `app.py`. Instead it
  > re-implements `sources_uses_waterfall` and `base_case_returns` locally in
  > `tools/site/charts.py` / `tools/site/returns.py` (small, pure copies). This
  > keeps the rule "no existing Python modified" intact and avoids triggering
  > Streamlit side effects at import time. (Confirmed during design: app.py has
  > module-level `st.*` calls, so it is not import-safe for a non-Streamlit
  > process.)

Rebuilt in the exporter (3b):
- Leaderboard IRR bar + 20% hurdle line
- Criteria-cleared bar
- Sweet-spot bubble
- Sources & uses waterfall
- `base_case_returns` logic

All chart builders return `alt.Chart`; the exporter calls `.to_dict()` to get
the Vega-Lite spec and writes it as JSON for vega-embed.

## Components

1. **`tools/export_site.py`** — orchestrator. Loads inputs (config, fundamentals,
   universe, live market data), runs `compute_metrics` + `apply_screen`, selects
   `passes_screen == True` rows, runs the market take-private `run_lbo` for each
   (premium/leverage/growth from config), renders templates, writes `web/`.
   CLI: `python tools/export_site.py [--no-fetch]` (`--no-fetch` uses a cached
   `data/market_snapshot.csv` for offline/deterministic runs and tests).

2. **`tools/site/charts.py`** — pure Altair chart builders (the 3b rebuilds) +
   a `chart_to_spec(chart) -> dict` helper. No Streamlit import.

3. **`tools/site/returns.py`** — local copy of `base_case_returns` (pure pandas).

4. **`tools/site/templates/`** — Jinja2:
   - `base.html` — shared shell (head, dark CSS link, vega-embed CDN script).
   - `index.html` — leaderboard: 3 charts + the ranked numeric table + intro
     copy (thesis one-liner, "as of" date, link to live Streamlit app + repo).
   - `tearsheet.html` — per company: screening rationale, sources & uses
     (chart + table), debt schedule table, IS/BS/CFS tables, sensitivity grids.

5. **`tools/site/style.css`** — dark theme matching the app
   (`#0e1117` bg, `#1a1d24` panels, `#4f8bf9` accent, `#e6e6e6` text).

6. **`web/`** — committed generated output:
   ```
   web/index.html
   web/t/<TICKER>.html         # 6 files
   web/assets/style.css
   web/assets/specs/<name>.json # Vega-Lite specs
   ```

7. **`vercel.json`** — static serve rooted at `web/`, no build command, no
   Python runtime. Clean URLs for `/t/<TICKER>`.

## Data flow per page

- **index.html:** `apply_screen` output (full 46 for the criteria/bubble context,
  but only passers highlighted) → `base_case_returns` for the 6 → 3 charts +
  table. Includes generation timestamp ("Data as of YYYY-MM-DD").
- **tearsheet.html (×6):** for each passing row, `run_lbo` in market mode →
  sources & uses dict, debt schedule, three statements, sensitivity grids →
  rendered as HTML tables; waterfall chart embedded as Vega spec.

## Numbers: market take-private base case

Each tear sheet uses the same defaults as the app's "Market take-private" mode:
`entry_ev = market_cap × (1 + control_premium_pct/100) + net_debt`, config
leverage, `revenue_growth`, flat exit multiple. The degenerate-EV guard
(net cash > market cap → negative EV, e.g. Just Dial) is carried over: such a
name shows "n.m." for return metrics rather than misleading numbers.

## Error handling

- yfinance failure for a ticker → that name's market cap is NaN → it fails
  `pass_mcap` → drops out of the passer set naturally (same as the app). The
  exporter logs which names were fetched vs. missing.
- If **zero** names pass (e.g. total yfinance outage), the exporter aborts with a
  clear error and writes nothing, rather than committing an empty site.
- `--no-fetch` path requires `data/market_snapshot.csv`; absent → clear error.
- Vega spec JSON is validated (json.loads round-trip) before write.

## Testing

`tests/test_export_site.py` (pytest), run against the committed
`data/market_snapshot.csv` via `--no-fetch` for determinism:
- Exporter produces exactly `index.html` + 6 tear sheets + css + N spec files.
- Each of the 6 passing tickers appears as a tear sheet file.
- Every emitted Vega spec is valid JSON and has a `mark`/`encoding`.
- **Parity:** IRR/MOIC rendered per name equal `base_case_returns` /
  `run_lbo` outputs to the displayed precision (guards against the 3b copies
  drifting numerically from `src/`).
- Degenerate name (if present in snapshot) renders "n.m.", not a number.

A `data/market_snapshot.csv` is captured once from a live fetch and committed so
tests and `--no-fetch` rebuilds are deterministic and offline.

## Isolation & rollout

- All work on branch `feat/static-site-export-vercel`. `main` and the live
  Streamlit deploy are untouched until review + approved merge.
- Manual verification: open `web/index.html` locally, spot-check against the
  running Streamlit app for the same names, then deploy the branch as a Vercel
  preview before merging.
- README gains a second link ("Static showcase (Vercel)") alongside the existing
  live-demo link.

## Out of scope / future

- Option B (client-side interactive LBO in JS) — deferred; would need a
  Python↔JS parity harness.
- Scheduled GitHub Action rebuild — deferred.
- Failing-name pages — deferred.
- 3a (extract shared `src/charts.py`) — deferred; revisit only if cosmetic
  chart drift between app and site becomes a real problem.
