import sys
sys.stdout.reconfigure(encoding="utf-8")  # rationale strings contain the rupee sign
sys.path.insert(0, "src")
import pandas as pd
from data_loader import load_config, load_fundamentals, load_universe
from screener import apply_screen, build_rationale, compute_metrics
from lbo_model import run_lbo, sensitivity_grid

cfg = load_config()
uni = load_universe()
fund = load_fundamentals()
print(f"universe: {len(uni)} names, fundamentals: {len(fund)} rows, "
      f"{fund['ticker'].nunique()} companies")

# offline market frame, with a fake mcap for INFY to exercise the mcap branch
market = pd.DataFrame({
    "ticker": ["INFY.NS", "TCS.NS"],
    "price": [1600.0, None],
    "market_cap_cr": [660000.0, None],
    "shares_outstanding": [4.15e9, None],
})
metrics = compute_metrics(fund, market, cfg)
results = apply_screen(metrics, cfg)
print(results[["ticker", "net_debt_to_ebitda", "interest_coverage",
               "fcf_positive_years", "ebitda_margin", "criteria_passed",
               "passes_screen"]].to_string(index=False))

for _, row in results.iterrows():
    print("\n" + build_rationale(row, cfg))

# LBO on a company with 5,000 cr revenue / 1,000 cr EBITDA (20% margin). Default
# tranches sum to 3.0x EBITDA, so sources & uses are EV 8000 / debt 3000 / equity 5000.
res = run_lbo(5000.0, 1000.0, cfg["lbo"])
su = res["sources_uses"]
assert abs(su["enterprise_value"] - 8000) < 1e-9
assert abs(su["debt"] - 3000) < 1e-9
assert abs(su["sponsor_equity"] - 5000) < 1e-9
# total debt = sum of itemized tranches
assert abs(sum(t["amount"] for t in su["tranches"]) - su["debt"]) < 1e-9
print(f"\nLBO @8x/3x on 5000cr rev / 1000cr EBITDA: MOIC {res['moic']:.2f}x, "
      f"IRR {res['irr']:.1%}, max balance error {res['max_balance_error']:.1e}")
print(res["schedule"].round(0).to_string(index=False))
print("\nBalance sheet (₹ cr):")
print(res["balance_sheet"].round(0).to_string(index=False))
# the balance sheet must tie out every year
assert res["max_balance_error"] < 1e-6
# the structure must net-deleverage over the hold (FCF may not be strictly
# monotonic year-on-year once real taxes/NWC are in the cash flow)
assert res["schedule"]["ending_debt"].iloc[-1] < su["debt"]
# IRR closed form consistency
assert abs((1 + res["irr"]) ** 5 - res["moic"]) < 1e-9

irr_g, moic_g = sensitivity_grid(5000.0, 1000.0, cfg["lbo"],
                                 cfg["sensitivity"]["entry_multiples"],
                                 cfg["sensitivity"]["leverage_multiples"])
print("\nIRR grid:\n", (irr_g * 100).round(1).to_string())
# center cell (entry 8x, total leverage 3.0x) must match the base run
assert abs(irr_g.loc[8.0, 3.0] - res["irr"]) < 1e-12
# RBI cap: 3.5x total leverage on a 4.0x EV = 87.5% > 75%, so the cap binds.
capped = run_lbo(5000.0, 1000.0, cfg["lbo"], entry_multiple=4.0, total_leverage=3.5)
assert abs(capped["sources_uses"]["debt"] - 0.75 * 4000) < 1e-9
print("\nAll assertions passed.")
