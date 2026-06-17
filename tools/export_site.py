"""Generate the static showcase site (web/) from the screener + LBO model.

A point-in-time snapshot of the screen and a paper LBO on each passing name,
rendered to static HTML that Vercel serves. This is the "showcase" companion to
the interactive Streamlit app — it imports the SAME src/ functions (no copy of
the model math) and renders their output to HTML; chart specs are rebuilt
locally (see tools/site/charts.py) only because the Streamlit app is not
import-safe.

Usage:
  python tools/export_site.py                 # live yfinance fetch
  python tools/export_site.py --no-fetch      # use data/market_snapshot.csv

Output: web/index.html, web/t/<TICKER>.html (one per passer), web/assets/.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

import altair as alt
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from data_loader import load_config, load_fundamentals, load_universe, fetch_market_data
from lbo_model import run_lbo, sensitivity_grid_premium
from screener import apply_screen, build_rationale, compute_metrics
from sitegen.charts import (chart_to_spec, criteria_leaderboard, irr_leaderboard,
                            sources_uses_waterfall, sweet_spot_bubble)
from sitegen.returns import base_case_returns

OUT_DIR = PROJECT_ROOT / "web"
PKG_DIR = PROJECT_ROOT / "tools" / "sitegen"
TEMPLATE_DIR = PKG_DIR / "templates"
SNAPSHOT_PATH = PROJECT_ROOT / "data" / "market_snapshot.csv"
LIVE_APP_URL = "https://india-lbo-take-pv-screener-7hv5yfvgmabjk5rnuyqdqj.streamlit.app/"
REPO_URL = "https://github.com/DogInfantry/India-LBO-Take-Pv-Screener"


# ----------------------------------------------------------------- formatting
def cr0(x) -> str:
    return "—" if pd.isna(x) else f"{x:,.0f}"


def pct1(x) -> str:
    return "—" if pd.isna(x) else f"{x * 100:.1f}%"


def mult1(x) -> str:
    return "—" if pd.isna(x) else f"{x:.1f}x"


def mult2(x) -> str:
    return "—" if pd.isna(x) else f"{x:.2f}x"


def cov(x) -> str:
    if pd.isna(x):
        return "—"
    return "n.m." if x == float("inf") else f"{x:,.1f}x"


# ----------------------------------------------------------------- HTML tables
def render_df(df: pd.DataFrame, value_fmt: str = "{:,.0f}", na_rep: str = "—") -> Markup:
    """Generic data table: first column left-aligned text, rest formatted nums."""
    cols = list(df.columns)
    head = "".join(f"<th>{c}</th>" for c in cols)
    body = []
    for _, row in df.iterrows():
        tds = []
        for i, c in enumerate(cols):
            v = row[c]
            if i == 0:
                tds.append(f"<td>{v}</td>")
            elif pd.isna(v):
                tds.append(f"<td>{na_rep}</td>")
            else:
                try:
                    tds.append(f"<td>{value_fmt.format(v)}</td>")
                except (ValueError, TypeError):
                    tds.append(f"<td>{v}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    return Markup(f'<table class="data"><thead><tr>{head}</tr></thead>'
                  f'<tbody>{"".join(body)}</tbody></table>')


def render_heat(df: pd.DataFrame, fmt) -> Markup:
    """Sensitivity grid with an RdYlGn background gradient (matches the app's
    Styler.background_gradient(cmap='RdYlGn', axis=None) — global min/max)."""
    import numpy as np
    from matplotlib import colormaps
    import matplotlib.colors as mcolors

    cmap = colormaps["RdYlGn"]
    vals = df.to_numpy(dtype=float)
    vmin, vmax = np.nanmin(vals), np.nanmax(vals)
    rng = (vmax - vmin) or 1.0

    head = "<th></th>" + "".join(f"<th>{c}</th>" for c in df.columns)
    body = []
    for idx, row in df.iterrows():
        tds = [f"<td>{idx}</td>"]
        for c in df.columns:
            v = row[c]
            if pd.isna(v):
                tds.append("<td>—</td>")
            else:
                bg = mcolors.to_hex(cmap((v - vmin) / rng))
                tds.append(f'<td class="h" style="background:{bg}">{fmt(v)}</td>')
        body.append("<tr>" + "".join(tds) + "</tr>")
    return Markup(f'<table class="data heat"><thead><tr>{head}</tr></thead>'
                  f'<tbody>{"".join(body)}</tbody></table>')


def specs_payload(specs: dict) -> Markup:
    """JSON for the embedded <script>, hardened against a </script> breakout."""
    raw = json.dumps(specs).replace("</", "<\\/")
    return Markup(raw)


def vega_scripts() -> list[str]:
    """The exact vega/vega-lite/vega-embed CDN URLs Altair itself uses, so the
    embedded specs always match the installed Altair version."""
    html = (alt.Chart(pd.DataFrame({"a": [1]})).mark_bar().encode(x="a:Q")
            .to_html())
    urls, seen = [], set()
    for u in re.findall(r'src="(https://cdn\.jsdelivr\.net/npm/vega[^"]+)"', html):
        if u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


# ----------------------------------------------------------------- data build
def gather(no_fetch: bool):
    cfg = load_config()
    fundamentals = load_fundamentals()
    universe = load_universe()
    tickers = list(fundamentals["ticker"].unique())

    if no_fetch:
        if not SNAPSHOT_PATH.exists():
            sys.exit(f"--no-fetch needs {SNAPSHOT_PATH} (run once without it to capture).")
        market = pd.read_csv(SNAPSHOT_PATH)
    else:
        print(f"Fetching live market data for {len(tickers)} tickers...")
        market = fetch_market_data(tickers)
        market.to_csv(SNAPSHOT_PATH, index=False)
        print(f"  cached snapshot -> {SNAPSHOT_PATH}")

    results = apply_screen(compute_metrics(fundamentals, market, cfg), cfg)
    return cfg, universe, results


# ----------------------------------------------------------------- tear sheet
def build_tearsheet_context(row: pd.Series, cfg: dict, data_date: str) -> tuple[dict, dict]:
    """Return (template_context, chart_specs) for one passing company."""
    lbo_cfg = cfg["lbo"]
    total_turns = sum(t["turns"] for t in lbo_cfg["tranches"])
    prem = float(lbo_cfg.get("control_premium_pct", 25.0))

    equity_offer = row["market_cap_cr"] * (1 + prem / 100)
    entry_ev = equity_offer + row["net_debt_cr"]
    result = run_lbo(row["revenue_cr"], row["ebitda_cr"], lbo_cfg,
                     entry_ev=entry_ev, total_leverage=total_turns)
    su = result["sources_uses"]
    degenerate = su["enterprise_value"] <= 0.05 * row["ebitda_cr"]

    # sources & uses table (same order as the app)
    su_rows = [(t["name"].capitalize() + " debt", cr0(t["amount"]))
               for t in su["tranches"]]
    su_rows += [("Total debt", cr0(su["debt"])),
                ("Transaction fees", cr0(su["txn_fees"])),
                ("Financing fees (capitalized)", cr0(su["financing_fees"])),
                ("Sponsor equity", cr0(su["sponsor_equity"])),
                ("Enterprise value", cr0(su["enterprise_value"]))]

    # debt schedule — rename exactly like the app
    base_renames = {
        "year": "Year", "ebitda": "EBITDA", "interest": "Interest",
        "taxes": "Taxes", "capex": "Capex", "delta_nwc": "ΔNWC",
        "fcf_for_debt": "FCF for debt", "revolver": "Revolver", "cash": "Cash",
        "ending_debt": "Ending debt"}
    tranche_renames = {c: c.replace("_", " ").capitalize()
                       for c in result["schedule"].columns
                       if c.endswith("_repaid") or c.endswith("_ending")}
    sched = result["schedule"].rename(columns={**base_renames, **tranche_renames})

    statements = [
        {"name": "Income statement", "table": render_df(result["income_statement"])},
        {"name": "Balance sheet", "table": render_df(result["balance_sheet"])},
        {"name": "Cash flow", "table": render_df(result["cash_flow"])},
    ]

    # sensitivity grids (premium × leverage)
    sens = cfg["sensitivity"]
    irr_grid, moic_grid = sensitivity_grid_premium(
        row["revenue_cr"], row["ebitda_cr"], lbo_cfg,
        row["market_cap_cr"], row["net_debt_cr"],
        sens["premiums_pct"], sens["leverage_multiples"])
    irr_grid.index = [f"{p:.0f}%" for p in irr_grid.index]
    moic_grid.index = [f"{p:.0f}%" for p in moic_grid.index]
    irr_grid.columns = [f"{c:.1f}x" for c in irr_grid.columns]
    moic_grid.columns = [f"{c:.1f}x" for c in moic_grid.columns]

    ctx = {
        "name": row["ticker"].replace(".NS", ""),
        "data_date": data_date,
        "verdict_pill": "Passes all screening criteria",
        "rationale": build_rationale(row, cfg),
        "metrics": [
            {"label": "LTM EBITDA", "value": f"₹{cr0(row['ebitda_cr'])} cr"},
            {"label": "Net debt/EBITDA", "value": mult2(row["net_debt_to_ebitda"])},
            {"label": "Market cap", "value": f"₹{cr0(row['market_cap_cr'])} cr"},
            {"label": "Unused debt capacity",
             "value": f"₹{cr0(row['unused_debt_capacity_cr'])} cr"},
        ],
        "entry_note": (
            f"Implied entry {result['entry_multiple']:.1f}x EBITDA · equity offer "
            f"₹{cr0(equity_offer)} cr (₹{cr0(row['market_cap_cr'])} cr market cap "
            f"+{prem:.0f}%) + net debt ₹{cr0(row['net_debt_cr'])} cr = entry EV "
            f"₹{cr0(entry_ev)} cr."),
        "su_rows": su_rows,
        "su_note": (
            f"Total debt = {su['debt_pct_of_ev']:.0%} of EV (RBI cap: 75% of "
            f"acquisition value). Equity check includes "
            f"₹{cr0(su['txn_fees'] + su['financing_fees'])} cr of fees "
            "(transaction folded into goodwill; financing capitalized & amortized)."),
        "returns": {
            "exit_label": "flat exit multiple",
            "moic": "n.m." if degenerate else mult2(result["moic"]),
            "irr": "n.m." if degenerate else pct1(result["irr"]),
            "exit_equity": "n.m." if degenerate else f"₹{cr0(result['exit_equity'])} cr",
            "note": (
                f"Exit EV ₹{cr0(result['exit_ev'])} cr at {result['exit_multiple']:.1f}x "
                f"Year-5 EBITDA (entry {result['entry_multiple']:.1f}x); exit net debt "
                f"₹{cr0(result['exit_net_debt'])} cr."),
        },
        "balance_note": (
            f"Balance sheet ties ✓ (max imbalance ₹{result['max_balance_error']:.2e} cr)"
            if result["max_balance_error"] < 1e-6
            else f"Balance sheet does NOT tie — ₹{result['max_balance_error']:,.2f} cr"),
        "schedule_table": render_df(sched),
        "statements": statements,
        "sens": {
            "title": "Sensitivity — control premium × leverage",
            "irr_table": render_heat(irr_grid, lambda v: f"{v:.1%}"),
            "moic_table": render_heat(moic_grid, lambda v: f"{v:.2f}x"),
            "note": ("Each row prices the take-private at market cap + that premium, "
                     "exiting at the implied entry multiple — returns come from debt "
                     "paydown and EBITDA growth, not multiple expansion."),
        },
        "rel": "../",
    }
    specs = {"waterfall": chart_to_spec(sources_uses_waterfall(su))}
    return ctx, specs


# ----------------------------------------------------------------- index page
def build_index_context(results: pd.DataFrame, cfg: dict, data_date: str) -> tuple[dict, dict, list]:
    lbo = cfg["lbo"]
    prem = lbo.get("control_premium_pct", 25.0)
    lev = sum(t["turns"] for t in lbo["tranches"])
    passed = results[results["passes_screen"]]
    ret = base_case_returns(passed, cfg)
    if ret.empty:
        sys.exit("No passing names with market data — nothing to render. Aborting.")

    candidates = [{
        "name": r["name"],
        "href": f"t/{r['name']}.html",
        "irr": "n.m." if pd.isna(r["irr"]) else pct1(r["irr"]),
        "moic": "n.m." if pd.isna(r["moic"]) else mult2(r["moic"]),
        "implied_mult": mult1(r["implied_mult"]),
        "equity": f"₹{cr0(r['equity_cr'])} cr",
    } for _, r in ret.iterrows()]

    n_criteria = sum(c.startswith("pass_") for c in results.columns)
    rankable = ret.dropna(subset=["irr"])
    specs = {"criteria": chart_to_spec(criteria_leaderboard(results, n_criteria))}
    if not rankable.empty:
        specs["irr"] = chart_to_spec(irr_leaderboard(rankable))
    bubble = sweet_spot_bubble(results)
    has_bubble = bubble is not None
    if has_bubble:
        specs["bubble"] = chart_to_spec(bubble)

    results_rows = [{
        "ticker": r["ticker"].replace(".NS", ""),
        "market_cap": cr0(r["market_cap_cr"]),
        "ebitda": cr0(r["ebitda_cr"]),
        "margin": pct1(r["ebitda_margin"]),
        "nd_ebitda": mult2(r["net_debt_to_ebitda"]),
        "coverage": cov(r["interest_coverage"]),
        "fcf_yield": pct1(r["fcf_yield"]),
        "unused": cr0(r["unused_debt_capacity_cr"]),
        "promoter": "—" if pd.isna(r["promoter_holding_pct"]) else f"{r['promoter_holding_pct']:.1f}",
        "pledge": "—" if pd.isna(r["promoter_pledge_pct"]) else f"{r['promoter_pledge_pct']:.1f}",
        "cleared": f"{int(r['criteria_passed'])}/{n_criteria}",
        "passes": bool(r["passes_screen"]),
    } for _, r in results.iterrows()]

    ctx = {
        "n_pass": len(passed),
        "n_total": len(results),
        "n_criteria": n_criteria,
        "data_date": data_date,
        "base_note": (
            f"Base case: market take-private at {prem:.0f}% control premium, "
            f"{lev:.1f}x leverage, {lbo['revenue_growth'] * 100:.0f}% revenue growth, "
            "flat exit. Tune any deal on the interactive app."),
        "candidates": candidates,
        "has_bubble": has_bubble,
        "results": results_rows,
        "rel": "",
    }
    return ctx, specs, list(ret["name"])


# ----------------------------------------------------------------- main
def main(argv: list[str]) -> None:
    # Console prints below may carry non-ASCII (e.g. ₹); don't let a Windows
    # cp1252 console abort the build. HTML files are always written utf-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true",
                    help="use data/market_snapshot.csv instead of a live fetch")
    args = ap.parse_args(argv)

    cfg, universe, results = gather(args.no_fetch)
    data_date = date.today().isoformat()
    scripts = vega_scripts()
    common = {"vega_scripts": scripts, "generated_at": data_date,
              "live_app_url": LIVE_APP_URL, "repo_url": REPO_URL}

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)),
                      autoescape=select_autoescape(["html"]))

    # --- index ---
    idx_ctx, idx_specs, ranked_names = build_index_context(results, cfg, data_date)
    index_html = env.get_template("index.html").render(
        **common, **idx_ctx, specs_json=specs_payload(idx_specs))

    # --- tear sheets (in ranked order) ---
    passed = results[results["passes_screen"]].copy()
    passed["_name"] = passed["ticker"].str.replace(".NS", "", regex=False)
    rank = {n: i for i, n in enumerate(ranked_names)}
    passed = passed.sort_values("_name", key=lambda s: s.map(rank))

    tear_pages = {}
    for _, row in passed.iterrows():
        ctx, specs = build_tearsheet_context(row, cfg, data_date)
        tear_pages[ctx["name"]] = env.get_template("tearsheet.html").render(
            **common, **ctx, specs_json=specs_payload(specs))

    # --- write everything (only after all rendering succeeds) ---
    (OUT_DIR / "t").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "assets").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "index.html").write_text(index_html, encoding="utf-8")
    for name, html in tear_pages.items():
        (OUT_DIR / "t" / f"{name}.html").write_text(html, encoding="utf-8")
    (OUT_DIR / "assets" / "style.css").write_text(
        (PKG_DIR / "style.css").read_text(encoding="utf-8"), encoding="utf-8")

    print(f"Wrote {OUT_DIR}/index.html + {len(tear_pages)} tear sheets "
          f"({', '.join(tear_pages)}).")


if __name__ == "__main__":
    main(sys.argv[1:])
