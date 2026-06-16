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

# offline market frame: in-band mcaps for two real names exercise the mcap
# branch; a None mcap exercises the missing-data branch. Other universe names
# get NaN mcap on merge and fail pass_mcap by design.
market = pd.DataFrame({
    "ticker": ["CYIENT.NS", "NATCOPHARM.NS", "INDIAMART.NS"],
    "price": [1700.0, 950.0, None],
    "market_cap_cr": [9000.0, 14000.0, None],
    "shares_outstanding": [1.1e8, 1.8e8, None],
})
metrics = compute_metrics(fund, market, cfg)
results = apply_screen(metrics, cfg)
print(results[["ticker", "net_debt_to_ebitda", "interest_coverage",
               "fcf_positive_years", "ebitda_margin", "criteria_passed",
               "passes_screen"]].to_string(index=False))

for _, row in results.iterrows():
    print("\n" + build_rationale(row, cfg))

# LBO on a company with 5,000 cr revenue / 1,000 cr EBITDA (20% margin). Default
# tranches sum to 3.0x EBITDA, so EV 8000 / debt 3000. Transaction and financing
# fees are now layered in: txn fees fold into goodwill and are funded by sponsor
# equity, financing fees are capitalized as a DFC asset and also equity-funded, so
# sponsor equity = EV + txn_fees + financing_fees - debt (5235 at defaults).
res = run_lbo(5000.0, 1000.0, cfg["lbo"])
su = res["sources_uses"]
assert abs(su["enterprise_value"] - 8000) < 1e-9
assert abs(su["debt"] - 3000) < 1e-9
# fees are positive and flow into the sources & uses
assert su["txn_fees"] > 0
assert su["financing_fees"] > 0
# fee-aware sources & uses identity: EV + fees (uses) = debt + equity (sources)
assert abs((su["enterprise_value"] + su["txn_fees"] + su["financing_fees"])
           - (su["debt"] + su["sponsor_equity"])) < 1e-6
# total debt = sum of itemized tranches
assert abs(sum(t["amount"] for t in su["tranches"]) - su["debt"]) < 1e-9
print(f"\nLBO @8x/3x on 5000cr rev / 1000cr EBITDA: MOIC {res['moic']:.2f}x, "
      f"IRR {res['irr']:.1%}, max balance error {res['max_balance_error']:.1e}")
print(f"  transaction fees (into goodwill, equity-funded): {su['txn_fees']:.1f} cr")
print(f"  financing fees (capitalized DFC, amortized):     {su['financing_fees']:.1f} cr")
print(res["schedule"].round(0).to_string(index=False))
print("\nBalance sheet (₹ cr):")
print(res["balance_sheet"].round(0).to_string(index=False))
opening_bs = res["balance_sheet"].iloc[0]
print(f"\nOpening WC/DFC sample (₹ cr): ar {opening_bs['ar']:.1f}, "
      f"inventory {opening_bs['inventory']:.1f}, ap {opening_bs['ap']:.1f}, "
      f"dfc {opening_bs['dfc']:.1f}")
# the balance sheet must tie out every year
assert res["max_balance_error"] < 1e-6
# the DFC asset must fully amortize to zero by the end of the hold
assert abs(res["balance_sheet"].iloc[-1]["dfc"]) < 1e-6
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
