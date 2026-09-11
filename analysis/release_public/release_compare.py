"""Comparison helpers for public release reproduction checks."""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

KEY_COLUMNS = {
    "block_map.csv": ["block_id", "source_artifact"],
    "comparison_by_dataset.csv": ["dataset"],
    "comparison_table.csv": ["dataset", "instance"],
    "gamma_effect.csv": ["dataset", "instance"],
    "gamma_effect_by_set.csv": ["dataset"],
    "gamma_tradeoff_2x.csv": ["instance"],
    "gamma_tradeoff_all.csv": ["dataset", "instance"],
    "ils_equal_budget.csv": ["dataset", "instance"],
    "ils_equal_budget_600.csv": ["dataset", "instance"],
    "ils_equal_budget_runs.csv": ["method", "dataset", "instance", "run_id"],
    "ils_equal_budget_600_runs.csv": ["method", "dataset", "instance", "run_id"],
    "master_instances.csv": ["method", "dataset", "instance"],
    "master_runs.csv": ["method", "dataset", "instance", "run_id"],
    "sprint3_canonical_3600_cells.csv": ["dataset", "instance"],
    "sprint3_cell_sources.csv": ["scope", "budget_s", "method"],
    "sprint3_descriptive_by_scale.csv": ["scope", "method"],
    "sprint3_frontier_counts.csv": ["scope", "budget_s"],
    "sprint3_mip10800_8x10x.csv": ["dataset", "instance"],
    "sprint3_q5_cross_budget.csv": ["dataset", "instance"],
    "sprint3_q5_verdict.csv": ["dataset"],
    "sprint3_scale_8x10x_canonical_v2.csv": ["dataset", "instance"],
    "sprint3_scale_v2_construction.csv": ["dataset", "instance", "method"],
    "sprint3_seed_variability.csv": ["dataset", "instance"],
    "sprint3_seed_window_audit.csv": ["instance", "seed"],
    "sprint3_statistical_tests.csv": ["scope", "metric"],
    "bks_counterfactual_without_mip10800.csv": ["dataset", "instance"],
}


def manifest_outputs(manifest: Path) -> list[str]:
    """Return public analysis outputs listed in a manifest."""
    outputs: list[str] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        outputs.append(clean.split("#", 1)[0].strip())
    return outputs


def compare_csv_files(observed_path: Path, expected_path: Path, name: str) -> None:
    """Compare two CSV files with exact nonnumeric equality and tight numeric tolerance."""
    observed = pd.read_csv(observed_path)
    expected = pd.read_csv(expected_path)
    if list(observed.columns) != list(expected.columns):
        raise AssertionError(f"{name}: columns differ: {list(observed.columns)} != {list(expected.columns)}")
    keys = [column for column in KEY_COLUMNS.get(name, []) if column in observed.columns]
    if keys:
        observed = observed.sort_values(keys).reset_index(drop=True)
        expected = expected.sort_values(keys).reset_index(drop=True)
    else:
        observed = observed.reset_index(drop=True)
        expected = expected.reset_index(drop=True)
    if len(observed) != len(expected):
        raise AssertionError(f"{name}: row count differs: {len(observed)} != {len(expected)}")
    for row_index in range(len(expected)):
        key = {
            column: expected.iloc[row_index][column]
            for column in keys
        } if keys else {"row": row_index}
        for column in expected.columns:
            exp = expected.iloc[row_index][column]
            obs = observed.iloc[row_index][column]
            if pd.isna(exp) and pd.isna(obs):
                continue
            if is_numeric(exp) and is_numeric(obs):
                if not math.isclose(float(obs), float(exp), rel_tol=1e-12, abs_tol=1e-9):
                    raise AssertionError(f"{name}: numeric mismatch at {key}, column {column}: {obs!r} != {exp!r}")
            elif str(obs) != str(exp):
                raise AssertionError(f"{name}: value mismatch at {key}, column {column}: {obs!r} != {exp!r}")


def is_numeric(value: object) -> bool:
    """Return whether a scalar can be compared numerically."""
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def compare_output_dirs(observed_root: Path, expected_root: Path, manifest: Path) -> None:
    """Compare all manifest-listed public analysis outputs."""
    missing: list[str] = []
    for name in manifest_outputs(manifest):
        observed = observed_root / name
        expected = expected_root / name
        if not observed.exists() or not expected.exists():
            missing.append(name)
            continue
        compare_csv_files(observed, expected, name)
    if missing:
        raise AssertionError(f"Missing reproduced or reference outputs: {missing}")
