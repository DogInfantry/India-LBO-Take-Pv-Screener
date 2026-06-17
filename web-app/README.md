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

## Notes

- Degenerate net-cash names (e.g. JUSTDIAL — net cash > market cap, LBO not
  computable) are flagged by the engine and render dimmed as "n.m." here.
- Deployment (`vercel.json` repoint) and the weekly refresh are Phase 4; until
  then the existing `web/` static site remains the deployed one.
