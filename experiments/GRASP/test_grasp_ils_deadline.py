"""Regression tests for GRASP+ILS deadline enforcement."""
from __future__ import annotations

from pathlib import Path

from experiments.GRASP.grasp_ils_psp import HARD_STOP_ENFORCED, load_instance_from_py, run_grasp_ils, run_instance


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
    assert result.total_time <= 0.7
    assert result.deadline_overrun_s <= 0.5
    assert all(entry["time_s"] <= 0.2 for entry in result.improvements)
    assert len(result.scheduling) == inst.T
    assert result.objective > 0.0


def test_cross_run_pr_does_not_overwrite_equal_budget_best(tmp_path: Path) -> None:
    """Post-hoc cross-run PR must remain separate from equal-budget results."""
    summary = run_instance(
        py_path=str(ROOT / "experiments" / "matheuristics" / "synthetic_tiny.py"),
        name="synthetic_tiny",
        dataset="Synthetic",
        out_dir=str(tmp_path),
        n_runs=2,
        time_limit_s=0.2,
        base_seed=100,
        n_workers=1,
        enable_cross_run_pr=True,
        cross_pr_time_s=0.1,
    )

    assert summary["hard_stop_enforced"] is True
    assert summary["Z_best"] == summary["Z_best_equal_budget"]
    assert summary["cross_run_pr_enabled"] is True
    assert "Z_cross_run_pr" in summary
    assert summary["deadline_overrun_s_max"] <= 0.5
