"""Tests for shared PSP instance loading and evaluation."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from experiments.matheuristics.psp_instance import evaluate, load_instance
from experiments.matheuristics.rf_fo_psp import make_windows
from experiments.matheuristics.synthetic_tiny import build_synthetic_tiny

ROOT = Path(__file__).resolve().parents[3]


def test_load_s_1_instance() -> None:
    """S_1 should parse with the dimensions of the homogeneous S set."""
    inst = load_instance(ROOT / "experiments" / "GAMSPy" / "S" / "S_1.py")

    assert inst.name == "S_1"
    assert inst.dataset == "S"
    assert inst.T == 19
    assert inst.J == 159
    assert inst.I == 50
    assert inst.A.shape == (50, 159)
    assert inst.D.shape == (50, 19)
    assert len(inst.products) == 50


def test_evaluate_s_1_mip_schedule() -> None:
    """The evaluator must reproduce the optimal MIP objective for S_1."""
    inst = load_instance(ROOT / "experiments" / "GAMSPy" / "S" / "S_1.py")
    result_path = ROOT / "experiments" / "matheuristics" / "results_production" / "s1" / "S_1_mip_seed1_b600.json"
    with result_path.open("r", encoding="utf-8") as fh:
        result = json.load(fh)

    schedule = np.asarray(result["schedule"], dtype=np.int64)

    z_value, shortage_total, excess_total = evaluate(schedule, inst)

    assert abs(z_value - 36964.861) < 0.01
    assert shortage_total >= 0.0
    assert excess_total >= 0.0


def test_synthetic_tiny_is_deterministic_and_evaluable() -> None:
    """The tiny synthetic instance should be deterministic for a fixed seed."""
    inst_a = build_synthetic_tiny(seed=42)
    inst_b = build_synthetic_tiny(seed=42)

    assert inst_a.T == 8
    assert inst_a.J == 10
    assert inst_a.I == 5
    np.testing.assert_array_equal(inst_a.A, inst_b.A)
    np.testing.assert_array_equal(inst_a.D, inst_b.D)

    schedule = np.array([1, 2, 0, 3, 4, 5, 0, 6], dtype=np.int64)
    z_value, shortage_total, excess_total = evaluate(schedule, inst_a)

    assert z_value == shortage_total + 0.001 * excess_total
    assert z_value > 0.0


def test_rf_windows_anchor_final_window() -> None:
    """RF windows should cover the horizon and anchor the last window at T."""
    assert make_windows(length=25, width=10, step=5) == [
        (0, 10),
        (5, 15),
        (10, 20),
        (15, 25),
    ]
