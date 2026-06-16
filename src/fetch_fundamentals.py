"""Populate data/fundamentals.csv with REAL historical financials for the
universe, pulled from yfinance.

yfinance carries ~5 recent fiscal years of income-statement, balance-sheet and
cash-flow data for NSE names. That is enough for the screen's 5-year margin
trend and 3-year FCF tests. Two columns it CANNOT provide are deliberately left
blank for a manual Screener.in fill:

    promoter_holding_pct, promoter_pledge_pct

These are India-specific shareholding-filing data, absent from yfinance. Until
they are populated the screen's promoter/pledge filters fail by design (NaN is
treated as a fail), so no name clears the *full* screen — every other criterion
still computes and shows in the tear sheet.

Conventions (match the hand-entered INFY/TCS rows in fundamentals_template.csv):
- All ₹ figures in crore: value / 1e7.
- net_debt_cr = total debt - cash (incl. short-term investments where reported),
  so a NET-CASH company is NEGATIVE (e.g. INFY ~ -29,500). yfinance's own
  "Net Debt" field is dropped for net-cash names, so we compute it ourselves.
- Fiscal-year label = calendar year of the (March-end) reporting date:
  a period ending 2025-03-31 -> "FY25".

Run:  python src/fetch_fundamentals.py            # all universe tickers
      python src/fetch_fundamentals.py CYIENT.NS  # a subset, for spot checks
Output is written to data/fundamentals.csv (overwritten each run).
"""

import sys
from pathlib import Path

import pandas as pd

from data_loader import FUNDAMENTALS_COLUMNS, PROJECT_ROOT, load_universe

CR = 1e7  # 1 crore in rupees
OUTPUT_PATH = PROJECT_ROOT / "data" / "fundamentals.csv"


def _row_value(df: pd.DataFrame, labels: list[str], col) -> float | None:
    """First present, non-null value among `labels` for statement column `col`.

    yfinance row labels drift between tickers/versions, so we try a short list
    of equivalents and return None (not a guess) if none are available. The
    statements don't always cover the same period columns, so a `col` absent
    from this statement also yields None rather than raising.
    """
    if col not in df.columns:
        return None
    for label in labels:
        if label in df.index:
            val = df.loc[label, col]
            if pd.notna(val):
                return float(val)
    return None


def _to_cr(val: float | None) -> float | None:
    return val / CR if val is not None else None


def fetch_ticker(ticker: str) -> list[dict]:
    """One fundamentals row per available fiscal year for a single ticker.

    Returns [] if yfinance has no statement data (delisted/illiquid/blocked),
    so a few bad tickers degrade coverage rather than crashing the run.
    """
    import yfinance as yf

    t = yf.Ticker(ticker)
    try:
        fin, bs, cf = t.financials, t.balance_sheet, t.cashflow
    except Exception:
        return []
    if fin is None or fin.empty:
        return []

    rows = []
    for col in fin.columns:  # columns are period-end Timestamps, newest first
        fy = f"FY{int(col.year) % 100:02d}"

        revenue = _to_cr(_row_value(fin, ["Total Revenue", "Operating Revenue"], col))
        ebitda = _to_cr(_row_value(fin, ["EBITDA", "Normalized EBITDA"], col))
        interest = _to_cr(_row_value(
            fin, ["Interest Expense", "Interest Expense Non Operating"], col))

        total_debt = _row_value(bs, ["Total Debt"], col) if bs is not None else None
        cash = _row_value(bs, ["Cash Cash Equivalents And Short Term Investments",
                               "Cash And Cash Equivalents"], col) if bs is not None else None
        net_debt = _to_cr((total_debt or 0.0) - (cash or 0.0)) \
            if (total_debt is not None or cash is not None) else None

        fcf = _to_cr(_row_value(cf, ["Free Cash Flow"], col)) if cf is not None else None

        # Skip empty shells: a year with no revenue and no EBITDA carries nothing.
        if revenue is None and ebitda is None:
            continue

        rows.append({
            "ticker": ticker, "year": fy,
            "revenue_cr": round(revenue, 1) if revenue is not None else None,
            "ebitda_cr": round(ebitda, 1) if ebitda is not None else None,
            "net_debt_cr": round(net_debt, 1) if net_debt is not None else None,
            "interest_expense_cr": round(interest, 1) if interest is not None else None,
            "fcf_cr": round(fcf, 1) if fcf is not None else None,
            "promoter_holding_pct": None,  # manual Screener.in fill
            "promoter_pledge_pct": None,   # manual Screener.in fill
        })
    return rows


def build_fundamentals(tickers: list[str]) -> pd.DataFrame:
    all_rows = []
    for ticker in tickers:
        rows = fetch_ticker(ticker)
        status = f"{len(rows)} yrs" if rows else "NO DATA"
        print(f"  {ticker:16s} {status}")
        all_rows.extend(rows)

    df = pd.DataFrame(all_rows, columns=FUNDAMENTALS_COLUMNS)
    df["_fy"] = df["year"].str.extract(r"(\d+)").astype(int)
    df = df.sort_values(["ticker", "_fy"]).drop(columns="_fy").reset_index(drop=True)
    return df


def main(argv: list[str]) -> None:
    if argv:
        tickers = [t.strip() for t in argv]
    else:
        tickers = load_universe()["ticker"].tolist()

    print(f"Fetching fundamentals for {len(tickers)} ticker(s) from yfinance...")
    df = build_fundamentals(tickers)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    covered = df["ticker"].nunique()
    print(f"\nWrote {len(df)} rows for {covered} ticker(s) to {OUTPUT_PATH}")
    print("Promoter holding/pledge left blank - fill from Screener.in to enable "
          "the promoter & pledge screen filters.")


if __name__ == "__main__":
    main(sys.argv[1:])
