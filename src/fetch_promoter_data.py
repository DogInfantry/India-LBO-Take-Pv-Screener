"""Populate the promoter columns in data/fundamentals.csv.

yfinance does not carry India-specific shareholding-filing data, but its
`insidersPercentHeld` field is a usable proxy for PROMOTER HOLDING on NSE
names (promoters are the reported insiders). This script fills
`promoter_holding_pct` for every ticker from that field.

PROMOTER PLEDGE has no free programmatic source (yfinance lacks it, NSE blocks
scraping), so it is sourced separately — by a targeted web lookup from
Screener.in for the names that clear the other screen criteria — and written
into PLEDGE_OVERRIDES below. Anything not in that map is left blank (NaN), which
the screen treats as a pledge fail until the figure is supplied.

Holding/pledge are written only to each ticker's LATEST fiscal-year row, since
the screener reads `hist.iloc[-1]` per company. The script is idempotent:
re-running refreshes holding from yfinance and re-applies the overrides.

Run:  python src/fetch_promoter_data.py            # all universe tickers
      python src/fetch_promoter_data.py CYIENT.NS  # a subset, for spot checks
"""

import sys

import pandas as pd

from data_loader import PROJECT_ROOT, load_fundamentals, load_universe

FUNDAMENTALS_PATH = PROJECT_ROOT / "data" / "fundamentals.csv"

# Promoter pledge % (of promoter holding), sourced by targeted web lookup from
# Screener.in for the names that clear the other screen criteria. Keyed by
# ticker; latest available quarterly shareholding filing. Names absent here are
# left blank and fail the pledge filter until filled.
# Sourced Mar-2026 quarter shareholding (Trendlyne / company filings), verified
# for the names that clear the other six screen criteria. All currently nil.
PLEDGE_OVERRIDES: dict[str, float] = {
    "NATCOPHARM.NS": 0.0,
    "ZENSARTECH.NS": 0.0,
    "TANLA.NS": 0.0,
    "JUSTDIAL.NS": 0.0,
    "INDIAMART.NS": 0.0,
    "ALKYLAMINE.NS": 0.0,
}


def fetch_promoter_holding(ticker: str) -> float | None:
    """Promoter holding % from yfinance insidersPercentHeld (0-1 -> %)."""
    import yfinance as yf

    try:
        pct = yf.Ticker(ticker).info.get("heldPercentInsiders")
    except Exception:
        return None
    return round(pct * 100, 1) if pct is not None else None


def _latest_row_index(df: pd.DataFrame, ticker: str) -> int | None:
    """Index of the most recent fiscal-year row for a ticker (the row the
    screener reads), or None if the ticker is absent from the file."""
    rows = df.index[df["ticker"] == ticker]
    if len(rows) == 0:
        return None
    fy = df.loc[rows, "year"].str.extract(r"(\d+)")[0].astype(int)
    return fy.idxmax()


def main(argv: list[str]) -> None:
    if not FUNDAMENTALS_PATH.exists():
        sys.exit(f"{FUNDAMENTALS_PATH} not found — run fetch_fundamentals.py first.")

    df = load_fundamentals(FUNDAMENTALS_PATH)
    tickers = [t.strip() for t in argv] if argv else load_universe()["ticker"].tolist()

    print(f"Filling promoter holding for {len(tickers)} ticker(s) from yfinance...")
    filled_holding = filled_pledge = 0
    for ticker in tickers:
        idx = _latest_row_index(df, ticker)
        if idx is None:
            print(f"  {ticker:16s} not in fundamentals.csv — skipped")
            continue

        holding = fetch_promoter_holding(ticker)
        if holding is not None:
            df.at[idx, "promoter_holding_pct"] = holding
            filled_holding += 1

        pledge = PLEDGE_OVERRIDES.get(ticker)
        if pledge is not None:
            df.at[idx, "promoter_pledge_pct"] = pledge
            filled_pledge += 1

        h = f"{holding:.1f}%" if holding is not None else "—"
        p = f"{pledge:.1f}%" if pledge is not None else "—"
        print(f"  {ticker:16s} holding {h:>7s}  pledge {p:>6s}")

    df.to_csv(FUNDAMENTALS_PATH, index=False)
    print(f"\nWrote holding for {filled_holding} and pledge for {filled_pledge} "
          f"ticker(s) to {FUNDAMENTALS_PATH}")
    if filled_pledge < filled_holding:
        print("Pledge still blank for some names — add them to PLEDGE_OVERRIDES "
              "from Screener.in to enable the pledge filter.")


if __name__ == "__main__":
    main(sys.argv[1:])
