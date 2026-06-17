# Phase 4 — Deploy Cutover + Weekly Refresh — Design

**Date:** 2026-06-18
**Branch:** `feat/phase4-deploy`
**Status:** Design — pending implementation. **Prepare-only: do NOT merge to
`main`.** Merging is the user's "go live" action.

## Problem

Phases 1–3 built the Python engine, the dashboard, and the tear sheet — all
working locally. But the deployed site (`india-lbo-take-pv-screener.vercel.app`)
still serves the old Jinja `web/` export via `vercel.json`, and there is no
automated refresh. Phase 4 stages the production cutover to `web-app/` and adds a
weekly auto-refresh — **on a branch, without going live**. The user merges to
flip the production URL when ready.

This is Phase 4 (final) of the parent spec
(`2026-06-17-lbo-quant-showcase-design.md`).

## Decisions

- **Prepare-only.** All changes land on `feat/phase4-deploy`. The branch is NOT
  merged; the user reviews and merges to switch the live site.
- **Commit `results.json`.** Vercel's build runs Node/Next and cannot run the
  Python engine, so the data contract must be in the repo. Remove
  `web-app/public/data/results.json` from `.gitignore` and commit it (plus
  `data/market_snapshot.csv`, which the live export refreshes). The weekly CI
  keeps it current via commit+push.
- **`vercel.json` repoint via build command** (no Vercel dashboard change
  required, given the project's Root Directory is the repo root today).
- **Weekly refresh = live yfinance fetch with a fail-safe.** A real weekly data
  refresh; the job only commits when the export succeeds with >0 passers,
  otherwise it leaves the last good `results.json` in place.

## Components

### 1. `.gitignore` + committed contract

Remove the `web-app/public/data/results.json` ignore line. Commit the current
`results.json` and `data/market_snapshot.csv` so a clean checkout (and Vercel)
can build the site without Python.

### 2. `vercel.json` (repoint)

Replace the `web/` rewrites with a static build of the Next app:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "installCommand": "cd web-app && npm install",
  "buildCommand": "cd web-app && npm run build",
  "outputDirectory": "web-app/out",
  "framework": null
}
```

The build reads the committed `results.json`; `output: 'export'` produces
`web-app/out`, which Vercel serves as static files. No Python runs on Vercel.
The README documents the cleaner alternative (set Vercel **Root Directory =
`web-app`** and let Vercel build Next natively) in case the build-command form
needs adjusting on the user's Vercel project.

### 3. `.github/workflows/weekly.yml`

```yaml
name: weekly-refresh
on:
  schedule: [{ cron: "0 6 * * 1" }]   # Mondays 06:00 UTC
  workflow_dispatch: {}                # manual "run now"
permissions:
  contents: write
```

Job steps:
1. checkout (with token that can push to `main`).
2. setup Python 3.x.
3. `pip install -r requirements-dev.txt` (includes SALib, needed for the Sobol
   block in the export).
4. `python tools/export_data.py` (live yfinance fetch) → writes
   `web-app/public/data/results.json` and refreshes `data/market_snapshot.csv`.
5. **Validate**: the export must produce `results.json` with `universe.passed > 0`
   (a small Python/jq check). If validation fails, the job fails and does NOT
   commit — the last good contract stays.
6. On success: configure git as `DogInfantry <ankleshrawat5@gmail.com>`, commit
   `web-app/public/data/results.json` + `data/market_snapshot.csv` if changed,
   and push to `main`. Vercel's Git integration redeploys on the push.

The validate-before-commit step is the fail-safe: a flaky/empty yfinance fetch
never publishes a broken screen.

### 4. Docs

- `web-app/README.md`: note the Vercel deploy (build `web-app/`) and the weekly
  refresh; the manual `workflow_dispatch` trigger.
- Root `README.md`: brief "deployment" section — the new app is the deployed
  site after the user merges this branch; `web/` remains in history.

## Non-goals

- **No merge to `main`** (prepare-only). No live change until the user merges.
- No removal/rewrite of the old `web/` site or `tools/export_site.py` (kept as
  history).
- No new Python analytics; no frontend feature changes. Phase 4 is deploy/CI
  config only.
- No Vercel dashboard automation (the user owns their Vercel project; the
  build-command vercel.json avoids needing dashboard changes, with the
  Root-Directory alternative documented).

## Testing / verification

- **Workflow validity:** the YAML parses; steps reference real files
  (`requirements-dev.txt`, `tools/export_data.py`). Optionally run the export +
  validate logic locally (`python tools/export_data.py --no-fetch` then the
  passers>0 check) to prove the CI logic, without doing a live fetch.
- **Build:** `cd web-app && npm run build` succeeds against the committed
  `results.json` (already verified in Phase 2/3).
- **Vercel:** the user confirms via a **preview deploy from the branch** before
  merging — the agent cannot drive the user's Vercel account. The spec/plan call
  this out as a user-side verification step.

## Risks / open questions

- **Vercel build form vs Root Directory:** the `buildCommand`/`outputDirectory`
  approach assumes the project's Root Directory is the repo root. If Vercel's
  Next.js detection interferes, the documented fallback is to set Root Directory
  to `web-app`. Surfaced to the user; confirmed via preview deploy.
- **yfinance in CI:** can be rate-limited or blocked from GitHub runners. The
  validate-before-commit fail-safe handles this (no publish on a bad fetch); a
  persistently failing fetch simply leaves the site on the last good data and
  shows up as a failed (visible) workflow run.
- **Push from CI to `main`:** requires the default `GITHUB_TOKEN` with
  `contents: write` (set in `permissions`); no PAT needed for pushing to the
  same repo. Commits are attributed to the configured git identity.
- **Commit churn:** a weekly commit of `results.json` is expected and harmless.
```
