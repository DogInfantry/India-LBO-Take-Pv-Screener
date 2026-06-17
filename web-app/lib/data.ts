import fs from "node:fs";
import path from "node:path";
import type { Results, Passer } from "./types";

const CONTRACT = path.join(process.cwd(), "public", "data", "results.json");

export function loadResults(): Results {
  if (!fs.existsSync(CONTRACT)) {
    throw new Error(
      `Missing ${CONTRACT}. Run: python tools/export_data.py --no-fetch (from repo root) first.`
    );
  }
  const raw = JSON.parse(fs.readFileSync(CONTRACT, "utf-8")) as Results;
  if (!raw.passers || !raw.companies) throw new Error("results.json is malformed");
  return raw;
}

export function topReturns(passers: Passer[]) {
  const live = passers.filter((p) => !p.degenerate && p.irr != null && p.moic != null);
  const byIrr = [...live].sort((a, b) => (b.irr! - a.irr!));
  const byMoic = [...live].sort((a, b) => (b.moic! - a.moic!));
  return {
    topIrr: byIrr[0]?.irr ?? null, topIrrTicker: byIrr[0]?.ticker ?? null,
    topMoic: byMoic[0]?.moic ?? null,
    topFeasibility: Math.max(...passers.map((p) => p.feasibility)),
  };
}
