"""Live-tail a log file with ponytail (a robust `tail -F`).

Pairs with tools/run_app_logged.py, which launches the Streamlit screener and
writes its output to logs/app.log. Run this in a second terminal to watch the
app's logs stream in real time:

    python tools/run_app_logged.py        # terminal 1: starts the app
    python tools/follow_log.py            # terminal 2: ponytail follows the log

ponytail survives log rotation and truncation, so the follower keeps working
across app restarts. Ctrl-C to stop. Pass a path to follow a different file:

    python tools/follow_log.py logs/app.log
"""

import sys
from pathlib import Path

from ponytail import Follow

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG = PROJECT_ROOT / "logs" / "app.log"


def follow(path: Path, max_lines: int | None = None) -> int:
    """Stream lines from `path` as they are written. Returns the count emitted.

    `max_lines` stops after that many lines (used by the smoke check so it does
    not block forever); the default of None follows indefinitely.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)  # so the first run has something to open
    print(f"[follow_log] ponytail following {path} (Ctrl-C to stop)", flush=True)

    count = 0
    for line in Follow(str(path)).readlines():
        print(line.rstrip(), flush=True)
        count += 1
        if max_lines is not None and count >= max_lines:
            break
    return count


def main(argv: list[str]) -> None:
    path = Path(argv[0]) if argv else DEFAULT_LOG
    try:
        follow(path)
    except KeyboardInterrupt:
        print("\n[follow_log] stopped", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
