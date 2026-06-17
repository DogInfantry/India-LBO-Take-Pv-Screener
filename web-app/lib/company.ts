import { loadResults } from "./data";
import type { CompanyBlock } from "./types";

export function loadCompany(ticker: string): CompanyBlock | null {
  return loadResults().companies[ticker] ?? null;
}
