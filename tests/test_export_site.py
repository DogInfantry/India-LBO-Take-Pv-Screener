"""Tests for the static site exporter (tools/export_site.py).

Run offline against the committed data/market_snapshot.csv (--no-fetch), so the
build is deterministic. The load-bearing checks are the PARITY tests: they guard
the standalone tools/sitegen/ copies (decision 3b) from drifting numerically
from the src/ model.
"""

import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

import export_site as ex  # noqa: E402
from lbo_model import run_lbo  # noqa: E402
from sitegen.charts import sources_uses_waterfall  # noqa: E402
from sitegen.returns import base_case_returns  # noqa: E402


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Run the exporter once into a temp web/ dir and return paths + data."""
    out = tmp_path_factory.mktemp("web")
    orig = ex.OUT_DIR
    ex.OUT_DIR = out
    try:
        ex.main(["--no-fetch"])
    finally:
        ex.OUT_DIR = orig
    cfg, _universe, results = ex.gather(no_fetch=True)
    passed = results[results["passes_screen"]]
    return {"out": out, "cfg": cfg, "results": results, "passed": passed}


def _specs(html: str) -> dict:
    m = re.search(r'id="chart-specs">(.*?)</script>', html, re.S)
    return json.loads(m.group(1).replace("<\\/", "</"))


def test_files_produced(built):
    out = built["out"]
    assert (out / "index.html").exists()
    assert (out / "assets" / "style.css").exists()
    n_pass = len(built["passed"])
    tear = list((out / "t").glob("*.html"))
    assert len(tear) == n_pass


def test_every_passer_has_a_tear_sheet(built):
    out = built["out"]
    for tkr in built["passed"]["ticker"]:
        name = tkr.replace(".NS", "")
        assert (out / "t" / f"{name}.html").exists(), f"missing tear sheet for {name}"


def test_all_specs_valid_json_with_marks(built):
    out = built["out"]
    for html_path in out.rglob("*.html"):
        specs = _specs(html_path.read_text(encoding="utf-8"))
        assert specs, f"no specs in {html_path.name}"
        for key, spec in specs.items():
            assert "mark" in spec or "layer" in spec, f"{html_path.name}:{key} not a chart"


def test_returns_parity(built):
    """Rendered IRR/MOIC per name equal an independent run_lbo, to displayed
    precision — guards tools/sitegen/returns.py from drifting from the model."""
    cfg, results = built["cfg"], built["results"]
    ret = base_case_returns(results[results["passes_screen"]], cfg)
    lbo = cfg["lbo"]
    prem = lbo.get("control_premium_pct", 25.0)
    lev = sum(t["turns"] for t in lbo["tranches"])
    expected = {}
    for _, r in results[results["passes_screen"]].iterrows():
        ev = r["market_cap_cr"] * (1 + prem / 100) + r["net_debt_cr"]
        out = run_lbo(r["revenue_cr"], r["ebitda_cr"], lbo,
                      entry_ev=ev, total_leverage=lev)
        degenerate = ev <= 0.05 * r["ebitda_cr"]
        expected[r["ticker"].replace(".NS", "")] = {
            "irr": float("nan") if degenerate else out["irr"],
            "moic": float("nan") if degenerate else out["moic"],
        }

    assert len(ret) == len(expected)
    for _, row in ret.iterrows():
        exp = expected[row["name"]]
        assert f"{row['irr']:.1%}" == f"{exp['irr']:.1%}"
        assert f"{row['moic']:.2f}" == f"{exp['moic']:.2f}"


def test_waterfall_bridge_data_parity(built):
    """The waterfall's bridge AMOUNTS equal run_lbo's sources_uses dict, so a
    corrupted local chart copy (not just restyled) is caught."""
    cfg = built["cfg"]
    lbo = cfg["lbo"]
    prem = lbo.get("control_premium_pct", 25.0)
    lev = sum(t["turns"] for t in lbo["tranches"])
    row = built["passed"].iloc[0]
    ev = row["market_cap_cr"] * (1 + prem / 100) + row["net_debt_cr"]
    out = run_lbo(row["revenue_cr"], row["ebitda_cr"], lbo,
                  entry_ev=ev, total_leverage=lev)
    su = out["sources_uses"]

    spec = sources_uses_waterfall(su).to_dict()
    # Altair stores a DataFrame's rows under datasets, referenced by name.
    datasets = spec.get("datasets") or {}
    values = next(iter(datasets.values())) if datasets else spec["data"]["values"]
    data = {d["label"]: d["amount"] for d in values}

    assert data["Enterprise value"] == pytest.approx(su["enterprise_value"])
    assert data["Transaction fees"] == pytest.approx(su["txn_fees"])
    assert data["Financing fees"] == pytest.approx(su["financing_fees"])
    assert data["Sponsor equity"] == pytest.approx(su["sponsor_equity"])
    for t in su["tranches"]:
        assert data[t["name"].capitalize() + " debt"] == pytest.approx(-t["amount"])
    # the bridge must close: EV + fees - debt = equity
    assert (su["enterprise_value"] + su["txn_fees"] + su["financing_fees"]
            - su["debt"]) == pytest.approx(su["sponsor_equity"])


def test_index_lists_all_candidates(built):
    out = built["out"]
    html = (out / "index.html").read_text(encoding="utf-8")
    for tkr in built["passed"]["ticker"]:
        name = tkr.replace(".NS", "")
        assert f"t/{name}.html" in html, f"{name} not linked on index"
