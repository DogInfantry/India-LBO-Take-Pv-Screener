"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";
import type { Passer } from "@/lib/types";
import { buildLeaderboardOption } from "@/lib/charts/leaderboard";
import { EChart } from "./EChart";

export function IrrLeaderboard({ passers, hurdle }: { passers: Passer[]; hurdle: number }) {
  const router = useRouter();
  const live = passers.filter((p) => !p.degenerate && p.irr != null).sort((a, b) => a.irr! - b.irr!);

  const onEvents = useMemo(() => ({
    click: (params: any) => {
      const passer = live[params.dataIndex];
      if (passer) router.push(`/t/${passer.ticker}`);
    },
  }), [live, router]);

  return (
    <div>
      <EChart option={buildLeaderboardOption(passers, hurdle)}
              height={Math.max(160, 34 * live.length)}
              onEvents={onEvents} />
      <ul className="mt-2 space-y-1 text-xs">
        {passers.map((p) => (
          <li key={p.ticker}>
            {p.degenerate ? (
              <span className="text-faint italic">
                {p.name} — n.m. (net cash &gt; mkt cap)
              </span>
            ) : (
              <Link href={`/t/${p.ticker}`}
                className="group inline-flex items-center gap-1 text-muted underline underline-offset-2 decoration-[0.5px] decoration-muted hover:text-ink hover:decoration-ink transition-colors">
                {p.name}
                <span className="opacity-0 group-hover:opacity-100 transition-opacity text-[10px]">→</span>
              </Link>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
