"""Load the universe list, the fundamentals CSV, and live market data
(price / market cap / shares outstanding) from yfinance.

Fundamentals are produced by fetch_fundamentals.py, which pulls ~4-5 recent
fiscal years of financials from yfinance into data/fundamentals.csv. The two
promoter columns (holding / pledge) are not in yfinance and are filled by hand
from Screener.in. load_fundamentals prefers fundamentals.csv and falls back to
the bundled template (INFY/TCS examples) when it is absent.
"""

from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

FUNDAMENTALS_COLUMNS = [
    "ticker", "year", "revenue_cr", "ebitda_cr", "net_debt_cr",
    "interest_expense_cr", "fcf_cr", "promoter_holding_pct",
    "promoter_pledge_pct",
]


def load_config(path: Path | str = PROJECT_ROOT / "config" / "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_universe(path: Path | str = PROJECT_ROOT / "data" / "universe.csv") -> pd.DataFrame:
    """Universe of candidate tickers: ticker, company_name, sector."""
    df = pd.read_csv(path)
    df["ticker"] = df["ticker"].str.strip()
    return df


def load_fundamentals(path: Path | str | None = None) -> pd.DataFrame:
    """Long-format fundamentals: one row per company-year.

    Defaults to the real data file (data/fundamentals.csv, produced by
    fetch_fundamentals.py) when present, falling back to the bundled template
    (INFY/TCS examples) so a fresh clone still loads. Sorted by ticker then
    fiscal year so the screener's "latest year" logic can take the last row.
    """
    if path is None:
        real = PROJECT_ROOT / "data" / "fundamentals.csv"
        path = real if real.exists() else PROJECT_ROOT / "data" / "fundamentals_template.csv"
    df = pd.read_csv(path)
    missing = set(FUNDAMENTALS_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Fundamentals CSV is missing columns: {sorted(missing)}")
    df["ticker"] = df["ticker"].str.strip()
    # FY16, FY17, ... sort correctly as strings within a decade, but sort
    # numerically to be safe (handles FY09 vs FY16 style mixes).
    df["_fy"] = df["year"].str.extract(r"(\d+)").astype(int)
    df = df.sort_values(["ticker", "_fy"]).drop(columns="_fy").reset_index(drop=True)
    return df


def fetch_market_data(tickers: list[str]) -> pd.DataFrame:
    """Fetch live price, market cap and shares outstanding for NSE tickers.

    Returns one row per ticker with NaNs where yfinance has no data, so a
    flaky connection degrades the screen rather than crashing it.
    Market cap is converted from INR to crore (1 cr = 1e7).
    """
    import yfinance as yf  # imported lazily: the screener works offline without it

    rows = []
    for ticker in tickers:
        row = {"ticker": ticker, "price": None, "market_cap_cr": None,
               "shares_outstanding": None}
        try:
            info = yf.Ticker(ticker).fast_info
            price = info.get("lastPrice")
            mcap = info.get("marketCap")
            shares = info.get("shares")
            row["price"] = price
            row["market_cap_cr"] = mcap / 1e7 if mcap else None
            row["shares_outstanding"] = shares
        except Exception:
            pass  # leave NaNs; the screener flags missing market data
        rows.append(row)
    return pd.DataFrame(rows)
