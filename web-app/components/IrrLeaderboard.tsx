"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";
import type { Passer } from "@/lib/types";
import { buildLeaderboardOption } from "@/lib/charts/leaderboard";
import { pct, mult } from "@/lib/format";
import { EChart } from "./EChart";

export function IrrLeaderboard({ passers, hurdle }: { passers: Passer[]; hurdle: number }) {
  const router = useRouter();
  const live = passers.filter((p) => !p.degenerate && p.irr != null).sort((a, b) => b.irr! - a.irr!);
  const degen = passers.filter((p) => p.degenerate);

  const onEvents = useMemo(() => ({
    click: (params: any) => {
      const sorted = [...live].reverse(); // chart is asc (bottom = highest)
      const passer = sorted[params.dataIndex];
      if (passer) router.push(`/t/${passer.ticker}`);
    },
  }), [live, router]);

  return (
    <div>
      <EChart option={buildLeaderboardOption(passers, hurdle)}
              height={Math.max(160, 34 * live.length)}
              onEvents={onEvents} />

      <div className="mt-3 flex flex-col gap-1.5">
        {live.map((p) => (
          <Link key={p.ticker} href={`/t/${p.ticker}`}
            className="group flex items-center justify-between rounded-md border border-edge bg-panel px-3 py-2.5 transition-all hover:border-emerald/40 hover:bg-[#0f1a24]">
            <div className="flex flex-col gap-0.5">
              <span className="font-mono text-[11px] font-semibold tracking-wider text-ink group-hover:text-emerald transition-colors">
                {p.name}
              </span>
              <span className="font-mono text-[9px] tracking-widest text-faint uppercase">
                {p.ticker} · tearsheet →
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex flex-col items-end gap-0.5">
                <span className="font-mono text-[11px] font-semibold text-emerald">{pct(p.irr)}</span>
                <span className="font-mono text-[9px] text-faint">IRR</span>
              </div>
              <div className="h-5 w-px bg-edge" />
              <div className="flex flex-col items-end gap-0.5">
                <span className="font-mono text-[11px] font-semibold text-violet">{mult(p.moic)}</span>
                <span className="font-mono text-[9px] text-faint">MOIC</span>
              </div>
              <div className="h-5 w-px bg-edge" />
              <div className="flex flex-col items-end gap-0.5">
                <span className="font-mono text-[11px] font-semibold text-amber">{p.feasibility}</span>
                <span className="font-mono text-[9px] text-faint">FEAS</span>
              </div>
              <svg className="ml-1 h-3.5 w-3.5 text-faint transition-all group-hover:translate-x-0.5 group-hover:text-emerald"
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            </div>
          </Link>
        ))}

        {degen.map((p) => (
          <div key={p.ticker}
            className="flex items-center justify-between rounded-md border border-edge/40 px-3 py-2 opacity-40">
            <div className="flex flex-col gap-0.5">
              <span className="font-mono text-[11px] italic text-muted">{p.name}</span>
              <span className="font-mono text-[9px] text-faint">net cash &gt; mkt cap · excluded</span>
            </div>
            <span className="font-mono text-[9px] text-faint italic">n.m.</span>
          </div>
        ))}
      </div>
    </div>
  );
}
