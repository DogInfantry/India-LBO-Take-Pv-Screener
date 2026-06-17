export interface IsoFrontierPoint { exit_multiple: number; premium_pct: number; }
export interface Passer {
  ticker: string; name: string;
  irr: number | null; moic: number | null;
  degenerate: boolean; feasibility: number;
  max_bid_premium_pct: number | null;
}

export interface IncomeRow { year:number; revenue:number; ebitda:number; da:number;
  dfc_amort:number; ebit:number; interest:number; ebt:number; taxes:number; net_income:number; }
export interface CashFlowRow { year:number; net_income:number; da:number; delta_nwc:number;
  cfo:number; capex:number; fcf_for_debt:number; principal_repaid:number;
  revolver_draw:number; cff:number; ending_cash:number; }
export interface BalanceRow { year:number; cash:number; ar:number; inventory:number; ap:number;
  nwc:number; ppe:number; goodwill:number; dfc:number; assets:number; debt:number;
  equity:number; balance_error:number; }
export interface DebtScheduleRow { year:number; ebitda:number; interest:number; revolver:number;
  cash:number; senior_repaid:number; senior_ending:number; mezzanine_repaid:number;
  mezzanine_ending:number; ending_debt:number; [k:string]:number; }
export interface Tranche { name:string; amount:number; pct_of_ev:number; }
export interface SourcesUses { enterprise_value:number; debt:number; tranches:Tranche[];
  txn_fees:number; financing_fees:number; sponsor_equity:number; debt_pct_of_ev:number; }
export interface IrrBridge { deleveraging:number; ebitda_growth:number;
  multiple_rerating:number; total_irr:number; }
export interface ValueBridge { entry_equity:number; ebitda_growth:number; multiple_change:number;
  debt_paydown:number; fees_and_other:number; exit_equity:number; }
export interface MonteCarlo { irr:(number|null)[]; moic:(number|null)[]; p_beat_hurdle:number; }
export interface Downside { p_loss:number|null; var5_moic:number|null; cvar5_moic:number|null; }
export interface Solvers {
  max_bid:{ converged:boolean; reason?:string; max_premium_pct:number|null; max_ev:number|null };
  debt_capacity:{ converged:boolean; max_leverage:number|null; min_coverage_at_max:number|null };
  optimal_exit:{ by_year:{year:number; irr:number|null; moic:number|null}[]; best_year:number|null };
}
export interface Delisting { indicative:boolean; acceptance_threshold_pct:number;
  promoter_holding_pct:number; float_to_tender_pct:number; indicative_premium_pct:number;
  indicative_discovered_ev_cr:number; assumptions:string; }
export interface SensitivityGrid { premiums_pct:number[]; exit_multiples:number[]; irr:(number|null)[][]; }

export interface CompanyBlock {
  ticker:string; name:string;
  statements: { income:IncomeRow[]; cash_flow:CashFlowRow[]; balance_sheet:BalanceRow[] } | null;
  debt_schedule: DebtScheduleRow[] | null;
  sources_uses: SourcesUses;
  returns: { irr:number|null; moic:number|null; degenerate:boolean;
             irr_bridge:IrrBridge|null; value_bridge:ValueBridge|null };
  montecarlo: MonteCarlo | null;
  downside: Downside | null;
  sensitivity: { iso_frontier:{target_irr:number; points:IsoFrontierPoint[]}; grid:SensitivityGrid } | null;
  solvers: Solvers | null;
  sobol: { first_order:Record<string,number>; total_order:Record<string,number> } | null;
  feasibility: { score:number; components:Record<string,number>; weights:Record<string,number> };
  delisting: Delisting;
}

export interface Results {
  as_of: string;
  config: { hurdle_irr: number; hold_years: number; control_premium_pct: number };
  universe: { screened: number; passed: number };
  passers: Passer[];
  companies: Record<string, CompanyBlock>;
}
