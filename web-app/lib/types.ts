export interface IsoFrontierPoint { exit_multiple: number; premium_pct: number; }
export interface Passer {
  ticker: string; name: string;
  irr: number | null; moic: number | null;
  degenerate: boolean; feasibility: number;
  max_bid_premium_pct: number | null;
}
export interface CompanyBlock {
  ticker: string; name: string;
  returns: { irr: number | null; moic: number | null; degenerate: boolean;
             irr_bridge: unknown | null; value_bridge: unknown | null };
  sensitivity: { iso_frontier: { target_irr: number; points: IsoFrontierPoint[] } } | null;
  sobol: { first_order: Record<string, number>;
           total_order: Record<string, number> } | null;
  feasibility: { score: number; components: Record<string, number>;
                 weights: Record<string, number> };
  // statements/debt_schedule/montecarlo/downside/solvers/delisting: Phase 3
  [k: string]: unknown;
}
export interface Results {
  as_of: string;
  config: { hurdle_irr: number; hold_years: number; control_premium_pct: number };
  universe: { screened: number; passed: number };
  passers: Passer[];
  companies: Record<string, CompanyBlock>;
}
