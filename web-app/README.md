# LBO Screener — Dashboard (web-app)

The Next.js (static-export) front end for the India LBO take-private screener.
It renders the `results.json` contract produced by the Python engine — no Python
runs here, and there is no runtime data fetch. The dashboard reads the contract
at **build time**.

## Prerequisite: generate the data contract

`results.json` is a build artifact (git-ignored). Produce it from the repo root
**before** building or running the dashboard:

```bash
# from the repo root (one directory up)
python tools/export_data.py --no-fetch     # uses the committed market snapshot
# or, for a live refresh:
python tools/export_data.py                # live yfinance fetch
```

This writes `web-app/public/data/results.json`.

## Develop / build

```bash
cd web-app
npm install
npm run dev      # http://localhost:3000
npm run test     # Vitest unit tests (loader, KPIs, every chart option-builder)
npm run build    # static export -> web-app/out/
```

## What's here

- `app/page.tsx` — the dense-grid dashboard (KPI band + IRR leaderboard, iso-IRR
  frontier, feasibility, Sobol drivers), Midnight-terminal theme.
- `app/t/[ticker]/page.tsx` — stub tear sheet (headline KPIs). The full tear
  sheet is Phase 3.
- `lib/` — typed contract (`types.ts`), build-time loader (`data.ts`), theme
  (`theme.ts`), and pure ECharts option-builders under `lib/charts/`.
- `components/` — the `EChart` wrapper (drives ECharts core directly; React-19
  safe) and the panel components.

## Deployment

Vercel builds this app from the repo-root `vercel.json` (`installCommand` /
`buildCommand` / `outputDirectory` all target `web-app/`): it runs
`npm install && npm run build` in `web-app/` and serves the static export from
`web-app/out`. The committed `web-app/public/data/results.json` feeds the build —
**no Python runs on Vercel.**

The data refreshes itself: `.github/workflows/weekly.yml` runs every Monday (and
on-demand via the Actions tab's "Run workflow"), does a live `yfinance` export,
validates `universe.passed > 0`, and commits + pushes the new `results.json`.
Vercel redeploys on that push. A flaky/empty fetch fails the validate step and
publishes nothing, leaving the last good contract in place.

> Fallback: if the `buildCommand` form ever misbehaves on Vercel, set the
> project's **Root Directory** to `web-app` in the Vercel dashboard and let
> Vercel build Next.js natively (it handles `output: 'export'` → serves `out/`).

## Notes

- Degenerate net-cash names (e.g. JUSTDIAL — net cash > market cap, LBO not
  computable) are flagged by the engine and render dimmed as "n.m." here.
