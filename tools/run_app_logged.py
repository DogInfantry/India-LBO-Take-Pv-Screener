"""Launch the Streamlit screener with all output captured to logs/app.log.

The log file is what tools/follow_log.py tails with ponytail. Running the app
this way (instead of plain `streamlit run`) gives a single, rotation-safe log
that the follower can stream live and across restarts.

    python tools/run_app_logged.py            # starts the app, logging to logs/app.log
    python tools/follow_log.py                # (other terminal) live-tail it

Ctrl-C to stop the app.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP = PROJECT_ROOT / "src" / "app.py"
LOG = PROJECT_ROOT / "logs" / "app.log"


def main() -> int:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "streamlit", "run", str(APP)]
    print(f"[run_app_logged] {' '.join(cmd)}\n[run_app_logged] logging to {LOG}",
          flush=True)
    # Line-buffered so the follower sees output promptly; merge stderr into stdout.
    with open(LOG, "w", encoding="utf-8", buffering=1) as fh:
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                cwd=str(PROJECT_ROOT), text=True)
        try:
            return proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            return proc.wait()


if __name__ == "__main__":
    raise SystemExit(main())
