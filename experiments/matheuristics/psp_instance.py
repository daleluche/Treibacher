"""PSP instance loading and schedule evaluation utilities.

The parser adapts the literal-extraction approach used by
``experiments/GRASP/grasp_ils_psp.py`` so matheuristics can consume the same
GAMSPy-generated instance files without executing them.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

EXCESS_WEIGHT = 0.001


@dataclass(frozen=True)
class PSPInstance:
    """Dense representation of one Process Selection Problem instance."""

    name: str
    dataset: str
    T: int
    J: int
    I: int
    products: list[str]
    A: np.ndarray
    D: np.ndarray


def _extract_list_literal(text: str, varname: str) -> str:
    """Extract a Python list literal assigned to ``varname`` from source text."""
    pattern = rf"^{re.escape(varname)}\s*=\s*(\[)"
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        raise ValueError(f"Variable {varname!r} not found in source.")

    start = match.start(1)
    depth = 0
    for pos in range(start, len(text)):
        char = text[pos]
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return text[start : pos + 1]

    raise ValueError(f"Could not find the end of list {varname!r}.")


def _extract_scalar(text: str, varname: str, default: str | None = None) -> str:
    """Extract a simple scalar assignment from source text."""
    pattern = rf"^{re.escape(varname)}\s*=\s*(.+)$"
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        if default is None:
            raise ValueError(f"Variable {varname!r} not found in source.")
        return default
    return match.group(1).strip()


def _literal_scalar(text: str, varname: str, default: str | None = None) -> object:
    """Extract and parse a scalar literal assignment."""
    return ast.literal_eval(_extract_scalar(text, varname, default))


def load_instance(path_to_gamspy_py: str | Path) -> PSPInstance:
    """Load a PSP instance from a GAMSPy-generated Python file.

    The function parses ``PRODUCTS``, ``NUM_PROCESSES``, ``NUM_PERIODS``,
    ``A_RECORDS``, and ``D_RECORDS`` as literals. It does not import or execute
    the source file.
    """
    path = Path(path_to_gamspy_py)
    text = path.read_text(encoding="utf-8")

    products = list(ast.literal_eval(_extract_list_literal(text, "PRODUCTS")))
    product_index = {product: idx for idx, product in enumerate(products)}
    I = len(products)
    J = int(_extract_scalar(text, "NUM_PROCESSES"))
    T = int(_extract_scalar(text, "NUM_PERIODS"))
    name = str(_literal_scalar(text, "INSTANCE", repr(path.stem)))
    dataset = str(_literal_scalar(text, "DATASET", repr(path.parent.name)))

    A = np.zeros((I, J), dtype=np.float64)
    for product, process, value in ast.literal_eval(_extract_list_literal(text, "A_RECORDS")):
        i = product_index.get(product)
        j = int(process) - 1
        if i is not None and 0 <= j < J:
            A[i, j] = float(value)

    D = np.zeros((I, T), dtype=np.float64)
    for product, period, value in ast.literal_eval(_extract_list_literal(text, "D_RECORDS")):
        i = product_index.get(product)
        t = int(period) - 1
        if i is not None and 0 <= t < T:
            D[i, t] = float(value)

    return PSPInstance(
        name=name,
        dataset=dataset,
        T=T,
        J=J,
        I=I,
        products=products,
        A=A,
        D=D,
    )


def evaluate(schedule: Sequence[int], inst: PSPInstance) -> tuple[float, float, float]:
    """Evaluate a 1-indexed PSP schedule with 0 as an idle period.

    Returns ``(Z, shortage_total, excess_total)`` using the MIP objective
    ``sum(F[i,t] + 0.001 * E[i,t])`` over cumulative production-demand balance.
    """
    schedule_arr = np.asarray(schedule, dtype=np.int64)
    if schedule_arr.shape != (inst.T,):
        raise ValueError(f"Schedule length must be {inst.T}, got {schedule_arr.size}.")
    if np.any(schedule_arr < 0) or np.any(schedule_arr > inst.J):
        raise ValueError(f"Schedule entries must be in [0, {inst.J}].")

    cumulative = np.zeros(inst.I, dtype=np.float64)
    shortage_total = 0.0
    excess_total = 0.0

    for t, process in enumerate(schedule_arr):
        if process > 0:
            cumulative += inst.A[:, process - 1]
        cumulative -= inst.D[:, t]
        shortage_total += float(np.maximum(-cumulative, 0.0).sum())
        excess_total += float(np.maximum(cumulative, 0.0).sum())

    z_value = shortage_total + EXCESS_WEIGHT * excess_total
    return float(z_value), float(shortage_total), float(excess_total)
