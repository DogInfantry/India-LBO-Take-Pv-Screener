"""Altair chart builders for the static site export.

These are deliberately STANDALONE copies of the chart specs that live inside
`src/app.py` (decision "3b" in the design spec): the Streamlit app is not
import-safe from a non-Streamlit process (it runs `st.set_page_config` at import
time), so rather than touch a single line of `src/`, the exporter rebuilds the
chart specs here. The accepted cost is cosmetic duplication — the *numbers* are
not duplicated (they come straight from `src/` via the exporter), only the
visual styling. A drift in styling is harmless; a drift in the underlying data
is caught by the parity tests.

Every builder returns an `alt.Chart`; `chart_to_spec` renders it to a Vega-Lite
spec dict that the templates embed with vega-embed.js, so in-chart tooltips and
hover survive on the otherwise-static page.
"""

import altair as alt
import pandas as pd

# Shared palette — mirrors the Streamlit app + the site's dark CSS.
_GREEN = "#2e8b57"
_RED = "#c25b5b"
_GREY = "#b0b7c0"
_VERDICT_SCALE = alt.Scale(domain=["Passes all", "Falls short"],
                           range=[_GREEN, _GREY])


def chart_to_spec(chart: alt.Chart) -> dict:
    """Vega-Lite spec dict for embedding, sized to its container width."""
    spec = chart.properties(width="container").to_dict()
    return spec


def irr_leaderboard(ret: pd.DataFrame) -> alt.Chart:
    """Horizontal IRR bars for ranked survivors + a dashed 20% PE-hurdle rule.

    `ret` is the output of base_case_returns (one row per name with irr/moic/
    implied_mult/equity_cr), already NaN-dropped on irr by the caller.
    """
    bars = (
        alt.Chart(ret)
        .mark_bar(color=_GREEN)
        .encode(
            x=alt.X("irr:Q", title="Base-case IRR", axis=alt.Axis(format="%")),
            y=alt.Y("name:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("name:N", title="Company"),
                alt.Tooltip("irr:Q", title="IRR", format=".1%"),
                alt.Tooltip("moic:Q", title="MOIC", format=".2f"),
                alt.Tooltip("implied_mult:Q", title="Implied entry (x)", format=".1f"),
                alt.Tooltip("equity_cr:Q", title="Equity check (₹cr)", format=",.0f"),
            ],
        )
        .properties(height=max(140, 34 * len(ret)))
    )
    hurdle = (
        alt.Chart(pd.DataFrame({"h": [0.20]}))
        .mark_rule(color=_RED, strokeDash=[4, 4])
        .encode(x="h:Q")
    )
    return bars + hurdle


def criteria_leaderboard(results: pd.DataFrame, n_criteria: int) -> alt.Chart:
    """One bar per company: criteria cleared, green if it passes all."""
    chart_df = results.assign(
        name=results["ticker"].str.replace(".NS", "", regex=False),
        verdict=results["passes_screen"].map(
            {True: "Passes all", False: "Falls short"}),
    )
    return (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            x=alt.X("criteria_passed:Q",
                    title=f"Criteria cleared (of {n_criteria})",
                    scale=alt.Scale(domain=[0, n_criteria])),
            y=alt.Y("name:N", sort="-x", title=None),
            color=alt.Color("verdict:N", scale=_VERDICT_SCALE, title=None),
            tooltip=[
                alt.Tooltip("name:N", title="Company"),
                alt.Tooltip("criteria_passed:Q", title="Criteria cleared"),
                alt.Tooltip("net_debt_to_ebitda:Q", title="Net debt/EBITDA", format=".2f"),
                alt.Tooltip("fcf_yield:Q", title="FCF yield", format=".1%"),
                alt.Tooltip("unused_debt_capacity_cr:Q", title="Unused debt cap (₹cr)", format=",.0f"),
            ],
        )
        .properties(height=max(180, 22 * len(chart_df)))
    )


def sweet_spot_bubble(results: pd.DataFrame) -> alt.Chart | None:
    """FCF yield x unused debt capacity, bubble size = EBITDA. None if no data."""
    chart_df = results.assign(
        name=results["ticker"].str.replace(".NS", "", regex=False),
        verdict=results["passes_screen"].map(
            {True: "Passes all", False: "Falls short"}),
    ).dropna(subset=["fcf_yield", "unused_debt_capacity_cr"])
    if chart_df.empty:
        return None
    return (
        alt.Chart(chart_df)
        .mark_circle(opacity=0.75, stroke="#33373d", strokeWidth=0.5)
        .encode(
            x=alt.X("unused_debt_capacity_cr:Q", title="Unused debt capacity (₹cr)"),
            y=alt.Y("fcf_yield:Q", title="FCF yield", axis=alt.Axis(format="%")),
            size=alt.Size("ebitda_cr:Q", title="EBITDA (₹cr)",
                          scale=alt.Scale(range=[60, 1200])),
            color=alt.Color("verdict:N", scale=_VERDICT_SCALE, title=None),
            tooltip=[
                alt.Tooltip("name:N", title="Company"),
                alt.Tooltip("fcf_yield:Q", title="FCF yield", format=".1%"),
                alt.Tooltip("unused_debt_capacity_cr:Q", title="Unused debt cap (₹cr)", format=",.0f"),
                alt.Tooltip("ebitda_cr:Q", title="EBITDA (₹cr)", format=",.0f"),
                alt.Tooltip("net_debt_to_ebitda:Q", title="Net debt/EBITDA", format=".2f"),
            ],
        )
        .properties(height=380)
        .interactive()
    )


def sources_uses_waterfall(su: dict) -> alt.Chart:
    """EV-to-equity bridge: EV plus fees, less each debt tranche, leaves the
    sponsor equity check. Standalone copy of the app's waterfall (app.py:36).

    The bridge *amounts* are asserted against run_lbo's sources_uses dict by the
    parity test, so this copy cannot silently corrupt the math.
    """
    steps = [("Enterprise value", su["enterprise_value"], "total"),
             ("Transaction fees", su["txn_fees"], "inc"),
             ("Financing fees", su["financing_fees"], "inc")]
    steps += [(t["name"].capitalize() + " debt", -t["amount"], "dec")
              for t in su["tranches"]]
    steps.append(("Sponsor equity", su["sponsor_equity"], "total"))

    rows, running = [], 0.0
    for label, amount, kind in steps:
        if kind == "total":
            start, end, running = 0.0, amount, amount
        else:
            start, end = running, running + amount
            running = end
        rows.append({"label": label, "amount": amount, "kind": kind,
                     "lo": min(start, end), "hi": max(start, end)})
    wf = pd.DataFrame(rows)
    order = wf["label"].tolist()

    color = alt.Color(
        "kind:N",
        scale=alt.Scale(domain=["total", "inc", "dec"],
                        range=["#3b6ea5", _RED, _GREEN]),
        legend=alt.Legend(title=None, orient="top",
            labelExpr="datum.label == 'total' ? 'EV / equity' "
                      ": datum.label == 'inc' ? 'Fees (add)' : 'Debt (fund)'"))
    return (
        alt.Chart(wf)
        .mark_bar()
        .encode(
            x=alt.X("label:N", sort=order, title=None,
                    axis=alt.Axis(labelAngle=-30)),
            y=alt.Y("lo:Q", title="₹ cr"),
            y2="hi:Q",
            color=color,
            tooltip=[alt.Tooltip("label:N", title="Item"),
                     alt.Tooltip("amount:Q", title="₹ cr", format=",.0f")],
        )
        .properties(height=360)
    )
