# India LBO Take-Private Screener

**A data-driven screen for NSE-listed mid-cap take-private candidates** — built around
India's February 2026 acquisition-finance rule change that made onshore leveraged
buyouts viable for the first time.

**▶ [Live dashboard](https://india-lbo-take-pv-screener.vercel.app/)** · refreshed weekly from live market data

---

## What this is

India's RBI raised the acquisition-finance cap to **75% of acquisition value** in
February 2026, unlocking onshore leveraged take-privates. This tool screens the
NSE mid/small-cap universe for the companies best positioned to be targets: low
current leverage, strong and consistent free cash flow, promoter holding in the
right band, and a market cap that fits realistic sponsor cheque sizes.

For each candidate that clears the screen, it runs a **paper LBO** — a
revenue-driven three-statement model (IS / BS / CFS that articulate) on a
multi-tranche cash-sweep waterfall — and surfaces IRR, MOIC, sensitivity grids,
Monte Carlo distributions, and a delisting feasibility estimate.

The thesis is intentional: find companies with *unused* debt capacity, not companies
that are already levered. A promoter (or a sponsor partnering with one) levers the
balance sheet at entry, and the company's own cash flows deleverage it over a
5-year hold.

---

## Live dashboard

The [Next.js dashboard](https://india-lbo-take-pv-screener.vercel.app/) shows:

- **Screener leaderboard** — passers ranked by base-case IRR with feasibility scores
- **Scenario war room** — cross-company Bull / Base / Bear IRR table on the dashboard; full P&L bridge (assumptions → financials → returns) on each tearsheet, pre-computed at build time from explicit lever deltas in config
- **Iso-IRR frontier** — the premium / exit-multiple combinations that hit a target return
- **IRR driver tornado** — one-at-a-time P10/P90 swing of each driver (growth, margin, exit multiple) in actual percentage-point IRR terms, alongside the Sobol variance decomposition that shows which driver explains the most return variance
- **Per-company tearsheet** — returns bridge, value bridge, Monte Carlo histogram, sensitivity heatmap, IRR tornado, three statements, debt waterfall, solver outputs (max bid premium, optimal exit year, debt capacity ceiling), delisting mechanics

The Python model runs locally (or in weekly CI) and writes `results.json`; the
Next.js app renders it statically. No Python runs on Vercel.

---

## Thesis: why screen for *unused* debt capacity

This is not a classic 5–7x LBO screen. Domestic leveraged take-privates in India
were historically near-impossible — RBI rules prevented lending against a target's
shares for acquisitions, so sponsors relied on offshore structures or all-equity
deals. The **February 2026 Amendment Directions** changed this: the cap was raised
to **75% of acquisition value, effective April 1, 2026**.

The screen therefore inverts the usual logic. Instead of looking for levered
companies, it looks for companies that are **currently low-levered with strong,
consistent free cash flow** — companies with *unused* debt capacity. A promoter (or
sponsor partnering with one) could take such a company private, lever it to ~3x
EBITDA, and let the cash flows deleverage the structure over a 5-year hold.

---

## Screening criteria

All thresholds live in [`config/config.yaml`](config/config.yaml).

| Criterion | Default | Rationale |
|---|---|---|
| Net debt / EBITDA | < 2.0x | Headroom is the opportunity |
| EBITDA / interest | > 3.0x | Must service existing debt comfortably |
| Positive FCF | last 3 years | Debt paydown comes entirely from FCF |
| EBITDA margin | > 15%, stable | Margin trend filters structural deterioration |
| Promoter holding | 50–75% | Control band for a take-private; SEBI cap at 75% |
| Promoter pledge | < 5% | High pledge signals a stressed counterparty |
| Market cap | ₹1,700–17,000 cr | Feasible cheque sizes for India-focused sponsors |

Banks and NBFCs are excluded — leverage screens are meaningless for balance-sheet lenders.

---

## LBO model

[`src/lbo_model.py`](src/lbo_model.py) is a **revenue-driven three-statement build**
with a multi-tranche cash-sweep waterfall. It is screening-grade, not underwriting-grade.

**Default capital structure:** senior tranche (2.0× EBITDA @ 9%, 10% annual amort) +
mezzanine (1.0× @ 13%, bullet) = 3.0× total, capped at the RBI 75%-of-EV limit.

**Returns at defaults:** MOIC ≈ 2.07× / IRR ≈ 15.6% for the top screen passer.
Transaction and financing fees are modelled explicitly (capitalized into goodwill and
DFC respectively) and drag returns relative to a fee-free build.

**Analytical outputs per company:**
- IRR / MOIC / returns bridge
- Bull / Base / Bear scenario war room (pre-computed; levers in `config/config.yaml`)
- Monte Carlo (1,024-path) with P(beat hurdle) and downside VaR
- Sobol variance decomposition across growth, margin shock, exit multiple
- IRR driver tornado (P10/P90 one-at-a-time swing, in percentage-point IRR terms)
- Iso-IRR frontier (premium % vs. exit multiple contour at target IRR)
- 5×5 sensitivity grid (entry multiple × total leverage)
- Max-bid solver, optimal-exit solver, debt-capacity ceiling

---

## Data

- **Financials:** yfinance (4–5 fiscal years of revenue, EBITDA, net debt, interest, FCF)
- **Promoter holding / pledge:** hand-filled from [Screener.in](https://www.screener.in) — blank counts as a fail by design
- **Universe:** ~46 non-financial NSE mid/small-caps across IT services, pharma, chemicals, industrials, consumer durables, auto ancillaries, building materials

Refresh the data:

```bash
python tools/export_data.py            # live yfinance fetch → results.json
python tools/export_data.py --no-fetch # rebuild from cached market_snapshot.csv
```

The weekly GitHub Action (`.github/workflows/weekly.yml`) runs this every Monday
and pushes the refreshed `results.json` — Vercel redeploys automatically.

---

## Running locally

```bash
pip install -r requirements-dev.txt
pytest -q                              # 60 tests
python tools/export_data.py --no-fetch # build results.json from cached data
cd web-app && npm install && npm run dev
```

The Next.js app runs at `localhost:3000`. The Python model and Next.js app are
fully independent — the handoff is the JSON file.

---

## Limitations

- **Screening-grade model.** No management rollover, PIK interest, purchase-price
  write-ups, deferred taxes, or NOL carryforwards. Exit multiple is held flat by
  construction.
- **Free-data constraints.** yfinance market caps can be stale; promoter pledge on
  Screener.in lags filings by up to a quarter.
- **Regulatory simplification.** The 75% RBI cap is applied mechanically; end-use
  restrictions and the practical pace of Indian acquisition-finance lending are not
  modelled.
- **No view on willingness.** The screen finds companies that *could* be taken
  private, not promoters who *want* to. India's reverse book-building delisting
  process is estimated but not fully modelled.
