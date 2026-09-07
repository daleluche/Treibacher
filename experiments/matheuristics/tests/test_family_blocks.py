"""Tests for benchmark family block mapping."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from analysis.families import base_pattern


ROOT = Path(__file__).resolve().parents[3]


def test_base_pattern_name_variants() -> None:
    """Map each supported instance naming convention to its base pattern."""
    assert base_pattern("S_1") == "S_1"
    assert base_pattern("IncT2X_10") == "S_10"
    assert base_pattern("IncT3x_7") == "S_7"
    assert base_pattern("IncT4X_8") == "S_8"
    assert base_pattern("IncT8x_2") == "S_2"
    assert base_pattern("IncT10X_6") == "S_6"
    assert base_pattern("REAL_1") == "REAL_1"


def test_generated_scale_blocks_have_expected_membership() -> None:
    """Check that derived benchmark scales expose the expected base blocks."""
    comp = pd.read_csv(ROOT / "analysis" / "output" / "comparison_table.csv")
    comp["base_pattern"] = comp["instance"].map(base_pattern)

    def block_index(block: str) -> int:
        return int(block.split("_", 1)[1])

    for dataset in ["2X", "3X", "4X", "5X"]:
        blocks = sorted(comp.loc[comp["dataset"] == dataset, "base_pattern"], key=block_index)
        assert blocks == [f"S_{idx}" for idx in range(1, 11)]

    for dataset in ["8X", "10X"]:
        blocks = sorted(comp.loc[comp["dataset"] == dataset, "base_pattern"], key=block_index)
        assert blocks == [f"S_{idx}" for idx in range(2, 7)]
