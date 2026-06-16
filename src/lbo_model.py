"""Revenue-driven paper-LBO with a full three-statement build on a multi-tranche
cash-sweep waterfall: sources & uses, an Income Statement, Balance Sheet, and
Cash Flow Statement that articulate (the BS balances every year), exit at a flat
multiple, and an entry-multiple x total leverage sensitivity grid.

Key mechanics (documented in the README; statement helpers in statements.py):
- Revenue grows at revenue_growth; EBITDA = revenue x flat entry margin.
- Debt is an ordered list of tranches (senior first) plus a revolver; sizes
  are turns x LTM EBITDA, total capped at 75% of EV (RBI), scaled proportionally.
- Sources & uses carry transaction fees (% of EV, equity-funded into goodwill)
  and financing fees (% of debt), both funded by additional sponsor equity.
- Opening BS is cash-free/debt-free with goodwill as the plug
  (goodwill = EV + txn_fees - opening PP&E - opening NWC); goodwill held flat.
  Financing fees are capitalized as a deferred-financing-cost (DFC) asset and
  amortized straight-line over the hold, rolling down to zero at exit.
- Working capital is days-based (DSO on revenue; DIO/DPO on COGS); NWC =
  AR + Inventory - AP.
- Each year: IS (EBIT = EBITDA - D&A on opening PP&E - DFC amort; taxes on EBT,
  floored at zero) -> debt waterfall (mandatory amort, then sweep
  revolver->senior->mezz, shortfalls draw the revolver) -> CFS (CFO = NI + D&A +
  DFC amort - dNWC; FCF for debt = CFO - capex) -> BS (cash is the CFS plug;
  PP&E rolls capex - D&A; DFC rolls down by amort; equity accumulates retained
  earnings). Interest accrues on opening balances, so the loop is a single
  forward pass and IRR stays closed-form.
- The balance check (max_balance_error ~ 0) is a bug detector, not load-bearing
  accounting (the BS balances by construction).
- Deferred: management rollover, PIK, purchase-price write-ups, deferred taxes,
  NOLs. Flat exit multiple = entry.
"""

import pandas as pd
from statements import opening_balance_sheet, income_statement_row, working_capital


def _size_tranches(entry_ebitda: float, ev: float, tranches: list[dict],
                   total_leverage: float | None) -> tuple[list[dict], float]:
    """Size each tranche in rupees and apply the RBI 75%-of-EV cap.

    If `total_leverage` is given, scale every tranche's turns so they sum to it
    (proportional scaling, used by the sensitivity grid). If the summed debt
    exceeds 0.75 x EV, scale all tranches down by the same factor.
    """
    base_turns = sum(t["turns"] for t in tranches)
    scale = (total_leverage / base_turns) if (total_leverage is not None and base_turns) else 1.0
    sized = [{
        "name": t["name"],
        "rate": t["rate"],
        "mandatory_amort_pct": t.get("mandatory_amort_pct", 0.0),
        "principal": t["turns"] * scale * entry_ebitda,
    } for t in tranches]

    cap = 0.75 * ev
    if cap <= 0:
        # Near-zero or negative EV (e.g. a net-cash company trading below its
        # cash): nothing to lever. Honest answer is no acquisition debt.
        for t in sized:
            t["principal"] = 0.0
        return sized, 0.0

    total_debt = sum(t["principal"] for t in sized)
    if total_debt > cap and total_debt > 0:
        cap_scale = cap / total_debt
        for t in sized:
            t["principal"] *= cap_scale
        total_debt = cap
    return sized, total_debt


def run_lbo(entry_revenue: float, entry_ebitda: float, assumptions: dict,
            entry_multiple: float | None = None,
            total_leverage: float | None = None,
            entry_ev: float | None = None) -> dict:
    """Run the paper LBO with a full three-statement build.

    Entry price is set one of two ways:
    - `entry_ev` given (market take-private): EV is the actual cost of the deal
      — equity purchase price (market cap x (1 + control premium)) plus assumed
      net debt — and the entry multiple FALLS OUT as entry_ev / EBITDA.
    - otherwise (fixed multiple): EV = EBITDA x entry_multiple, the legacy path.
    The exit reuses the (implied or fixed) entry multiple, so returns come from
    deleveraging and EBITDA growth, never multiple expansion.

    Revenue drives the model; EBITDA = revenue x flat entry margin
    (entry_ebitda / entry_revenue). Each year produces an income statement, the
    debt waterfall (mandatory amort -> sweep -> revolver), a cash flow statement,
    and a balance sheet that balances. Interest accrues on opening balances, so
    the loop is a single forward pass and IRR stays closed-form.
    """
    a = assumptions
    margin = entry_ebitda / entry_revenue if entry_revenue else 0.0
    if entry_ev is not None:
        ev = entry_ev
        entry_multiple = ev / entry_ebitda if entry_ebitda else 0.0
    else:
        entry_multiple = entry_multiple if entry_multiple is not None else a["entry_multiple"]
        ev = entry_ebitda * entry_multiple

    sized, total_debt = _size_tranches(entry_ebitda, ev, a["tranches"], total_leverage)
    txn_fees = a["txn_fee_pct_of_ev"] * ev
    financing_fees = a["financing_fee_pct_of_debt"] * total_debt
    dfc_amort = financing_fees / a["hold_years"] if a["hold_years"] else 0.0
    equity = ev + txn_fees + financing_fees - total_debt  # sponsor equity (entry); MOIC denominator

    balances = [t["principal"] for t in sized]
    originals = [t["principal"] for t in sized]
    rates = [t["rate"] for t in sized]
    amort_pcts = [t["mandatory_amort_pct"] for t in sized]
    names = [t["name"] for t in sized]
    revolver = 0.0

    obs = opening_balance_sheet(entry_revenue, ev, total_debt, equity, a,
                                txn_fees=txn_fees, financing_fees=financing_fees)
    cash, nwc, ppe, goodwill = obs["cash"], obs["nwc"], obs["ppe"], obs["goodwill"]
    dfc = obs["dfc"]
    book_equity = equity            # accumulates retained earnings
    revenue = entry_revenue

    is_rows, cf_rows, sched_rows = [], [], []
    wc0 = working_capital(entry_revenue, a)
    bs_rows = [{
        "year": 0, "cash": cash, "ar": wc0["ar"], "inventory": wc0["inventory"],
        "ap": wc0["ap"], "nwc": nwc, "ppe": ppe, "goodwill": goodwill, "dfc": dfc,
        "assets": cash + nwc + ppe + goodwill + dfc,
        "debt": sum(balances) + revolver, "equity": book_equity,
        "balance_error": (cash + nwc + ppe + goodwill + dfc)
                         - (sum(balances) + revolver + book_equity),
    }]

    for year in range(1, a["hold_years"] + 1):
        opening_ppe = ppe
        revenue = revenue * (1 + a["revenue_growth"])
        wc = working_capital(revenue, a)
        cash_interest = sum(b * r for b, r in zip(balances, rates)) + revolver * a["revolver_rate"]
        isr = income_statement_row(revenue, margin, opening_ppe, cash_interest, a,
                                   dfc_amort=dfc_amort)

        capex = a["capex_pct_of_revenue"] * revenue
        delta_nwc = wc["nwc"] - nwc
        cfo = isr["net_income"] + isr["da"] + isr["dfc_amort"] - delta_nwc
        fcf_for_debt = cfo - capex

        # --- debt waterfall (same mechanism as Phase 1) ---
        mandatory = []
        for i in range(len(balances)):
            amt = min(amort_pcts[i] * originals[i], balances[i])
            balances[i] -= amt
            mandatory.append(amt)
        excess = fcf_for_debt - sum(mandatory)
        sweep = [0.0] * len(balances)
        revolver_draw = 0.0
        revolver_repaid = 0.0
        if excess > 0:
            revolver_repaid = min(revolver, excess)
            revolver -= revolver_repaid
            excess -= revolver_repaid
            for i in range(len(balances)):
                pay = min(balances[i], excess)
                balances[i] -= pay
                sweep[i] += pay
                excess -= pay
                if excess <= 1e-12:
                    break
        elif excess < 0:
            revolver_draw = -excess
            revolver += revolver_draw

        principal_repaid = sum(mandatory) + sum(sweep) + revolver_repaid
        cff = -principal_repaid + revolver_draw
        cash = cash + cfo - capex + cff

        # roll forward balances
        nwc = wc["nwc"]
        ppe = opening_ppe + capex - isr["da"]
        dfc = max(0.0, dfc - dfc_amort)
        book_equity = book_equity + isr["net_income"]

        ending_debt = sum(balances) + revolver
        assets = cash + nwc + ppe + goodwill + dfc

        is_rows.append({"year": year, **isr})
        cf_rows.append({
            "year": year, "net_income": isr["net_income"], "da": isr["da"],
            "delta_nwc": delta_nwc, "cfo": cfo, "capex": capex,
            "fcf_for_debt": fcf_for_debt, "principal_repaid": principal_repaid,
            "revolver_draw": revolver_draw, "cff": cff, "ending_cash": cash,
        })
        bs_rows.append({
            "year": year, "cash": cash, "ar": wc["ar"], "inventory": wc["inventory"],
            "ap": wc["ap"], "nwc": nwc, "ppe": ppe, "goodwill": goodwill, "dfc": dfc,
            "assets": assets, "debt": ending_debt, "equity": book_equity,
            "balance_error": assets - (ending_debt + book_equity),
        })
        srow = {"year": year, "ebitda": isr["ebitda"], "interest": cash_interest,
                "taxes": isr["taxes"], "capex": capex, "delta_nwc": delta_nwc,
                "fcf_for_debt": fcf_for_debt, "revolver": revolver, "cash": cash}
        for i, nm in enumerate(names):
            srow[f"{nm}_repaid"] = mandatory[i] + sweep[i]
            srow[f"{nm}_ending"] = balances[i]
        srow["ending_debt"] = ending_debt
        sched_rows.append(srow)

    schedule = pd.DataFrame(sched_rows)
    income_statement = pd.DataFrame(is_rows)
    cash_flow = pd.DataFrame(cf_rows)
    balance_sheet = pd.DataFrame(bs_rows)
    max_balance_error = balance_sheet["balance_error"].abs().max()

    final_ebitda = is_rows[-1]["ebitda"]
    exit_ev = final_ebitda * entry_multiple  # flat exit multiple
    ending_debt = sum(balances) + revolver
    exit_net_debt = ending_debt - cash
    exit_equity = exit_ev - exit_net_debt
    moic = exit_equity / equity if equity > 0 else float("nan")
    irr = moic ** (1 / a["hold_years"]) - 1 if moic > 0 else float("nan")

    return {
        "entry_multiple": entry_multiple,
        "margin": margin,
        "sources_uses": {
            "enterprise_value": ev,
            "debt": total_debt,
            "tranches": [{"name": t["name"], "amount": t["principal"],
                          "pct_of_ev": t["principal"] / ev} for t in sized],
            "txn_fees": txn_fees,
            "financing_fees": financing_fees,
            "sponsor_equity": equity,
            "debt_pct_of_ev": total_debt / ev,
        },
        "schedule": schedule,
        "income_statement": income_statement,
        "cash_flow": cash_flow,
        "balance_sheet": balance_sheet,
        "max_balance_error": max_balance_error,
        "exit_ev": exit_ev,
        "exit_net_debt": exit_net_debt,
        "exit_equity": exit_equity,
        "moic": moic,
        "irr": irr,
    }


def sensitivity_grid(entry_revenue: float, entry_ebitda: float, assumptions: dict,
                     entry_multiples: list[float],
                     leverage_multiples: list[float]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """IRR and MOIC grids across entry multiple (rows) x total leverage (cols).

    Each column scales all tranches proportionally to the target total leverage.
    """
    irr = pd.DataFrame(index=entry_multiples, columns=leverage_multiples, dtype=float)
    moic = irr.copy()
    for em in entry_multiples:
        for lm in leverage_multiples:
            result = run_lbo(entry_revenue, entry_ebitda, assumptions,
                             entry_multiple=em, total_leverage=lm)
            irr.loc[em, lm] = result["irr"]
            moic.loc[em, lm] = result["moic"]
    irr.index.name = "entry_multiple"
    irr.columns.name = "total_leverage"
    moic.index.name = "entry_multiple"
    moic.columns.name = "total_leverage"
    return irr, moic


def sensitivity_grid_premium(
        entry_revenue: float, entry_ebitda: float, assumptions: dict,
        market_cap: float, net_debt: float,
        premiums_pct: list[float],
        leverage_multiples: list[float]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """IRR and MOIC grids across control premium (rows) x total leverage (cols)
    for a market take-private. Each row prices the deal at
    EV = market_cap x (1 + premium) + net_debt, the actual acquisition cost.
    """
    irr = pd.DataFrame(index=premiums_pct, columns=leverage_multiples, dtype=float)
    moic = irr.copy()
    for prem in premiums_pct:
        entry_ev = market_cap * (1 + prem / 100.0) + net_debt
        for lm in leverage_multiples:
            result = run_lbo(entry_revenue, entry_ebitda, assumptions,
                             entry_ev=entry_ev, total_leverage=lm)
            irr.loc[prem, lm] = result["irr"]
            moic.loc[prem, lm] = result["moic"]
    irr.index.name = "premium_pct"
    irr.columns.name = "total_leverage"
    moic.index.name = "premium_pct"
    moic.columns.name = "total_leverage"
    return irr, moic
