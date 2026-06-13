"""Simplified paper-LBO: sources & uses, a yearly debt schedule with a 100%
cash sweep, exit at a flat multiple, and an entry-multiple x leverage
sensitivity grid.

Key simplifications (documented in the README):
- Levered FCF = EBITDA - cash interest - taxes - capex - change in WC.
- Capex is modelled as a % of EBITDA and doubles as the D&A proxy in the
  tax calculation (taxes = tax_rate x max(0, EBITDA - capex - interest)).
- Working-capital build is a % of incremental EBITDA.
- Interest accrues on beginning-of-year debt.
- 100% cash sweep; FCF left over after debt is fully repaid accumulates as
  cash and is returned to the sponsor at exit.
- No transaction fees, no management rollover, flat exit multiple = entry.
"""

import pandas as pd


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

    total_debt = sum(t["principal"] for t in sized)
    cap = 0.75 * ev
    if total_debt > cap and total_debt > 0:
        cap_scale = cap / total_debt
        for t in sized:
            t["principal"] *= cap_scale
        total_debt = cap
    return sized, total_debt


def run_lbo(entry_ebitda: float, assumptions: dict,
            entry_multiple: float | None = None,
            total_leverage: float | None = None) -> dict:
    """Run the paper LBO for one company with a multi-tranche waterfall.

    `assumptions` is the `lbo` config section. `entry_multiple` and
    `total_leverage` can be overridden for sensitivity runs; `total_leverage`
    scales all tranches proportionally. Returns sources & uses (itemized by
    tranche), the yearly schedule, and MOIC / IRR.
    """
    a = assumptions
    entry_multiple = entry_multiple if entry_multiple is not None else a["entry_multiple"]
    ev = entry_ebitda * entry_multiple

    sized, total_debt = _size_tranches(entry_ebitda, ev, a["tranches"], total_leverage)
    equity = ev - total_debt

    balances = [t["principal"] for t in sized]
    originals = [t["principal"] for t in sized]
    rates = [t["rate"] for t in sized]
    amort_pcts = [t["mandatory_amort_pct"] for t in sized]
    names = [t["name"] for t in sized]
    revolver = 0.0
    cash = 0.0
    ebitda = entry_ebitda

    rows = []
    for year in range(1, a["hold_years"] + 1):
        prev_ebitda = ebitda
        ebitda = prev_ebitda * (1 + a["ebitda_growth"])

        cash_interest = sum(b * r for b, r in zip(balances, rates)) + revolver * a["revolver_rate"]
        capex = a["capex_pct_of_ebitda"] * ebitda
        taxes = a["tax_rate"] * max(0.0, ebitda - capex - cash_interest)  # capex ~ D&A
        delta_wc = a["wc_pct_of_incremental_ebitda"] * (ebitda - prev_ebitda)
        fcf = ebitda - cash_interest - taxes - capex - delta_wc

        # 1) mandatory amortization (contractual, % of original principal)
        mandatory = []
        for i in range(len(balances)):
            amt = min(amort_pcts[i] * originals[i], balances[i])
            balances[i] -= amt
            mandatory.append(amt)

        # 2) sweep excess down the priority stack, or draw the revolver
        excess = fcf - sum(mandatory)
        sweep = [0.0] * len(balances)
        if excess > 0:
            pay = min(revolver, excess)            # revolver swept first
            revolver -= pay
            excess -= pay
            for i in range(len(balances)):          # then tranches by priority
                pay = min(balances[i], excess)
                balances[i] -= pay
                sweep[i] += pay
                excess -= pay
                if excess <= 1e-12:
                    break
            cash += max(excess, 0.0)                # leftover accumulates
        elif excess < 0:
            revolver += -excess                     # funding gap drawn on revolver

        row = {
            "year": year, "ebitda": ebitda, "interest": cash_interest,
            "taxes": taxes, "capex": capex, "delta_wc": delta_wc,
            "levered_fcf": fcf, "revolver": revolver, "cash": cash,
        }
        for i, nm in enumerate(names):
            row[f"{nm}_repaid"] = mandatory[i] + sweep[i]
            row[f"{nm}_ending"] = balances[i]
        row["ending_debt"] = sum(balances) + revolver
        rows.append(row)

    schedule = pd.DataFrame(rows)
    exit_ev = ebitda * entry_multiple  # flat exit multiple
    ending_debt = sum(balances) + revolver
    exit_equity = exit_ev - ending_debt + cash
    moic = exit_equity / equity if equity > 0 else float("nan")
    irr = moic ** (1 / a["hold_years"]) - 1 if moic > 0 else float("nan")

    return {
        "entry_multiple": entry_multiple,
        "sources_uses": {
            "enterprise_value": ev,
            "debt": total_debt,
            "tranches": [{"name": t["name"], "amount": t["principal"],
                          "pct_of_ev": t["principal"] / ev} for t in sized],
            "sponsor_equity": equity,
            "debt_pct_of_ev": total_debt / ev,
        },
        "schedule": schedule,
        "exit_ev": exit_ev,
        "exit_net_debt": ending_debt - cash,
        "exit_equity": exit_equity,
        "moic": moic,
        "irr": irr,
    }


def sensitivity_grid(entry_ebitda: float, assumptions: dict,
                     entry_multiples: list[float],
                     leverage_multiples: list[float]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """IRR and MOIC grids across entry multiple (rows) x total leverage (cols).

    Each column scales all tranches proportionally to the target total leverage.
    """
    irr = pd.DataFrame(index=entry_multiples, columns=leverage_multiples, dtype=float)
    moic = irr.copy()
    for em in entry_multiples:
        for lm in leverage_multiples:
            result = run_lbo(entry_ebitda, assumptions,
                             entry_multiple=em, total_leverage=lm)
            irr.loc[em, lm] = result["irr"]
            moic.loc[em, lm] = result["moic"]
    irr.index.name = "entry_multiple"
    irr.columns.name = "total_leverage"
    moic.index.name = "entry_multiple"
    moic.columns.name = "total_leverage"
    return irr, moic
