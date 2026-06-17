"""Build results.json: screen the universe, run every analytic per passer.

Usage:
  python tools/export_data.py                 # live yfinance fetch
  python tools/export_data.py --no-fetch      # use data/market_snapshot.csv
  python tools/export_data.py --out path.json # custom output path
"""
import argparse, json, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import analytics
from export_site import gather


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "web-app" / "public" / "data" / "results.json"))
    args = ap.parse_args(argv)

    cfg, _universe, results_df = gather(no_fetch=args.no_fetch)  # (cfg, universe, results)
    as_of = date.today().isoformat()
    payload = analytics.build_results(results_df, cfg, as_of)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out} -- {payload['universe']['passed']} passers "
          f"of {payload['universe']['screened']} screened (as of {payload['as_of']}).")


if __name__ == "__main__":
    main()
