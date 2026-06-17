# Phase 4 — Deploy Cutover + Weekly Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stage the production cutover to `web-app/` + a Monday auto-refresh on `feat/phase4-deploy` (commit `results.json`, repoint `vercel.json`, add `weekly.yml`, docs), verify via a Vercel **preview** build, and leave the branch **unmerged** for the user to flip live.

**Architecture:** Vercel's Node build serves the Next static export from `web-app/out` (build command in `vercel.json`); the committed `results.json` feeds it (no Python on Vercel). A scheduled GitHub Action re-runs the Python export weekly, validates passers>0, and commits+pushes the refreshed contract, which triggers a Vercel redeploy.

**Tech Stack:** Vercel (project `india-lbo-take-pv-screener`, team `team_4pgfqRkIU2W9etJoOiEwg250`, framework null, Node 24), GitHub Actions, Python export from Phase 1.

**This is config/CI — not TDD.** "Tests" are verification commands: a local dry-run of the CI logic, a successful `web-app` build, and the **Vercel preview build logs** read via MCP.

---

## Reference (verified)

- `tools/export_data.py` — default = live yfinance fetch; `--no-fetch` uses `data/market_snapshot.csv`; writes `web-app/public/data/results.json`. Imports `export_site.gather` (needs Jinja2) and `analytics` (needs SALib for Sobol).
- `requirements-dev.txt` — `-r requirements.txt` + pytest + Jinja2 + SALib (everything the export needs in CI).
- Current `vercel.json` — rewrites all routes to `/web/...` (the old Jinja site).
- `.gitignore:19` — `web-app/public/data/results.json` (to be removed).
- Contract is valid: `universe.passed == 6`.
- Vercel: project `prj_MZSkV8xzfrUZuEBBvB15j1nkHcLh`, framework `null`, Root Directory = repo root, deploys from `main`, prod domain `india-lbo-take-pv-screener.vercel.app`.

## File structure

```
.gitignore                                  # remove the results.json ignore line
web-app/public/data/results.json            # now COMMITTED (build artifact -> tracked data)
data/market_snapshot.csv                    # ensure committed (live export refreshes it)
vercel.json                                  # repoint: build web-app -> serve web-app/out
.github/workflows/weekly.yml                # NEW: Monday cron refresh + manual dispatch
README.md / web-app/README.md               # deployment + refresh notes
```

---

### Task 1: Commit the data contract

**Files:** Modify `.gitignore`; add `web-app/public/data/results.json`, ensure `data/market_snapshot.csv` tracked.

- [ ] **Step 1: Un-ignore the contract** — in `.gitignore`, delete these two lines:
```
# generated data contract (rebuilt by tools/export_data.py / weekly CI)
web-app/public/data/results.json
```

- [ ] **Step 2: Regenerate a fresh contract** (so the committed one is current)
Run (repo root): `python tools/export_data.py --no-fetch`
Expected: writes `web-app/public/data/results.json` (6 passers).

- [ ] **Step 3: Verify both data files are now stageable**
Run: `git status --short web-app/public/data/results.json data/market_snapshot.csv`
Expected: `results.json` shows as untracked/new; if `market_snapshot.csv` is already tracked it won't appear unless changed — that's fine. If `data/market_snapshot.csv` is NOT tracked (run `git ls-files data/market_snapshot.csv`), include it in the add below.

- [ ] **Step 4: Commit**
```bash
git add .gitignore web-app/public/data/results.json data/market_snapshot.csv
git commit -m "build: commit results.json contract for Vercel (Node build, no Python on Vercel)"
```

---

### Task 2: Repoint `vercel.json`

**Files:** Modify `vercel.json`.

- [ ] **Step 1: Replace the file contents** with the static build of the Next app:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "installCommand": "cd web-app && npm install",
  "buildCommand": "cd web-app && npm run build",
  "outputDirectory": "web-app/out",
  "framework": null
}
```

- [ ] **Step 2: Sanity-check locally that the referenced build works**
Run: `cd web-app && npm run build` (repo root: `npm --prefix web-app run build`)
Expected: static export succeeds, `web-app/out/index.html` and `web-app/out/t/*.html` exist. (This is the exact command Vercel will run after `cd web-app`.)

- [ ] **Step 3: Validate the JSON**
Run: `python -c "import json; json.load(open('vercel.json')); print('vercel.json OK')"`
Expected: `vercel.json OK`.

- [ ] **Step 4: Commit**
```bash
git add vercel.json
git commit -m "build: repoint vercel.json to build/serve web-app (static export)"
```

---

### Task 3: Weekly refresh workflow

**Files:** Create `.github/workflows/weekly.yml`.

- [ ] **Step 1: Create the workflow**

```yaml
name: weekly-refresh

on:
  schedule:
    - cron: "0 6 * * 1"   # Mondays 06:00 UTC
  workflow_dispatch: {}    # manual "run now"

permissions:
  contents: write          # push the refreshed contract to main

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements-dev.txt

      - name: Export contract (live yfinance fetch)
        run: python tools/export_data.py

      - name: Validate (passers > 0) — fail-safe, no publish on a bad fetch
        run: |
          python -c "import json,sys; d=json.load(open('web-app/public/data/results.json')); print('passed', d['universe']['passed']); sys.exit(0 if d['universe']['passed']>0 else 1)"

      - name: Commit & push if changed
        run: |
          git config user.name "DogInfantry"
          git config user.email "ankleshrawat5@gmail.com"
          git add web-app/public/data/results.json data/market_snapshot.csv
          if git diff --cached --quiet; then
            echo "No data change this week."
          else
            git commit -m "chore: weekly results.json refresh ($(date -u +%Y-%m-%d))"
            git push
          fi
```

> Notes for the implementer:
> - The workflow triggers on `schedule`/`workflow_dispatch` only (NOT `push`), so
>   the CI's own commit cannot loop. Vercel redeploys on the push via its own Git
>   integration.
> - `permissions: contents: write` + the default `GITHUB_TOKEN` (persisted by
>   `actions/checkout`) is enough to push to `main` in the same repo; no PAT.
> - If the live fetch fails or yields 0 passers, the validate step fails the job
>   and nothing is committed — the site stays on the last good contract, and the
>   failed run is visible in the Actions tab.

- [ ] **Step 2: Lint the YAML**
Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/weekly.yml')); print('weekly.yml OK')"`
Expected: `weekly.yml OK`. (PyYAML is already a dependency.)

- [ ] **Step 3: Dry-run the CI logic locally** (prove export → validate works without a live fetch)
Run:
```bash
python tools/export_data.py --no-fetch
python -c "import json,sys; d=json.load(open('web-app/public/data/results.json')); print('passed', d['universe']['passed']); sys.exit(0 if d['universe']['passed']>0 else 1)"
```
Expected: prints `passed 6`, exit 0 — the same gate the workflow uses.

- [ ] **Step 4: Commit**
```bash
git add .github/workflows/weekly.yml
git commit -m "ci: weekly Monday results.json refresh (live fetch, validate-before-commit)"
```

---

### Task 4: Documentation

**Files:** Modify `web-app/README.md` and root `README.md`.

- [ ] **Step 1: web-app/README.md** — add a "Deployment" section:
  - Vercel builds `web-app/` via the root `vercel.json` (`installCommand`/
    `buildCommand`/`outputDirectory`); the committed `results.json` feeds the
    build; no Python runs on Vercel.
  - The weekly GitHub Action (`.github/workflows/weekly.yml`) refreshes the
    contract on Mondays (or via the manual "Run workflow" button) and pushes,
    which redeploys.
  - Fallback: if the build-command form ever misbehaves, set the Vercel project's
    **Root Directory** to `web-app` and let Vercel build Next natively.

- [ ] **Step 2: root README.md** — add a short "Deployment" note: the deployed
  site is the Next app in `web-app/` (after this branch is merged); the legacy
  `web/` Jinja export remains in history but is no longer served.

- [ ] **Step 3: Commit**
```bash
git add web-app/README.md README.md
git commit -m "docs: deployment + weekly-refresh notes"
```

---

### Task 5: Push branch + verify the Vercel preview build (controller, via MCP)

This is the verification gate. **Production is untouched** — pushing a feature
branch yields a Vercel *preview* deploy that uses the branch's `vercel.json`;
`main` keeps the old one until the user merges.

- [ ] **Step 1: Push the branch**
```bash
git push -u origin feat/phase4-deploy
```

- [ ] **Step 2: Find the preview deployment** (controller, MCP)
Use `list_deployments` (projectId `prj_MZSkV8xzfrUZuEBBvB15j1nkHcLh`, teamId
`team_4pgfqRkIU2W9etJoOiEwg250`) to find the deployment for the
`feat/phase4-deploy` branch (target = preview). Note its id/url.

- [ ] **Step 3: Read the build logs** (controller, MCP)
`get_deployment_build_logs` for that deployment. Confirm: install ran in
`web-app`, `next build` produced the static export, and the deployment reached
`READY`. If it failed, read the error, fix (`vercel.json` / build), re-push, re-check.

- [ ] **Step 4: Confirm the preview renders** — fetch the preview URL (e.g. via
`web_fetch_vercel_url` or report the URL for the user to open) and confirm the
dashboard HTML is served (not the old `web/` site).

- [ ] **Step 5: Report to the user** — preview URL + build status, and the
one remaining action: **merge `feat/phase4-deploy` → `main` to flip production.**
Do NOT merge automatically (prepare-only).

---

## Done criteria for Phase 4

- `results.json` (+ `market_snapshot.csv`) committed; `.gitignore` no longer ignores the contract.
- `vercel.json` builds `web-app` and serves `web-app/out`; `npm --prefix web-app run build` passes locally.
- `.github/workflows/weekly.yml` present, YAML valid, the export→validate gate proven locally.
- Branch pushed; **Vercel preview deployment READY**, build logs confirm the Next static export, preview URL serves the new app.
- Branch is **NOT merged** to `main`. The user merges to go live.

## After merge (user action, documented — not part of this plan's execution)

- Merging `feat/phase4-deploy` → `main` makes the next production deployment serve `web-app/` — the cutover.
- The weekly workflow begins running on its Monday schedule (and can be run on demand from the Actions tab).
```
