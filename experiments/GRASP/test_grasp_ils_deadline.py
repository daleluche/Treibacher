"""Regression tests for GRASP+ILS deadline enforcement."""
from __future__ import annotations

from pathlib import Path

from experiments.GRASP.grasp_ils_psp import HARD_STOP_ENFORCED, load_instance_from_py, run_grasp_ils


ROOT = Path(__file__).resolve().parents[2]


def test_grasp_ils_honors_short_deadline() -> None:
    """A tiny run should stop near its absolute wall-clock deadline."""
    inst = load_instance_from_py(
        str(ROOT / "experiments" / "matheuristics" / "synthetic_tiny.py"),
        name="synthetic_tiny",
        dataset="Synthetic",
    )

    result = run_grasp_ils(inst, time_limit_s=0.2, run_id=1, seed=123)

    assert HARD_STOP_ENFORCED is True
    assert result.total_time <= 0.6
    assert len(result.scheduling) == inst.T
    assert result.objective > 0.0
