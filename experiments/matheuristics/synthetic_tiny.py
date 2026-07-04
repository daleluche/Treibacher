"""Deterministic tiny PSP instance for matheuristic smoke tests."""
from __future__ import annotations

import numpy as np

from experiments.matheuristics.psp_instance import PSPInstance


def build_synthetic_tiny(seed: int = 42) -> PSPInstance:
    """Build a deterministic PSP instance small enough for demo solvers."""
    rng = np.random.default_rng(seed)
    T = 8
    J = 10
    I = 5
    products = [f"P{i + 1}" for i in range(I)]

    A = rng.integers(0, 16, size=(I, J)).astype(np.float64)
    D = rng.integers(4, 18, size=(I, T)).astype(np.float64)

    return PSPInstance(
        name="synthetic_tiny",
        dataset="Synthetic",
        T=T,
        J=J,
        I=I,
        products=products,
        A=A,
        D=D,
    )


if __name__ == "__main__":
    inst = build_synthetic_tiny()
    print(f"{inst.name}: T={inst.T}, J={inst.J}, I={inst.I}")
