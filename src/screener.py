"""Screening logic: compute per-company credit and ownership metrics from the
fundamentals CSV, apply the configured thresholds, and rank survivors.

The screen looks for UNUSED debt capacity, not existing leverage: companies
with low net debt, strong interest coverage and consistent FCF are the ones a
sponsor could lever up in a take-private under RBI's 2026 acquisition-finance
regime.
"""

import pandas as pd


def _margin_trend_ok(margins: pd.Series, trend_years: int, tolerance_pp: float) -> bool:
    """Stable-or-improving test: average EBITDA margin of the most recent two
    years must not sit more than `tolerance_pp` percentage points below the
    average of the earlier years in the trend window.
    """
    window = margins.dropna().tail(trend_years)
    if len(window) < 3:
        return False  # not enough history to judge a trend
    recent = window.tail(2).mean()
    earlier = window.head(len(window) - 2).mean()
    return (recent - earlier) * 100 >= -tolerance_pp


def compute_metrics(fundamentals: pd.DataFrame, market: pd.DataFrame,
                    cfg: dict) -> pd.DataFrame:
    """One row of screening metrics per ticker present in the fundamentals CSV.

    `fundamentals` is long-format (one row per company-year, sorted by year);
    `market` carries live market_cap_cr per ticker from yfinance.
    """
    scr = cfg["screening"]
    lbo = cfg["lbo"]
    rows = []
    for ticker, hist in fundamentals.groupby("ticker"):
        latest = hist.iloc[-1]
        ebitda = latest["ebitda_cr"]
        net_debt = latest["net_debt_cr"]
        margins = hist["ebitda_cr"] / hist["revenue_cr"]

        n_fcf = scr["min_consecutive_fcf_years"]
        recent_fcf = hist["fcf_cr"].tail(n_fcf)

        rows.append({
            "ticker": ticker,
            "latest_year": latest["year"],
            "revenue_cr": latest["revenue_cr"],
            "ebitda_cr": ebitda,
            "ebitda_margin": ebitda / latest["revenue_cr"] if latest["revenue_cr"] else None,
            "net_debt_cr": net_debt,
            "net_debt_to_ebitda": net_debt / ebitda if ebitda > 0 else None,
            "interest_coverage": (ebitda / latest["interest_expense_cr"]
                                  if latest["interest_expense_cr"] > 0 else float("inf")),
            "fcf_cr": latest["fcf_cr"],
            "fcf_positive_years": int((recent_fcf > 0).sum()),
            "fcf_years_available": len(recent_fcf),
            "margin_trend_ok": _margin_trend_ok(
                margins, scr["margin_trend_years"], scr["margin_tolerance_pp"]),
            "promoter_holding_pct": latest["promoter_holding_pct"],
            "promoter_pledge_pct": latest["promoter_pledge_pct"],
            # Headroom to the modelled LBO leverage level — the thesis metric.
            "unused_debt_capacity_cr": max(
                0.0, sum(t["turns"] for t in lbo["tranches"]) * ebitda - net_debt),
        })

    metrics = pd.DataFrame(rows)
    metrics = metrics.merge(market[["ticker", "market_cap_cr"]], on="ticker", how="left")
    metrics["fcf_yield"] = metrics["fcf_cr"] / metrics["market_cap_cr"]
    return metrics


def apply_screen(metrics: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Add one boolean pass/fail column per criterion plus an overall verdict,
    and rank passing names by FCF yield (cheapest cash flow first).
    """
    scr = cfg["screening"]
    df = metrics.copy()

    df["pass_leverage"] = df["net_debt_to_ebitda"] < scr["max_net_debt_to_ebitda"]
    df["pass_coverage"] = df["interest_coverage"] > scr["min_interest_coverage"]
    df["pass_fcf"] = (df["fcf_positive_years"] == df["fcf_years_available"]) & \
                     (df["fcf_years_available"] >= scr["min_consecutive_fcf_years"])
    df["pass_margin"] = (df["ebitda_margin"] > scr["min_ebitda_margin"]) & df["margin_trend_ok"]
    df["pass_promoter"] = df["promoter_holding_pct"].between(
        scr["min_promoter_holding_pct"], scr["max_promoter_holding_pct"])
    df["pass_pledge"] = df["promoter_pledge_pct"] < scr["max_promoter_pledge_pct"]
    df["pass_mcap"] = df["market_cap_cr"].between(
        scr["min_market_cap_cr"], scr["max_market_cap_cr"])

    pass_cols = [c for c in df.columns if c.startswith("pass_")]
    # NaN (e.g. market cap unavailable) counts as a fail, not a pass.
    df[pass_cols] = df[pass_cols].fillna(False).astype(bool)
    df["passes_screen"] = df[pass_cols].all(axis=1)
    df["criteria_passed"] = df[pass_cols].sum(axis=1)

    return df.sort_values(["passes_screen", "fcf_yield"],
                          ascending=[False, False]).reset_index(drop=True)


def build_rationale(row: pd.Series, cfg: dict) -> str:
    """Template-based screening rationale paragraph for a tear sheet."""
    scr = cfg["screening"]
    name = row["ticker"].replace(".NS", "")

    if row["passes_screen"]:
        coverage = ("n.m. (negligible interest)" if row["interest_coverage"] == float("inf")
                    else f"{row['interest_coverage']:.1f}x")
        fcf_yield = (f"{row['fcf_yield'] * 100:.1f}%" if pd.notna(row["fcf_yield"])
                     else "n.a.")
        return (
            f"{name} passes all screening criteria. Net debt/EBITDA of "
            f"{row['net_debt_to_ebitda']:.1f}x against a {scr['max_net_debt_to_ebitda']:.0f}x "
            f"ceiling implies roughly ₹{row['unused_debt_capacity_cr']:,.0f} cr of unused "
            f"debt capacity at the modelled leverage level. Interest coverage of {coverage} "
            f"and {row['fcf_positive_years']} consecutive years of positive FCF "
            f"(latest FCF yield {fcf_yield}) suggest the cash flows could service "
            f"acquisition debt. Promoter holding of {row['promoter_holding_pct']:.1f}% with "
            f"{row['promoter_pledge_pct']:.1f}% pledged is consistent with a promoter-led "
            f"take-private under the SEBI 75% non-public shareholding ceiling."
        )

    failures = []
    if not row["pass_leverage"]:
        failures.append(f"net debt/EBITDA of {row['net_debt_to_ebitda']:.1f}x exceeds "
                        f"the {scr['max_net_debt_to_ebitda']:.0f}x ceiling")
    if not row["pass_coverage"]:
        failures.append(f"interest coverage of {row['interest_coverage']:.1f}x is below "
                        f"{scr['min_interest_coverage']:.0f}x")
    if not row["pass_fcf"]:
        failures.append(f"FCF was positive in only {row['fcf_positive_years']} of the "
                        f"last {row['fcf_years_available']} years")
    if not row["pass_margin"]:
        failures.append(f"EBITDA margin of {row['ebitda_margin'] * 100:.1f}% fails the "
                        f"{scr['min_ebitda_margin'] * 100:.0f}% floor or is deteriorating")
    if not row["pass_promoter"]:
        failures.append(f"promoter holding of {row['promoter_holding_pct']:.1f}% is outside "
                        f"the {scr['min_promoter_holding_pct']:.0f}-"
                        f"{scr['max_promoter_holding_pct']:.0f}% band")
    if not row["pass_pledge"]:
        failures.append(f"promoter pledge of {row['promoter_pledge_pct']:.1f}% exceeds "
                        f"the {scr['max_promoter_pledge_pct']:.0f}% limit")
    if not row["pass_mcap"]:
        mcap = (f"₹{row['market_cap_cr']:,.0f} cr" if pd.notna(row["market_cap_cr"])
                else "unavailable")
        failures.append(f"market cap ({mcap}) is outside the "
                        f"₹{scr['min_market_cap_cr']:,}-{scr['max_market_cap_cr']:,} cr band")

    return f"{name} fails the screen: " + "; ".join(failures) + "."
