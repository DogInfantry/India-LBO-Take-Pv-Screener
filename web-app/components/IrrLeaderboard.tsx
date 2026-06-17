"use client";
import Link from "next/link";
import type { Passer } from "@/lib/types";
import { buildLeaderboardOption } from "@/lib/charts/leaderboard";
import { EChart } from "./EChart";

export function IrrLeaderboard({ passers, hurdle }: { passers: Passer[]; hurdle: number }) {
  const degen = passers.filter((p) => p.degenerate);
  return (
    <div>
      <EChart option={buildLeaderboardOption(passers, hurdle)}
              height={Math.max(160, 34 * passers.filter((p) => !p.degenerate).length)} />
      <ul className="mt-2 space-y-1 text-xs">
        {passers.map((p) => (
          <li key={p.ticker}>
            <Link href={`/t/${p.ticker}`}
              className={p.degenerate ? "text-faint italic" : "text-muted hover:text-ink"}>
              {p.name}{p.degenerate ? " — n.m. (net cash > mkt cap)" : ""}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
