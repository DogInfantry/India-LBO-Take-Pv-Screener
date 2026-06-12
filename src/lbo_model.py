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


def run_lbo(entry_ebitda: float, assumptions: dict,
            entry_multiple: float | None = None,
            leverage_multiple: float | None = None) -> dict:
    """Run the paper LBO for one company.

    `assumptions` is the `lbo` section of the config; entry/leverage multiples
    can be overridden for sensitivity runs. Returns sources & uses, the yearly
    schedule (DataFrame), and MOIC / IRR.
    """
    a = assumptions
    entry_multiple = entry_multiple if entry_multiple is not None else a["entry_multiple"]
    leverage_multiple = (leverage_multiple if leverage_multiple is not None
                         else a["leverage_multiple"])

    ev = entry_ebitda * entry_multiple
    entry_debt = min(entry_ebitda * leverage_multiple, 0.75 * ev)  # RBI 75%-of-value cap
    equity = ev - entry_debt
    debt = entry_debt

    rows = []
    ebitda = entry_ebitda
    cash = 0.0
    for year in range(1, a["hold_years"] + 1):
        prev_ebitda = ebitda
        ebitda = prev_ebitda * (1 + a["ebitda_growth"])
        opening_debt = debt

        interest = opening_debt * a["interest_rate"]
        capex = a["capex_pct_of_ebitda"] * ebitda
        taxes = a["tax_rate"] * max(0.0, ebitda - capex - interest)  # capex ~ D&A
        delta_wc = a["wc_pct_of_incremental_ebitda"] * (ebitda - prev_ebitda)
        fcf = ebitda - interest - taxes - capex - delta_wc

        repayment = min(opening_debt, max(fcf, 0.0))
        debt = opening_debt - repayment
        cash += max(fcf, 0.0) - repayment
        if fcf < 0:  # funding gap drawn on debt (revolver-style)
            debt += -fcf

        rows.append({
            "year": year, "ebitda": ebitda, "interest": interest,
            "taxes": taxes, "capex": capex, "delta_wc": delta_wc,
            "levered_fcf": fcf, "debt_repaid": repayment,
            "ending_debt": debt, "ending_cash": cash,
        })

    schedule = pd.DataFrame(rows)
    exit_ev = ebitda * entry_multiple  # flat exit multiple
    exit_equity = exit_ev - debt + cash
    moic = exit_equity / equity if equity > 0 else float("nan")
    # Single cash-out at exit (100% sweep, no interim dividends), so IRR has
    # a closed form — no numerical root-finding needed.
    irr = moic ** (1 / a["hold_years"]) - 1 if moic > 0 else float("nan")

    return {
        "entry_multiple": entry_multiple,
        "leverage_multiple": leverage_multiple,
        "sources_uses": {
            "enterprise_value": ev,
            "debt": entry_debt,
            "sponsor_equity": equity,
            "debt_pct_of_ev": entry_debt / ev,
        },
        "schedule": schedule,
        "exit_ev": exit_ev,
        "exit_net_debt": debt - cash,
        "exit_equity": exit_equity,
        "moic": moic,
        "irr": irr,
    }


def sensitivity_grid(entry_ebitda: float, assumptions: dict,
                     entry_multiples: list[float],
                     leverage_multiples: list[float]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """IRR and MOIC grids across entry multiple (rows) x leverage (columns)."""
    irr = pd.DataFrame(index=entry_multiples, columns=leverage_multiples, dtype=float)
    moic = irr.copy()
    for em in entry_multiples:
        for lm in leverage_multiples:
            result = run_lbo(entry_ebitda, assumptions,
                             entry_multiple=em, leverage_multiple=lm)
            irr.loc[em, lm] = result["irr"]
            moic.loc[em, lm] = result["moic"]
    irr.index.name = "entry_multiple"
    irr.columns.name = "leverage_multiple"
    moic.index.name = "entry_multiple"
    moic.columns.name = "leverage_multiple"
    return irr, moic
