"""Deterministic tiny PSP instance for matheuristic smoke tests."""
from __future__ import annotations

import numpy as np

from experiments.matheuristics.psp_instance import PSPInstance

INSTANCE = "synthetic_tiny"
DATASET = "Synthetic"
PRODUCTS = ["P1", "P2", "P3", "P4", "P5"]
NUM_PROCESSES = 10
NUM_PERIODS = 8
NUM_PRODUCTS = 5
A_RECORDS = [["P1", "1", 1.0], ["P1", "2", 12.0], ["P1", "3", 10.0], ["P1", "4", 7.0], ["P1", "5", 6.0], ["P1", "6", 13.0], ["P1", "7", 1.0], ["P1", "8", 11.0], ["P1", "9", 3.0], ["P1", "10", 1.0], ["P2", "1", 8.0], ["P2", "2", 15.0], ["P2", "3", 11.0], ["P2", "4", 12.0], ["P2", "5", 11.0], ["P2", "6", 12.0], ["P2", "7", 8.0], ["P2", "8", 2.0], ["P2", "9", 13.0], ["P2", "10", 7.0], ["P3", "1", 8.0], ["P3", "2", 5.0], ["P3", "3", 2.0], ["P3", "4", 14.0], ["P3", "5", 12.0], ["P3", "6", 10.0], ["P3", "7", 6.0], ["P3", "8", 13.0], ["P3", "9", 8.0], ["P3", "10", 7.0], ["P4", "1", 7.0], ["P4", "2", 3.0], ["P4", "3", 1.0], ["P4", "4", 8.0], ["P4", "5", 14.0], ["P4", "6", 1.0], ["P4", "7", 13.0], ["P4", "8", 13.0], ["P4", "9", 4.0], ["P4", "10", 10.0], ["P5", "1", 2.0], ["P5", "2", 12.0], ["P5", "3", 11.0], ["P5", "4", 5.0], ["P5", "5", 1.0], ["P5", "6", 15.0], ["P5", "7", 7.0], ["P5", "8", 14.0], ["P5", "9", 10.0], ["P5", "10", 12.0]]
D_RECORDS = [["P1", "1", 14.0], ["P1", "2", 6.0], ["P1", "3", 9.0], ["P1", "4", 10.0], ["P1", "5", 10.0], ["P1", "6", 4.0], ["P1", "7", 11.0], ["P1", "8", 6.0], ["P2", "1", 14.0], ["P2", "2", 13.0], ["P2", "3", 16.0], ["P2", "4", 14.0], ["P2", "5", 9.0], ["P2", "6", 17.0], ["P2", "7", 9.0], ["P2", "8", 8.0], ["P3", "1", 16.0], ["P3", "2", 9.0], ["P3", "3", 5.0], ["P3", "4", 10.0], ["P3", "5", 15.0], ["P3", "6", 6.0], ["P3", "7", 10.0], ["P3", "8", 5.0], ["P4", "1", 13.0], ["P4", "2", 10.0], ["P4", "3", 8.0], ["P4", "4", 7.0], ["P4", "5", 11.0], ["P4", "6", 13.0], ["P4", "7", 17.0], ["P4", "8", 10.0], ["P5", "1", 6.0], ["P5", "2", 15.0], ["P5", "3", 12.0], ["P5", "4", 13.0], ["P5", "5", 5.0], ["P5", "6", 8.0], ["P5", "7", 14.0], ["P5", "8", 15.0]]


def build_synthetic_tiny(seed: int = 42) -> PSPInstance:
    """Build a deterministic PSP instance small enough for demo solvers."""
    if seed != 42:
        rng = np.random.default_rng(seed)
        products = [f"P{i + 1}" for i in range(NUM_PRODUCTS)]
        A = rng.integers(0, 16, size=(NUM_PRODUCTS, NUM_PROCESSES)).astype(np.float64)
        D = rng.integers(4, 18, size=(NUM_PRODUCTS, NUM_PERIODS)).astype(np.float64)
    else:
        products = PRODUCTS
        A = np.zeros((NUM_PRODUCTS, NUM_PROCESSES), dtype=np.float64)
        D = np.zeros((NUM_PRODUCTS, NUM_PERIODS), dtype=np.float64)
        product_index = {product: idx for idx, product in enumerate(products)}
        for product, process, value in A_RECORDS:
            A[product_index[product], int(process) - 1] = float(value)
        for product, period, value in D_RECORDS:
            D[product_index[product], int(period) - 1] = float(value)

    return PSPInstance(
        name=INSTANCE,
        dataset=DATASET,
        T=NUM_PERIODS,
        J=NUM_PROCESSES,
        I=NUM_PRODUCTS,
        products=products,
        A=A,
        D=D,
    )


if __name__ == "__main__":
    inst = build_synthetic_tiny()
    print(f"{inst.name}: T={inst.T}, J={inst.J}, I={inst.I}")
