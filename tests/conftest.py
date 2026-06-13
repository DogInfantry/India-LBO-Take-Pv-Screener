import pathlib
import sys

# Make `src/` importable as top-level modules (lbo_model, screener, ...)
SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
