"""Shared family ordering and atomic table-writing helpers for analysis scripts."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

REAL_ORDER_BOOK = "Real order book"

# All public families, including the original real order book. Use this only in
# descriptive tables where the real order book is reported as a separate row.
FULL_FAMILY_ORDER = [REAL_ORDER_BOOK, "S", "2X", "3X", "4X", "5X", "8X", "10X"]

# Derived benchmark families only. Use this in every aggregate benchmark count,
# statistical test, performance profile, frontier table, and heatmap.
BENCHMARK_FAMILY_ORDER = ["S", "2X", "3X", "4X", "5X", "8X", "10X"]


def public_benchmark(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of *df* restricted to the derived public benchmark."""
    return df[df["dataset"].isin(BENCHMARK_FAMILY_ORDER)].copy()


def family_rank(order: Sequence[str]) -> dict[str, int]:
    """Return a stable sort-rank mapping for a family order."""
    return {dataset: rank for rank, dataset in enumerate(order)}


def validate_key_columns(df: pd.DataFrame, key_cols: Sequence[str], path: str | Path) -> None:
    """Raise a clear error when a table has empty rows or invalid key columns."""
    if df.empty:
        raise ValueError(f"Refusing to write empty table: {path}")
    missing = [column for column in key_cols if column not in df.columns]
    if missing:
        raise ValueError(f"Refusing to write {path}: missing key columns {missing}")
    for column in key_cols:
        values = df[column]
        invalid = values.isna() | values.astype(str).str.strip().eq("")
        if invalid.any():
            bad_rows = ", ".join(str(idx) for idx in values.index[invalid][:10])
            raise ValueError(
                f"Refusing to write {path}: null or empty key values in column "
                f"{column!r} at rows {bad_rows}"
            )


def atomic_write_text(path: str | Path, text: str) -> None:
    """Write text through a temporary file in the destination directory."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_text(encoding="utf-8") == text:
        return
    data = text.encode("utf-8")
    if target.exists() and target.read_bytes() == data:
        return
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def write_table(df: pd.DataFrame, path: str | Path, key_cols: Sequence[str]) -> None:
    """Validate and atomically write a CSV table."""
    validate_key_columns(df, key_cols, path)
    target = Path(path)
    atomic_write_text(target, df.to_csv(index=False))


def validate_latex_first_cells(rows: Iterable[Sequence[object]], path: str | Path) -> None:
    """Reject LaTeX table rows whose first cell is empty."""
    for index, row in enumerate(rows):
        if not row or pd.isna(row[0]) or str(row[0]).strip() == "":
            raise ValueError(f"Refusing to write {path}: empty first cell in table row {index}")
