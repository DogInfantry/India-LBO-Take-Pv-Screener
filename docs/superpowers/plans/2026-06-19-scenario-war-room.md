# Scenario War Room Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Bull / Base / Bear scenario comparison, pre-computed in Python at build time, surfaced as a compact cross-company table on the dashboard and a full P&L bridge panel on each tearsheet.

**Architecture:** `scenario_block()` in `analytics.py` calls `run_lbo()` three times per company (applying config-driven lever deltas), writes output into `results.json`, consumed by two new React components — `WarRoomTable` on `/` and `ScenarioWarRoom` on `/t/[ticker]`. No live backend, no new build tooling.

**Tech Stack:** Python 3 · pandas · pytest — for analytics. TypeScript · React · Tailwind CSS · Vitest + Testing Library — for the frontend.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `config/config.yaml` | Modify | Add `scenarios:` section with bull/bear deltas |
| `src/analytics.py` | Modify | Add `scenario_block()`, update `build_company_block()`, `build_results()`, `COMPANY_KEYS`, degenerate stub |
| `tests/test_analytics.py` | Modify | Add three new Python tests for `scenario_block` |
| `web-app/lib/types.ts` | Modify | Add 5 new interfaces; extend `CompanyBlock` and `Passer` |
| `web-app/components/tearsheet/ScenarioWarRoom.tsx` | Create | Full P&L bridge table: assumptions → financials → returns |
| `web-app/components/WarRoomTable.tsx` | Create | Compact cross-company IRR table for dashboard |
| `web-app/app/t/[ticker]/page.tsx` | Modify | Wire `ScenarioWarRoom` after Returns Attribution section |
| `web-app/app/page.tsx` | Modify | Wire `WarRoomTable` after IrrLeaderboard panel |

---

## Task 1: Add scenario config

**Files:**
- Modify: `config/config.yaml`

- [ ] **Step 1: Append scenarios section to config.yaml**

Open `config/config.yaml`. After the last line of the `sensitivity:` block, append:

```yaml
scenarios:
  bull:
    revenue_growth_delta:  0.08   # +8pp above base → ~16% growth
    margin_delta:          0.05   # +5pp above company entry margin
    exit_multiple_delta:   2.0    # +2x above entry multiple
  bear:
    revenue_growth_delta: -0.05   # -5pp below base → ~3% growth
    margin_delta:         -0.05   # -5pp below company entry margin
    exit_multiple_delta:  -2.0    # -2x below entry multiple
```

- [ ] **Step 2: Verify YAML parses cleanly**

```bash
python -c "import yaml; yaml.safe_load(open('config/config.yaml')); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add config/config.yaml
git commit -m "config: add bull/bear scenario lever deltas"
```

---

## Task 2: Python — `scenario_block()` function

**Files:**
- Modify: `src/analytics.py` (add after `delisting_model`, before `COMPANY_KEYS`)
- Modify: `tests/test_analytics.py`

- [ ] **Step 1: Write the three failing tests first**

In `tests/test_analytics.py`, add a `scenarios_cfg()` helper and three tests after the existing tests:

```python
def scenarios_cfg():
    """Extend base_cfg with a scenarios block."""
    cfg = base_cfg()
    cfg["scenarios"] = {
        "bull": {"revenue_growth_delta": 0.08, "margin_delta": 0.05, "exit_multiple_delta": 2.0},
        "bear": {"revenue_growth_delta": -0.05, "margin_delta": -0.05, "exit_multiple_delta": -2.0},
    }
    return cfg


def test_scenario_block_has_three_keys():
    block = analytics.scenario_block(
        analytics.company_inputs(sample_row(), scenarios_cfg()),
        scenarios_cfg(),
    )
    assert set(block.keys()) == {"bull", "base", "bear"}


def test_scenario_block_base_matches_run_lbo():
    """Base scenario (zero deltas) must reproduce the direct run_lbo call exactly."""
    from lbo_model import run_lbo
    cfg = scenarios_cfg()
    inp = analytics.company_inputs(sample_row(), cfg)
    block = analytics.scenario_block(inp, cfg)
    base = block["base"]
    assert base is not None
    res = run_lbo(inp["entry_revenue"], inp["entry_ebitda"], inp["assumptions"],
                  entry_ev=inp["entry_ev"], total_leverage=inp["total_leverage"])
    assert base["returns"]["irr"] == pytest.approx(res["irr"], rel=1e-6)
    assert base["returns"]["moic"] == pytest.approx(res["moic"], rel=1e-6)
    assert base["financials"]["revenue"] == pytest.approx(
        res["income_statement"].iloc[-1]["revenue"], rel=1e-6)


def test_scenario_block_bull_gt_base_gt_bear():
    """For a healthy company, bull IRR > base IRR > bear IRR."""
    cfg = scenarios_cfg()
    inp = analytics.company_inputs(sample_row(), cfg)
    block = analytics.scenario_block(inp, cfg)
    bull_irr = block["bull"]["returns"]["irr"]
    base_irr = block["base"]["returns"]["irr"]
    bear_irr = block["bear"]["returns"]["irr"]
    assert bull_irr is not None and base_irr is not None
    assert bull_irr > base_irr
    if bear_irr is not None:   # bear may be degenerate for some inputs
        assert base_irr > bear_irr


def test_scenario_block_zero_ebitda_clamp_returns_none():
    """A margin_delta so negative that sc_ebitda clamps to 0 must return None, not crash."""
    cfg = scenarios_cfg()
    cfg["scenarios"]["bear"]["margin_delta"] = -99.0   # guaranteed to zero out ebitda
    inp = analytics.company_inputs(sample_row(), cfg)
    block = analytics.scenario_block(inp, cfg)
    assert block["bear"] is None          # clamped → skipped, not an exception
    assert block["base"] is not None      # base unaffected
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src && python -m pytest ../tests/test_analytics.py::test_scenario_block_has_three_keys -v
```

Expected: `FAILED` with `AttributeError: module 'analytics' has no attribute 'scenario_block'`

- [ ] **Step 3: Implement `scenario_block()` in `src/analytics.py`**

Add this function after `delisting_model()` (around line 306) and before `COMPANY_KEYS`:

```python
def scenario_block(inp: dict, cfg: dict) -> dict:
    """Run Bull / Base / Bear by applying lever deltas to base inputs.

    entry_revenue is ALWAYS the as-of-today value from inp — it never varies
    across scenarios. Only sc_ebitda, sc_growth, and sc_exit_mult change.
    """
    sc_cfg = cfg.get("scenarios", {})
    a = inp["assumptions"]
    base_margin = inp["entry_ebitda"] / inp["entry_revenue"] if inp["entry_revenue"] else 0.0
    base_growth = a["revenue_growth"]
    base_exit_mult = _entry_multiple(inp)

    def _run_scenario(deltas: dict):
        sc_growth = base_growth + deltas.get("revenue_growth_delta", 0.0)
        sc_margin = base_margin + deltas.get("margin_delta", 0.0)
        sc_ebitda = inp["entry_revenue"] * sc_margin
        sc_ebitda = max(0.0, sc_ebitda)                    # clamp first
        if sc_ebitda == 0.0:                               # then check
            return None
        sc_exit_mult = base_exit_mult + deltas.get("exit_multiple_delta", 0.0)
        res = run_lbo(inp["entry_revenue"], sc_ebitda,
                      {**a, "revenue_growth": float(sc_growth)},
                      entry_ev=inp["entry_ev"],
                      total_leverage=inp["total_leverage"],
                      exit_multiple=float(sc_exit_mult))
        irr = res["irr"]; moic = res["moic"]
        return {
            "assumptions": {
                "revenue_growth": sc_growth,
                "ebitda_margin":  sc_ebitda / inp["entry_revenue"],  # absolute, not delta
                "exit_multiple":  sc_exit_mult,
            },
            "financials": {
                "revenue":      float(res["income_statement"].iloc[-1]["revenue"]),
                "ebitda":       float(res["income_statement"].iloc[-1]["ebitda"]),
                "fcf_for_debt": float(res["cash_flow"].iloc[-1]["fcf_for_debt"]),
            },
            "returns": {
                "irr":         None if not math.isfinite(irr)  else float(irr),
                "moic":        None if not math.isfinite(moic) else float(moic),
                "exit_equity": float(res["exit_equity"]),
            },
        }

    return {
        "bull": _run_scenario(sc_cfg.get("bull", {})),
        "base": _run_scenario({}),
        "bear": _run_scenario(sc_cfg.get("bear", {})),
    }
```

- [ ] **Step 4: Run all four new tests**

```bash
cd src && python -m pytest ../tests/test_analytics.py::test_scenario_block_has_three_keys ../tests/test_analytics.py::test_scenario_block_base_matches_run_lbo ../tests/test_analytics.py::test_scenario_block_bull_gt_base_gt_bear ../tests/test_analytics.py::test_scenario_block_zero_ebitda_clamp_returns_none -v
```

Expected: all four `PASSED`

- [ ] **Step 5: Run the full Python test suite to check no regressions**

```bash
cd src && python -m pytest ../tests/ -v
```

Expected: all existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add src/analytics.py tests/test_analytics.py
git commit -m "feat(analytics): add scenario_block() — Bull/Base/Bear precompute"
```

---

## Task 3: Wire scenarios into the build pipeline

**Files:**
- Modify: `src/analytics.py` (lines 309–311, 365–380, 382–406, 328–345)

- [ ] **Step 1: Write the failing tests**

In `tests/test_analytics.py`, add:

```python
def test_build_company_block_has_scenarios_key():
    cfg = scenarios_cfg()
    block = analytics.build_company_block(sample_row(), cfg)
    assert "scenarios" in block
    sc = block["scenarios"]
    assert sc is not None
    assert "bull" in sc and "base" in sc and "bear" in sc


def test_build_company_block_degenerate_has_scenarios_none():
    """Degenerate (net-cash) company stub must include scenarios: None."""
    cfg = scenarios_cfg()
    # Force a degenerate: entry_ev ≈ 0 by making market_cap tiny and net_debt negative
    row = sample_row()
    row["market_cap_cr"] = 10.0     # tiny market cap
    row["net_debt_cr"] = -9990.0    # large net cash → entry_ev near zero
    block = analytics.build_company_block(row, cfg)
    assert block["returns"]["degenerate"] is True
    assert block["scenarios"] is None


def test_build_results_passers_have_scenario_irrs():
    cfg = scenarios_cfg()
    row = sample_row()
    row["passes_screen"] = True
    df = pd.DataFrame([row])
    payload = analytics.build_results(df, cfg, "2026-01-01")
    passer = payload["passers"][0]
    assert "scenario_irrs" in passer
    si = passer["scenario_irrs"]
    assert si is not None
    assert "bull" in si and "base" in si and "bear" in si
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src && python -m pytest ../tests/test_analytics.py::test_build_company_block_has_scenarios_key -v
```

Expected: `FAILED` with `AssertionError` (key missing)

- [ ] **Step 3: Update `COMPANY_KEYS`**

Find line 309 in `src/analytics.py`:
```python
COMPANY_KEYS = ["ticker", "name", "statements", "debt_schedule", "sources_uses",
                "returns", "montecarlo", "downside", "sensitivity", "solvers",
                "sobol", "feasibility", "delisting"]
```

Replace with:
```python
COMPANY_KEYS = ["ticker", "name", "statements", "debt_schedule", "sources_uses",
                "returns", "montecarlo", "downside", "sensitivity", "solvers",
                "sobol", "feasibility", "delisting", "scenarios"]
```

- [ ] **Step 4: Add `"scenarios": None` to the degenerate stub**

Find the degenerate early-return block in `build_company_block` (around line 370–380). It currently ends with:
```python
            "feasibility": feasibility_score(row, cfg),
            "delisting": delisting_model(inp, row, cfg),
        }
```

Change it to:
```python
            "feasibility": feasibility_score(row, cfg),
            "delisting": delisting_model(inp, row, cfg),
            "scenarios": None,
        }
```

- [ ] **Step 5: Add `scenario_block()` call in the non-degenerate return**

Find the non-degenerate return in `build_company_block` (around line 404–406). It currently ends with:
```python
        "feasibility": feasibility_score(row, cfg),
        "delisting": delisting_model(inp, row, cfg),
    }
```

Change it to:
```python
        "feasibility": feasibility_score(row, cfg),
        "delisting": delisting_model(inp, row, cfg),
        "scenarios": scenario_block(inp, cfg),
    }
```

- [ ] **Step 6: Add `scenario_irrs` to `build_results` passers**

Find `build_results` (line 328). The inner loop currently appends:
```python
        passers.append({"ticker": row["ticker"], "name": block["name"],
                        "irr": block["returns"]["irr"], "moic": block["returns"]["moic"],
                        "degenerate": block["returns"]["degenerate"],
                        "feasibility": block["feasibility"]["score"],
                        "max_bid_premium_pct": max_bid.get("max_premium_pct")})
```

Replace with:
```python
        sc = block.get("scenarios")

        def _sc_irr(sc, name):
            if not sc:
                return None
            s = sc.get(name)
            return s["returns"]["irr"] if s else None

        passers.append({"ticker": row["ticker"], "name": block["name"],
                        "irr": block["returns"]["irr"], "moic": block["returns"]["moic"],
                        "degenerate": block["returns"]["degenerate"],
                        "feasibility": block["feasibility"]["score"],
                        "max_bid_premium_pct": max_bid.get("max_premium_pct"),
                        "scenario_irrs": {
                            "bull": _sc_irr(sc, "bull"),
                            "base": _sc_irr(sc, "base"),
                            "bear": _sc_irr(sc, "bear"),
                        }})
```

Note: define `_sc_irr` as a module-level helper above `build_results` rather than inside the loop — move it there after the tests pass for cleaner style.

- [ ] **Step 7: Run the three new tests**

```bash
cd src && python -m pytest ../tests/test_analytics.py::test_build_company_block_has_scenarios_key ../tests/test_analytics.py::test_build_company_block_degenerate_has_scenarios_none ../tests/test_analytics.py::test_build_results_passers_have_scenario_irrs -v
```

Expected: all `PASSED`

- [ ] **Step 8: Run full Python suite**

```bash
cd src && python -m pytest ../tests/ -v
```

Expected: all pass

- [ ] **Step 9: Commit**

```bash
git add src/analytics.py tests/test_analytics.py
git commit -m "feat(analytics): wire scenario_block into build pipeline"
```

---

## Task 4: TypeScript types

**Files:**
- Modify: `web-app/lib/types.ts`

- [ ] **Step 1: Add the five new interfaces**

Open `web-app/lib/types.ts`. Before the `CompanyBlock` interface, add:

```typescript
export interface ScenarioAssumptions {
  revenue_growth: number;
  ebitda_margin: number;   // absolute margin (e.g. 0.22), NOT the delta
  exit_multiple: number;
}
export interface ScenarioFinancials {
  revenue: number;
  ebitda: number;
  fcf_for_debt: number;    // matches run_lbo cash_flow key; displayed as "FCF" in UI
}
export interface ScenarioReturns {
  irr: number | null;
  moic: number | null;
  exit_equity: number;
}
export interface Scenario {
  assumptions: ScenarioAssumptions;
  financials: ScenarioFinancials;
  returns: ScenarioReturns;
}
export interface ScenarioBlock {
  bull: Scenario | null;   // null when sc_ebitda clamped to zero
  base: Scenario | null;
  bear: Scenario | null;
}
```

- [ ] **Step 2: Extend `CompanyBlock`**

Find the `CompanyBlock` interface. After the `delisting` field, add:
```typescript
  scenarios: ScenarioBlock | null;
```

- [ ] **Step 3: Extend `Passer`**

Find the `Passer` interface. After `max_bid_premium_pct`, add:
```typescript
  scenario_irrs: { bull: number | null; base: number | null; bear: number | null } | null;
```

- [ ] **Step 4: Run TS type-check**

```bash
cd web-app && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add web-app/lib/types.ts
git commit -m "feat(types): add ScenarioBlock interfaces, extend CompanyBlock and Passer"
```

---

## Task 5: `ScenarioWarRoom` tearsheet component

**Files:**
- Create: `web-app/components/tearsheet/ScenarioWarRoom.tsx`

- [ ] **Step 1: Write the failing test**

Create `web-app/components/tearsheet/ScenarioWarRoom.test.tsx`:

```typescript
import { it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ScenarioWarRoom } from "@/components/tearsheet/ScenarioWarRoom";
import type { ScenarioBlock } from "@/lib/types";

const fixture: ScenarioBlock = {
  bull: {
    assumptions: { revenue_growth: 0.16, ebitda_margin: 0.25, exit_multiple: 12 },
    financials:  { revenue: 820, ebitda: 205, fcf_for_debt: 155 },
    returns:     { irr: 0.31, moic: 3.9, exit_equity: 1820 },
  },
  base: {
    assumptions: { revenue_growth: 0.08, ebitda_margin: 0.20, exit_multiple: 10 },
    financials:  { revenue: 620, ebitda: 112, fcf_for_debt: 82 },
    returns:     { irr: 0.22, moic: 2.7, exit_equity: 980 },
  },
  bear: {
    assumptions: { revenue_growth: 0.03, ebitda_margin: 0.15, exit_multiple: 8 },
    financials:  { revenue: 480, ebitda: 58, fcf_for_debt: 31 },
    returns:     { irr: 0.09, moic: 1.5, exit_equity: 410 },
  },
};

it("renders BULL / BASE / BEAR column headers", () => {
  const { getByText } = render(<ScenarioWarRoom scenarios={fixture} />);
  getByText("BULL"); getByText("BASE"); getByText("BEAR");
});

it("renders assumption rows", () => {
  const { getByText } = render(<ScenarioWarRoom scenarios={fixture} />);
  getByText("Rev growth"); getByText("Margin"); getByText("Exit multiple");
});

it("renders returns rows", () => {
  const { getByText } = render(<ScenarioWarRoom scenarios={fixture} />);
  getByText("IRR"); getByText("MOIC"); getByText("Exit equity");
});

it("renders nothing when scenarios is null", () => {
  const { container } = render(<ScenarioWarRoom scenarios={null} />);
  expect(container.firstChild).toBeNull();
});

it("reads fcf_for_debt not fcf", () => {
  const { getByText } = render(<ScenarioWarRoom scenarios={fixture} />);
  getByText("FCF");  // displayed label; ensure render doesn't crash on fcf_for_debt key
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd web-app && npx vitest run components/tearsheet/ScenarioWarRoom.test.tsx
```

Expected: `FAILED` — module not found

- [ ] **Step 3: Create the component**

Create `web-app/components/tearsheet/ScenarioWarRoom.tsx`:

```typescript
import type { ScenarioBlock, Scenario } from "@/lib/types";
import { pct, mult, cr } from "@/lib/format";

interface Props { scenarios: ScenarioBlock | null; }

function irrColor(irr: number | null): string {
  if (irr == null) return "text-muted";
  if (irr >= 0.20) return "text-green-600";
  if (irr >= 0.10) return "text-amber-600";
  return "text-red-600";
}

interface RowProps { label: string; bull: string; base: string; bear: string; bullClass?: string; baseClass?: string; bearClass?: string; }
function Row({ label, bull, base, bear, bullClass = "", baseClass = "", bearClass = "" }: RowProps) {
  return (
    <tr className="border-t border-edge text-[11px]">
      <td className="py-1 pr-3 font-mono text-faint">{label}</td>
      <td className={`py-1 text-center bg-green-50 ${bullClass}`}>{bull}</td>
      <td className={`py-1 text-center ${baseClass}`}>{base}</td>
      <td className={`py-1 text-center bg-red-50 ${bearClass}`}>{bear}</td>
    </tr>
  );
}

function SectionHeader({ label }: { label: string }) {
  return (
    <tr>
      <td colSpan={4} className="pt-3 pb-1 font-mono text-[10px] uppercase tracking-wider text-faint">{label}</td>
    </tr>
  );
}

function fmt(s: Scenario | null, fn: (s: Scenario) => string): string {
  return s ? fn(s) : "—";
}

export function ScenarioWarRoom({ scenarios }: Props) {
  if (!scenarios) return null;
  const { bull, base, bear } = scenarios;

  return (
    <table className="w-full">
      <thead>
        <tr className="text-[11px]">
          <th className="w-28 text-left font-mono text-faint" />
          <th className="text-center font-mono text-green-600">BULL</th>
          <th className="text-center font-mono text-ink">BASE</th>
          <th className="text-center font-mono text-red-600">BEAR</th>
        </tr>
      </thead>
      <tbody>
        <SectionHeader label="Assumptions" />
        <Row label="Rev growth"
          bull={fmt(bull, s => pct(s.assumptions.revenue_growth, 0))}
          base={fmt(base, s => pct(s.assumptions.revenue_growth, 0))}
          bear={fmt(bear, s => pct(s.assumptions.revenue_growth, 0))} />
        <Row label="Margin"
          bull={fmt(bull, s => pct(s.assumptions.ebitda_margin, 0))}
          base={fmt(base, s => pct(s.assumptions.ebitda_margin, 0))}
          bear={fmt(bear, s => pct(s.assumptions.ebitda_margin, 0))} />
        <Row label="Exit multiple"
          bull={fmt(bull, s => `${s.assumptions.exit_multiple.toFixed(1)}x`)}
          base={fmt(base, s => `${s.assumptions.exit_multiple.toFixed(1)}x`)}
          bear={fmt(bear, s => `${s.assumptions.exit_multiple.toFixed(1)}x`)} />

        <SectionHeader label="Financials at exit (₹cr)" />
        <Row label="Revenue"
          bull={fmt(bull, s => cr(s.financials.revenue))}
          base={fmt(base, s => cr(s.financials.revenue))}
          bear={fmt(bear, s => cr(s.financials.revenue))} />
        <Row label="EBITDA"
          bull={fmt(bull, s => cr(s.financials.ebitda))}
          base={fmt(base, s => cr(s.financials.ebitda))}
          bear={fmt(bear, s => cr(s.financials.ebitda))} />
        <Row label="FCF"
          bull={fmt(bull, s => cr(s.financials.fcf_for_debt))}
          base={fmt(base, s => cr(s.financials.fcf_for_debt))}
          bear={fmt(bear, s => cr(s.financials.fcf_for_debt))} />

        <SectionHeader label="Returns" />
        <Row label="IRR"
          bull={fmt(bull, s => pct(s.returns.irr, 1))}
          base={fmt(base, s => pct(s.returns.irr, 1))}
          bear={fmt(bear, s => pct(s.returns.irr, 1))}
          bullClass={bull ? irrColor(bull.returns.irr) + " font-bold text-sm" : ""}
          baseClass={base ? irrColor(base.returns.irr) + " font-bold text-sm" : ""}
          bearClass={bear ? irrColor(bear.returns.irr) + " font-bold text-sm" : ""} />
        <Row label="MOIC"
          bull={fmt(bull, s => mult(s.returns.moic))}
          base={fmt(base, s => mult(s.returns.moic))}
          bear={fmt(bear, s => mult(s.returns.moic))} />
        <Row label="Exit equity"
          bull={fmt(bull, s => cr(s.returns.exit_equity))}
          base={fmt(base, s => cr(s.returns.exit_equity))}
          bear={fmt(bear, s => cr(s.returns.exit_equity))} />
      </tbody>
    </table>
  );
}
```

**Note on `cr()` helper:** `cr()` already exists in `web-app/lib/format.ts` (line 5) — do **not** add it again. Its signature is `cr(v: number | null | undefined): string`, returning `"—"` for null and `₹${Math.round(v).toLocaleString("en-IN")} cr` otherwise. Use it as-is.

- [ ] **Step 4: Run tests**

```bash
cd web-app && npx vitest run components/tearsheet/ScenarioWarRoom.test.tsx
```

Expected: all tests `PASSED`

- [ ] **Step 5: Run full TS test suite**

```bash
cd web-app && npx vitest run
```

Expected: no regressions

- [ ] **Step 6: Commit**

```bash
git add web-app/components/tearsheet/ScenarioWarRoom.tsx web-app/components/tearsheet/ScenarioWarRoom.test.tsx
git commit -m "feat(ui): add ScenarioWarRoom tearsheet component"
```

---

## Task 6: `WarRoomTable` dashboard component

**Files:**
- Create: `web-app/components/WarRoomTable.tsx`

- [ ] **Step 1: Write the failing test**

Create `web-app/components/WarRoomTable.test.tsx`:

```typescript
import { it, expect } from "vitest";
import { render } from "@testing-library/react";
import { WarRoomTable } from "@/components/WarRoomTable";
import type { Passer } from "@/lib/types";

const passers: Passer[] = [
  { ticker: "TANLA", name: "Tanla Platforms", irr: 0.22, moic: 2.7, degenerate: false,
    feasibility: 80, max_bid_premium_pct: 35,
    scenario_irrs: { bull: 0.31, base: 0.22, bear: 0.09 } },
  { ticker: "JUSTDIAL", name: "Just Dial", irr: 0.19, moic: 2.4, degenerate: false,
    feasibility: 72, max_bid_premium_pct: 28,
    scenario_irrs: { bull: 0.28, base: 0.19, bear: 0.07 } },
  { ticker: "NOSCEN", name: "No Scenarios Ltd", irr: 0.15, moic: 2.0, degenerate: false,
    feasibility: 60, max_bid_premium_pct: null,
    scenario_irrs: null },
];

it("renders BULL / BASE / BEAR column headers", () => {
  const { getByText } = render(<WarRoomTable passers={passers} />);
  getByText(/BULL/i); getByText(/BASE/i); getByText(/BEAR/i);
});

it("renders a row per passer", () => {
  const { getByText } = render(<WarRoomTable passers={passers} />);
  getByText("TANLA"); getByText("JUSTDIAL");
});

it("renders — for null scenario_irrs", () => {
  const { getAllByText } = render(<WarRoomTable passers={passers} />);
  // NOSCEN row should have em-dashes
  expect(getAllByText("—").length).toBeGreaterThan(0);
});

it("renders nothing when no passer has scenario_irrs", () => {
  const noScenPassers = passers.map(p => ({ ...p, scenario_irrs: null }));
  const { container } = render(<WarRoomTable passers={noScenPassers} />);
  expect(container.firstChild).toBeNull();
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd web-app && npx vitest run components/WarRoomTable.test.tsx
```

Expected: `FAILED` — module not found

- [ ] **Step 3: Create the component**

Create `web-app/components/WarRoomTable.tsx`:

```typescript
import Link from "next/link";
import type { Passer } from "@/lib/types";
import { pct } from "@/lib/format";

interface Props { passers: Passer[]; }

function irrCell(irr: number | null): { text: string; cls: string } {
  if (irr == null) return { text: "—", cls: "text-muted" };
  const text = pct(irr, 1);
  const cls = irr >= 0.20 ? "text-green-600 font-semibold"
             : irr >= 0.10 ? "text-amber-600"
             : "text-red-600";
  return { text, cls };
}

export function WarRoomTable({ passers }: Props) {
  const hasAny = passers.some(p => p.scenario_irrs != null);
  if (!hasAny) return null;

  const sorted = [...passers].sort((a, b) => {
    const ai = a.scenario_irrs?.base ?? -Infinity;
    const bi = b.scenario_irrs?.base ?? -Infinity;
    return bi - ai;
  });

  return (
    <table className="w-full text-[11px]">
      <thead>
        <tr className="border-b border-edge">
          <th className="pb-1 text-left font-mono text-faint">Company</th>
          <th className="pb-1 text-center font-mono text-green-600">BULL</th>
          <th className="pb-1 text-center font-mono text-ink">BASE</th>
          <th className="pb-1 text-center font-mono text-red-600">BEAR</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map(p => {
          const si = p.scenario_irrs;
          const bull = irrCell(si?.bull ?? null);
          const base = irrCell(si?.base ?? null);
          const bear = irrCell(si?.bear ?? null);
          return (
            <tr key={p.ticker} className="border-t border-edge hover:bg-panel">
              <td className="py-1 pr-3">
                <Link href={`/t/${p.ticker}`} className="font-mono hover:text-emerald">
                  {p.ticker}
                </Link>
                <span className="ml-1 text-faint">{p.name}</span>
              </td>
              <td className={`py-1 text-center ${bull.cls}`}>{bull.text}</td>
              <td className={`py-1 text-center ${base.cls}`}>{base.text}</td>
              <td className={`py-1 text-center ${bear.cls}`}>{bear.text}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 4: Run tests**

```bash
cd web-app && npx vitest run components/WarRoomTable.test.tsx
```

Expected: all `PASSED`

- [ ] **Step 5: Run full TS test suite**

```bash
cd web-app && npx vitest run
```

Expected: no regressions

- [ ] **Step 6: Commit**

```bash
git add web-app/components/WarRoomTable.tsx web-app/components/WarRoomTable.test.tsx
git commit -m "feat(ui): add WarRoomTable dashboard component"
```

---

## Task 7: Page wiring

**Files:**
- Modify: `web-app/app/t/[ticker]/page.tsx`
- Modify: `web-app/app/page.tsx`

- [ ] **Step 1: Wire `ScenarioWarRoom` into tearsheet**

In `web-app/app/t/[ticker]/page.tsx`:

Add import at the top with the other tearsheet imports:
```typescript
import { ScenarioWarRoom } from "@/components/tearsheet/ScenarioWarRoom";
```

Find the **non-degenerate fragment** — it starts at `{co.returns.degenerate ? <DegenerateNotice /> : (` (line 48) and its content is wrapped in a `<>…</>` fragment. The Returns attribution section ends around line 55 with a `</Section>`. Insert the War Room section **immediately after that `</Section>`, still inside the non-degenerate fragment** (before the Monte Carlo `<Section>`):

```tsx
          <Section title="Scenario war room — Bull / Base / Bear">
            <ScenarioWarRoom scenarios={co.scenarios} />
          </Section>
```

Do **not** add an outer `{co.scenarios && (…)}` guard — `ScenarioWarRoom` already returns `null` when `scenarios` is null, so the section header will still render for degenerate stubs. If you want to suppress the header too, wrap the whole section: `{co.scenarios && (<Section …><ScenarioWarRoom … /></Section>)}`. Either is acceptable; the guard is cleaner.

The insertion point in full context:
```tsx
          <Section title="Returns attribution">
            <div className="grid gap-4 lg:grid-cols-2">
              {co.returns.irr_bridge && <IrrBridge bridge={co.returns.irr_bridge} />}
              {co.returns.value_bridge && <ValueBridge bridge={co.returns.value_bridge} />}
            </div>
          </Section>

          {/* INSERT HERE — still inside the non-degenerate fragment */}
          {co.scenarios && (
            <Section title="Scenario war room — Bull / Base / Bear">
              <ScenarioWarRoom scenarios={co.scenarios} />
            </Section>
          )}

          <Section title="Risk — Monte Carlo (5,000 sims)">
```

- [ ] **Step 2: Wire `WarRoomTable` into dashboard**

In `web-app/app/page.tsx`:

Add import:
```typescript
import { WarRoomTable } from "@/components/WarRoomTable";
```

Find the grid that starts at `<div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">`. Before that div, insert a full-width war room panel:

```tsx
      <div className="mt-3">
        <Panel title="Scenario war room — Bull / Base / Bear">
          <WarRoomTable passers={r.passers} />
        </Panel>
      </div>
```

- [ ] **Step 3: Type-check**

```bash
cd web-app && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add web-app/app/t/[ticker]/page.tsx web-app/app/page.tsx
git commit -m "feat(pages): wire ScenarioWarRoom and WarRoomTable into tearsheet and dashboard"
```

---

## Task 8: Rebuild data and smoke test

**Files:**
- `web-app/public/data/results.json` (regenerated, not hand-edited)

- [ ] **Step 1: Rebuild results.json using cached market data**

Run from the project root (not `src/`):

```bash
python tools/export_data.py --no-fetch
```

Expected output ends with something like:
```
Wrote web-app/public/data/results.json  (N companies)
```

If `--no-fetch` fails because `data/market_snapshot.csv` is stale, run without the flag (requires internet).

- [ ] **Step 2: Verify scenarios appear in the output**

```bash
python -c "
import json
d = json.load(open('web-app/public/data/results.json'))
for ticker, co in d['companies'].items():
    sc = co.get('scenarios')
    print(ticker, 'scenarios:', 'OK' if sc else 'NONE (degenerate?)')
for p in d['passers']:
    print(p['ticker'], 'scenario_irrs:', p.get('scenario_irrs'))
"
```

Expected: every non-degenerate company shows `OK`; every passer has `scenario_irrs` with three keys.

- [ ] **Step 3: Run the Next.js dev build to catch any runtime errors**

```bash
cd web-app && npm run build 2>&1 | tail -20
```

Expected: `Route (app) ... compiled` with no TypeScript or import errors.

- [ ] **Step 4: Commit results.json**

```bash
git add web-app/public/data/results.json
git commit -m "data: rebuild results.json with scenario war room data"
```

---

## Done

After Task 8, the Scenario War Room is fully live:
- Dashboard `/` shows a compact Bull/Base/Bear IRR table for all passing companies
- Each tearsheet `/t/[ticker]` shows a full P&L bridge panel (assumptions → financials → returns) after the Returns Attribution section

Next Vercel deploy (or `vercel --prod` from `web-app/`) will pick up the new `results.json` automatically — no config changes needed.
