"""Gamma=0 variant wrapper for 3X/IncT3x_7."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.GAMSPy.variant_gamma0.solve_gamma0 import solve_instance


if __name__ == "__main__":
    solve_instance(ROOT / "experiments/GAMSPy/3X/IncT3x_7.py", ROOT / "experiments/GAMSPy/variant_gamma0/results_gamma0")
