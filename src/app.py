"""Streamlit dashboard: ranked shortlist of screen survivors plus a
per-company tear sheet with sources & uses, debt schedule, returns and a
sensitivity grid.

Run from the project root:  streamlit run src/app.py
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))  # allow running from any cwd

from data_loader import load_config, load_fundamentals, load_universe, fetch_market_data
from lbo_model import run_lbo, sensitivity_grid
from screener import apply_screen, build_rationale, compute_metrics

st.set_page_config(page_title="India LBO Screener", layout="wide")

cfg = load_config()


@st.cache_data(ttl=900, show_spinner="Fetching market data from yfinance...")
def cached_market_data(tickers: tuple[str, ...]) -> pd.DataFrame:
    return fetch_market_data(list(tickers))


@st.cache_data
def load_inputs():
    return load_universe(), load_fundamentals()


universe, fundamentals = load_inputs()

st.title("India LBO & Take-Private Screener")
st.caption(
    "Screens NSE mid/small-caps for take-private deleveraging candidates — "
    "low-levered, cash-generative, promoter-controlled companies with unused "
    "debt capacity under RBI's 2026 acquisition-finance regime — then runs a "
    "simplified paper LBO on each."
)

use_live = st.sidebar.toggle(
    "Fetch live market data (yfinance)", value=True,
    help="Disable to work offline; market-cap-dependent criteria will then fail.")

tickers = tuple(fundamentals["ticker"].unique())
if use_live:
    market = cached_market_data(tickers)
else:
    market = pd.DataFrame({"ticker": list(tickers), "price": None,
                           "market_cap_cr": None, "shares_outstanding": None})

metrics = compute_metrics(fundamentals, market, cfg)
results = apply_screen(metrics, cfg)

n_covered = len(results)
n_universe = len(universe)
if n_covered < n_universe:
    st.sidebar.info(
        f"Fundamentals CSV covers {n_covered} of {n_universe} universe names. "
        "Populate data/fundamentals_template.csv from Screener.in exports to "
        "widen coverage.")

view = st.sidebar.radio("View", ["Shortlist", "Company tear sheet"])

# ---------------------------------------------------------------- shortlist
if view == "Shortlist":
    st.subheader("Screen results")
    passed = results[results["passes_screen"]]
    st.metric("Candidates passing all criteria", f"{len(passed)} / {len(results)}")

    display_cols = {
        "ticker": "Ticker",
        "market_cap_cr": "Mkt cap (₹cr)",
        "ebitda_cr": "EBITDA (₹cr)",
        "ebitda_margin": "EBITDA margin",
        "net_debt_to_ebitda": "Net debt/EBITDA",
        "interest_coverage": "Int. coverage",
        "fcf_yield": "FCF yield",
        "unused_debt_capacity_cr": "Unused debt capacity (₹cr)",
        "promoter_holding_pct": "Promoter %",
        "promoter_pledge_pct": "Pledge %",
        "criteria_passed": "Criteria passed",
        "passes_screen": "Passes",
    }
    table = results[list(display_cols)].rename(columns=display_cols)
    st.dataframe(
        table.style.format({
            "Mkt cap (₹cr)": "{:,.0f}", "EBITDA (₹cr)": "{:,.0f}",
            "EBITDA margin": "{:.1%}", "Net debt/EBITDA": "{:.2f}x",
            "Int. coverage": "{:,.1f}x", "FCF yield": "{:.1%}",
            "Unused debt capacity (₹cr)": "{:,.0f}",
            "Promoter %": "{:.1f}", "Pledge %": "{:.1f}",
        }, na_rep="—"),
        width="stretch", hide_index=True)

    with st.expander("Criterion-level detail"):
        pass_cols = [c for c in results.columns if c.startswith("pass_")]
        st.dataframe(results[["ticker"] + pass_cols], width="stretch",
                     hide_index=True)

# --------------------------------------------------------------- tear sheet
else:
    # Screen survivors first in the picker, but allow inspecting any name.
    order = results["ticker"].tolist()
    ticker = st.selectbox("Company", order)
    row = results[results["ticker"] == ticker].iloc[0]

    st.subheader(f"Tear sheet — {ticker.replace('.NS', '')}")
    st.markdown("**Screening rationale.** " + build_rationale(row, cfg))

    if not row["passes_screen"]:
        st.warning("This company does not pass the screen; the LBO below is "
                   "illustrative only.")

    a, b, c, d = st.columns(4)
    a.metric("LTM EBITDA", f"₹{row['ebitda_cr']:,.0f} cr")
    b.metric("Net debt/EBITDA", f"{row['net_debt_to_ebitda']:.2f}x")
    c.metric("Market cap", f"₹{row['market_cap_cr']:,.0f} cr"
             if pd.notna(row["market_cap_cr"]) else "n.a.")
    d.metric("Unused debt capacity", f"₹{row['unused_debt_capacity_cr']:,.0f} cr")

    st.divider()
    st.subheader("Paper LBO")
    lbo_cfg = cfg["lbo"]
    col1, col2, col3 = st.columns(3)
    total_turns = sum(t["turns"] for t in lbo_cfg["tranches"])
    entry_mult = col1.number_input("Entry multiple (x EBITDA)", 4.0, 15.0,
                                   float(lbo_cfg["entry_multiple"]), 0.5)
    lev_mult = col2.number_input("Total leverage (x EBITDA)", 1.0, 6.0,
                                 float(total_turns), 0.5,
                                 help="Scales all debt tranches proportionally.")
    growth = col3.number_input("EBITDA growth (%)", -5.0, 25.0,
                               lbo_cfg["ebitda_growth"] * 100, 0.5)

    assumptions = {**lbo_cfg, "ebitda_growth": growth / 100}
    result = run_lbo(row["ebitda_cr"], assumptions,
                     entry_multiple=entry_mult, total_leverage=lev_mult)

    su = result["sources_uses"]
    left, right = st.columns(2)
    with left:
        st.markdown("**Sources & uses (₹ cr)**")
        su_rows = [(t["name"].capitalize() + " debt", t["amount"])
                   for t in su["tranches"]]
        su_rows += [("Total debt", su["debt"]),
                    ("Sponsor equity", su["sponsor_equity"]),
                    ("Enterprise value", su["enterprise_value"])]
        st.table(pd.DataFrame(su_rows, columns=["Item", "₹ cr"])
                 .style.format({"₹ cr": "{:,.0f}"}))
        st.caption(f"Total debt = {su['debt_pct_of_ev']:.0%} of EV "
                   f"(RBI cap: 75% of acquisition value).")
    with right:
        st.markdown("**Returns (5-yr hold, flat exit multiple)**")
        m1, m2, m3 = st.columns(3)
        m1.metric("MOIC", f"{result['moic']:.2f}x")
        m2.metric("IRR", f"{result['irr']:.1%}")
        m3.metric("Exit equity", f"₹{result['exit_equity']:,.0f} cr")
        st.caption(f"Exit EV ₹{result['exit_ev']:,.0f} cr at "
                   f"{result['entry_multiple']:.1f}x Year-5 EBITDA; exit net "
                   f"debt ₹{result['exit_net_debt']:,.0f} cr.")

    st.markdown("**Debt paydown schedule (₹ cr)**")
    base_renames = {
        "year": "Year", "ebitda": "EBITDA", "interest": "Interest",
        "taxes": "Taxes", "capex": "Capex", "delta_wc": "ΔWC",
        "levered_fcf": "Levered FCF", "revolver": "Revolver", "cash": "Cash",
        "ending_debt": "Ending debt"}
    # Per-tranche columns (e.g. senior_repaid, mezzanine_ending) -> "Senior repaid"
    tranche_renames = {c: c.replace("_", " ").capitalize()
                       for c in result["schedule"].columns
                       if c.endswith("_repaid") or c.endswith("_ending")}
    sched = result["schedule"].rename(columns={**base_renames, **tranche_renames})
    st.dataframe(sched.style.format("{:,.0f}", subset=sched.columns[1:]),
                 width="stretch", hide_index=True)
    st.line_chart(sched.set_index("Year")[["Ending debt", "Levered FCF"]])

    st.markdown("**Sensitivity — IRR (entry multiple × leverage)**")
    sens = cfg["sensitivity"]
    irr_grid, moic_grid = sensitivity_grid(
        row["ebitda_cr"], assumptions,
        sens["entry_multiples"], sens["leverage_multiples"])
    st.dataframe(irr_grid.style.format("{:.1%}")
                 .background_gradient(cmap="RdYlGn", axis=None),
                 width="stretch")
    st.markdown("**Sensitivity — MOIC**")
    st.dataframe(moic_grid.style.format("{:.2f}x")
                 .background_gradient(cmap="RdYlGn", axis=None),
                 width="stretch")
    st.caption("Exit multiple held flat at the entry multiple in every "
               "scenario — returns come from debt paydown and EBITDA growth, "
               "not multiple expansion.")
