import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages" / "contracts"), str(ROOT / "services" / "api")]
os.environ.setdefault("DEMO_ROUND_DELAY_MS", "0")
os.environ.setdefault("STORE", "memory")
os.environ.setdefault("COMPILER", "template")
