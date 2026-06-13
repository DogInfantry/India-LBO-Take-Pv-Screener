# India LBO & Take-Private Screener

A screening tool for NSE-listed mid/small-cap companies that identifies
**take-private deleveraging candidates** and runs a simplified paper LBO on
each. Built as an analyst's screen with an explicit investment thesis, not a
generic stock screener.

## Thesis: why screen for *unused* debt capacity

This is not a classic 5–7x leveraged buyout screen. Domestic LBOs in India
were historically near-impossible: RBI rules prevented banks from lending
against a target's shares to fund acquisitions, so sponsors relied on offshore
structures or all-equity deals. RBI's **February 2026 Amendment Directions**
changed this — the acquisition-finance cap was raised to **75% of acquisition
value, effective April 1, 2026** — opening the door to onshore leveraged
take-privates for the first time.

The screen therefore inverts the usual logic. Instead of looking for levered
companies, it looks for companies that are **currently low-levered with
strong, consistent free cash flow** — i.e., companies with *unused* debt
capacity. A promoter (or sponsor partnering with one) could take such a
company private, lever it to a moderate ~3x EBITDA, and let the cash flows
deleverage the structure over a 5-year hold. The regulatory change is the
tailwind; the balance-sheet headroom is the opportunity.

## Methodology: screening criteria and why

All thresholds live in [config/config.yaml](config/config.yaml) and are easy
to tweak.

| Criterion | Default | Why |
|---|---|---|
| Net debt / EBITDA | < 2.0x | Low current leverage is the unused debt capacity the thesis depends on. Net-cash names (negative net debt) pass trivially. |
| Interest coverage (EBITDA / interest) | > 3.0x | The company must already service its obligations comfortably before any acquisition debt is added. |
| Positive FCF | each of last 3 years | Debt paydown in the LBO comes entirely from FCF; one bad year breaks a 100% cash sweep. FCF yield is computed against live market cap. |
| EBITDA margin | > 15%, stable or improving | Margin level proxies pricing power; the trend test (recent 2-yr avg vs. earlier years, 1.5pp tolerance) filters structurally deteriorating businesses. |
| Promoter holding | 50–75% | Below 50%, the promoter lacks the control to drive a take-private. 75% is SEBI's ceiling on non-public shareholding, so holdings above it don't occur in compliant companies. |
| Promoter pledge | < 5% | High pledge signals a stressed promoter — the wrong counterparty for a leveraged transaction. |
| Market cap | ₹1,700–17,000 cr (~$200M–2B) | Mid/small-cap band where take-private cheque sizes are feasible for India-focused sponsors. |

Survivors are ranked by **FCF yield** (latest FCF / market cap) — the
cheapest sustainable cash flow ranks first. The tool also reports **unused
debt capacity**: `3x EBITDA − current net debt`, the incremental debt the
balance sheet could absorb at the modelled leverage level.

Banks and NBFCs are excluded from the universe entirely — leverage and
coverage screens are meaningless for balance-sheet lenders.

## Paper-LBO assumptions

The model ([src/lbo_model.py](src/lbo_model.py)) is a **revenue-driven
three-statement build** — an Income Statement, Balance Sheet, and Cash Flow
Statement that articulate, with the **balance sheet balancing every year** as
the integrity check — sitting on top of a **multi-tranche cash-sweep waterfall**.
It is screening-grade (assumption-driven), not a full underwriting model, but it
now carries transaction/financing fees and a days-based working-capital build.
Assumptions, all configurable:

- **Driver:** revenue grows at `revenue_growth`; the entry EBITDA margin
  (`entry_ebitda / entry_revenue`, read from the fundamentals CSV) is held flat,
  so EBITDA = revenue × margin.
- **Entry:** EV = LTM EBITDA × 8.0x entry multiple.
- **Debt tranches:** an ordered list in [config/config.yaml](config/config.yaml),
  index 0 = most senior. Each tranche has a size (`turns` × LTM EBITDA), a
  cash interest `rate`, and a `mandatory_amort_pct` (fraction of original
  principal repaid contractually each year; 0 = bullet). The default stack is
  senior (2.0x @ 9.0%, 10% amort) + mezzanine (1.0x @ 13.0%, bullet), totalling
  3.0x. A revolver (`revolver_rate`) catches funding gaps.
- **Sources & uses:** total debt = Σ(tranche turns) × EBITDA, **capped at RBI's
  75% of acquisition value** — if the cap binds, all tranches scale down
  proportionally. **Fees** are layered on top of the purchase price:
  - *Transaction fees* (`txn_fee_pct_of_ev` × EV — M&A/legal/diligence) are
    **equity-funded and folded into goodwill**. Since the model has no Year-0
    income statement to expense them through, they are capitalized into goodwill
    as a simplification rather than run through a P&L.
  - *Financing fees* (`financing_fee_pct_of_debt` × debt — arrangement/OID) are
    **capitalized as a deferred-financing-cost (DFC) asset** and amortized
    straight-line over the hold; the amortization is a non-cash IS expense added
    back in CFO, creating a small tax shield.

  Both fees are funded by sponsor equity, so
  **sponsor equity = EV + transaction fees + financing fees − total debt**.
- **Opening balance sheet:** cash-free / debt-free. Opening PP&E is synthesized
  from `ppe_pct_of_revenue` × entry revenue and opening working capital from the
  days-based build below; the DFC asset is seeded at the financing fee.
  **Goodwill is the plug**:
  `goodwill = EV + transaction fees − opening PP&E − opening NWC`, so
  Assets = Liabilities + Equity on Day 1. Goodwill is held flat. *This opening BS
  is assumption-driven, not a real purchase-price allocation.*
- **Income statement:** EBIT = EBITDA − D&A (`da_pct_of_ppe` × opening PP&E) −
  DFC amortization (financing fee ÷ hold years, a non-cash expense);
  EBT = EBIT − cash interest (blended across tranches + revolver, on opening
  balances); taxes = `tax_rate` × max(0, EBT) (floored at zero, no NOL carry);
  net income = EBT − taxes.
- **Days-based working capital:** opening and each year's working capital are
  built from days assumptions rather than a single ratio. AR keys off revenue;
  inventory and AP key off COGS (= `cogs_pct_of_revenue` × revenue):
  - AR = `dso_days` ÷ 365 × revenue
  - inventory = `dio_days` ÷ 365 × COGS
  - AP = `dpo_days` ÷ 365 × COGS

  NWC = AR + inventory − AP. (This replaces the older single net-working-capital
  ratio.)
- **Cash flow & FCF for debt:** CFO = net income + D&A + DFC amortization − ΔNWC;
  capex = `capex_pct_of_revenue` × revenue (genuinely separate from D&A);
  **FCF available for debt = CFO − capex**. PP&E rolls forward:
  PP&E = prior PP&E + capex − D&A. The DFC asset amortizes straight-line to zero
  by the end of the hold.
- **Waterfall:** each year, **mandatory amortization** is paid first on every
  tranche; remaining FCF is then **swept down the priority stack** — revolver
  first, then senior, then mezzanine — so a junior tranche's principal cannot
  fall via the sweep until every senior tranche is retired. A funding shortfall
  draws the revolver.
- **Balance check:** the cash line is the cash-flow-statement plug and the
  balance sheet ties every year (`max_balance_error` ≈ 0). The tear sheet shows a
  "balance sheet ties ✓" indicator.
- **Exit:** flat multiple — exit EV = entry multiple × Year-5 EBITDA. No
  multiple expansion; returns come from deleveraging and EBITDA growth only.
- **Returns:** MOIC = exit equity / entry equity; exit equity = exit EV − exit
  net debt (debt − cash). Because there is a single cash flow out at exit,
  IRR = MOIC^(1/5) − 1 in closed form. At defaults the run now returns
  **MOIC ≈ 2.09x / IRR ≈ 15.8%**, down from the pre-fee build (~2.18x / ~16.9%):
  the larger equity cheque from transaction and financing fees drags returns,
  only partially offset by the DFC amortization tax shield.
- **Sensitivity:** IRR and MOIC across a 5×5 grid of entry multiple × **total
  leverage**; each leverage column scales all tranches proportionally.

## Data sources

- **yfinance** is used *only* for live price, market cap and shares
  outstanding (`.NS` tickers). Its historical financial statements are capped
  at ~4 years and have known alignment bugs, so they are not used.
- **Fundamentals are manual CSV input** — 10 years of consolidated figures
  per company, populated by hand from Screener.in.

### Populating the fundamentals CSV from Screener.in

1. Open the company page on [screener.in](https://www.screener.in) (logged
   in), switch to **Consolidated** figures, and use **Export to Excel**.
2. For each fiscal year, fill one row in
   [data/fundamentals_template.csv](data/fundamentals_template.csv):

   | Column | Screener.in source |
   |---|---|
   | `revenue_cr` | P&L → Sales |
   | `ebitda_cr` | P&L → Operating profit (+ other operating income if material) |
   | `net_debt_cr` | Balance sheet → Borrowings − cash & investments (negative = net cash) |
   | `interest_expense_cr` | P&L → Interest |
   | `fcf_cr` | Cash flow → CFO − capex (Screener shows "Free cash flow" in the cash-flow section) |
   | `promoter_holding_pct` | Shareholding pattern (latest quarter) |
   | `promoter_pledge_pct` | Shareholding pattern → pledged % of promoter holding |

3. All ₹ figures are in **crore**; `year` uses `FY16`-style labels;
   promoter columns can simply repeat the latest values on every row of a
   company (the screener reads them from the most recent year).

The template ships with two filled examples — **Infosys and TCS** — chosen
because their figures are public and well known. *The example numbers are
approximations for format illustration, not audited figures; replace them
with your own universe.* (Both are also far outside the mid-cap band, so they
correctly fail the market-cap screen.)

The starter universe ([data/universe.csv](data/universe.csv)) holds ~45
non-financial NSE mid/small-caps drawn from Nifty Midcap/Smallcap
constituents across IT services, auto ancillaries, consumer durables,
building materials, chemicals, pharma, industrials and QSR.

## How to run

```bash
pip install -r requirements.txt
streamlit run src/app.py
```

`python smoke_test.py` runs an offline sanity check of the full pipeline
(loader → screen → LBO → sensitivity) against the bundled example data.

The dashboard has two views:

1. **Shortlist** — every company in the fundamentals CSV with its metrics,
   per-criterion pass/fail detail, ranked with survivors first.
2. **Company tear sheet** — screening rationale paragraph, sources & uses,
   year-by-year debt paydown schedule, MOIC/IRR, and the sensitivity grid,
   with entry multiple / leverage / growth adjustable live.

A sidebar toggle disables yfinance for offline work (market-cap-dependent
criteria then fail by design rather than erroring).

## Limitations

- **Manual data entry.** Fundamentals are hand-keyed from Screener.in;
  transcription errors are possible, and the screen only covers companies you
  have entered. Screener.in's "operating profit" can differ from reported
  EBITDA for companies with significant other income.
- **Simplified LBO.** The model is now a revenue-driven three-statement build
  (IS/BS/CFS that tie out) on a multi-tranche cash-sweep waterfall, with
  transaction/financing fees and a days-based AR/inventory/AP working-capital
  build, but it stays screening-grade: the opening balance sheet is
  assumption-driven (goodwill as a plug, not a real purchase-price allocation),
  the exit multiple is held flat by construction, and it still omits management
  rollover, PIK interest, purchase-price write-ups, deferred taxes, and NOL
  carryforwards. Outputs are screening-grade, not underwriting-grade.
- **Free-data constraints.** yfinance market caps can be stale or missing for
  thinly traded names; promoter pledge data on Screener.in lags exchange
  filings by up to a quarter.
- **Regulatory simplification.** The RBI 75% cap is applied mechanically;
  the model ignores end-use restrictions, pricing norms, and the practical
  pace at which Indian banks will actually write acquisition-finance cheques.
- **No view on willingness.** The screen finds companies that *could* be
  taken private, not promoters who *want* to. Delisting in India also
  requires a reverse book-building process the model does not capture.
