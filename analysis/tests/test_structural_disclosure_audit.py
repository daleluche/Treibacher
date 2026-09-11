"""Tests for the private structural disclosure audit."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from analysis import structural_disclosure_audit as audit
from experiments.matheuristics.psp_instance import PSPInstance


ROOT = Path(__file__).resolve().parents[2]
DATASETS = {"S": 10, "2X": 10, "3X": 10, "4X": 10, "5X": 10, "8X": 5, "10X": 5}


def instance(name: str = "S_1", dataset: str = "S", *, offset: float = 0.0) -> PSPInstance:
    """Return a small deterministic PSP instance for structural tests."""
    products = ["P01", "P02", "P03"]
    a = np.array([[1.0, 0.0, 2.0], [0.0, 3.0, 0.0], [4.0, 0.0, 5.0]]) + offset
    d = np.array([[2.0, 0.0, 1.0, 0.0], [0.0, 3.0, 0.0, 1.0], [1.0, 1.0, 0.0, 0.0]]) + offset
    return PSPInstance(name=name, dataset=dataset, T=4, J=3, I=3, products=products, A=a, D=d)


def permute(inst: PSPInstance) -> PSPInstance:
    """Return an instance with product rows reversed."""
    order = [2, 1, 0]
    return PSPInstance(
        name=inst.name,
        dataset=inst.dataset,
        T=inst.T,
        J=inst.J,
        I=inst.I,
        products=[inst.products[i] for i in order],
        A=inst.A[order, :],
        D=inst.D[order, :],
    )


def with_block(inst: PSPInstance) -> PSPInstance:
    """Return an instance with the demand matrix embedded as a temporal block."""
    return PSPInstance(
        name=inst.name,
        dataset=inst.dataset,
        T=inst.T + 2,
        J=inst.J,
        I=inst.I,
        products=inst.products,
        A=inst.A.copy(),
        D=np.column_stack([np.zeros((inst.I, 1)), inst.D, np.zeros((inst.I, 1))]),
    )


def write_pair(root: Path, inst: PSPInstance, *, json_inst: PSPInstance | None = None) -> None:
    """Write one Python/JSON public instance pair."""
    py_path = root / "instances" / "gamspy_py" / inst.dataset / f"{inst.name}.py"
    json_path = root / "instances" / "json" / inst.dataset / f"{inst.name}.json"
    py_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    a_records = [
        (product, j + 1, float(inst.A[i, j]))
        for i, product in enumerate(inst.products)
        for j in range(inst.J)
        if float(inst.A[i, j]) != 0.0
    ]
    d_records = [
        (product, t + 1, float(inst.D[i, t]))
        for i, product in enumerate(inst.products)
        for t in range(inst.T)
        if float(inst.D[i, t]) != 0.0
    ]
    py_path.write_text(
        "\n".join(
            [
                f"INSTANCE = {inst.name!r}",
                f"DATASET = {inst.dataset!r}",
                f"PRODUCTS = {inst.products!r}",
                f"NUM_PROCESSES = {inst.J}",
                f"NUM_PERIODS = {inst.T}",
                f"A_RECORDS = {a_records!r}",
                f"D_RECORDS = {d_records!r}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    json_source = json_inst or inst
    json_path.write_text(
        json.dumps(
            {
                "name": json_source.name,
                "dataset": json_source.dataset,
                "T": json_source.T,
                "J": json_source.J,
                "I": json_source.I,
                "products": json_source.products,
                "A_records": [
                    {"product": product, "process": j + 1, "value": float(json_source.A[i, j])}
                    for i, product in enumerate(json_source.products)
                    for j in range(json_source.J)
                    if float(json_source.A[i, j]) != 0.0
                ],
                "D_records": [
                    {"product": product, "period": t + 1, "value": float(json_source.D[i, t])}
                    for i, product in enumerate(json_source.products)
                    for t in range(json_source.T)
                    if float(json_source.D[i, t]) != 0.0
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def write_public_root(root: Path, bad_json: PSPInstance | None = None, mismatch: bool = False) -> None:
    """Write 60 paired public fixtures, optionally altering the first JSON."""
    first = True
    for dataset, count in DATASETS.items():
        for index in range(1, count + 1):
            name = f"S_{index}" if dataset == "S" else f"IncT{dataset.lower()}_{index}"
            inst = instance(name=name, dataset=dataset, offset=10.0 + index)
            json_inst = None
            if first and bad_json is not None:
                json_inst = bad_json
            elif first and mismatch:
                json_inst = instance(name=inst.name, dataset=inst.dataset, offset=99.0)
            write_pair(root, inst, json_inst=json_inst)
            first = False


def test_structural_rules_reject_private_signature_variants() -> None:
    """Protected D and A+D signatures are detected independent of product order."""
    real = instance()
    assert set(audit.check_instance_against_private_signature(real, real)) == {
        "D_FULL_MATRIX",
        "D_CONTIGUOUS_19_PERIOD_BLOCK",
        "AD_JOINT_FULL_OR_BLOCK",
    }
    assert "D_FULL_MATRIX" in audit.check_instance_against_private_signature(permute(real), real)
    assert "AD_JOINT_FULL_OR_BLOCK" in audit.check_instance_against_private_signature(permute(real), real)
    assert "D_CONTIGUOUS_19_PERIOD_BLOCK" in audit.check_instance_against_private_signature(permute(with_block(real)), real)


def test_shared_a_without_protected_d_passes() -> None:
    """Sharing A alone is allowed by the disclosure rules."""
    real = instance()
    candidate = PSPInstance("S_1", "S", real.T, real.J, real.I, real.products, real.A.copy(), real.D + 100.0)
    assert audit.check_instance_against_private_signature(candidate, real) == []


def test_structural_audit_rejects_json_only_signature(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A protected signature present only in JSON fails representation equivalence."""
    real = instance()
    write_public_root(tmp_path, bad_json=real)
    monkeypatch.setattr(audit, "load_private_real_order_book", lambda: real)
    with pytest.raises(RuntimeError, match="Python/JSON A matrix mismatch"):
        audit.run_structural_audit(tmp_path)


def test_structural_audit_rejects_python_json_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Numeric divergence between public representations fails before disclosure checks."""
    write_public_root(tmp_path, mismatch=True)
    monkeypatch.setattr(audit, "load_private_real_order_book", instance)
    with pytest.raises(RuntimeError, match="Python/JSON A matrix mismatch"):
        audit.run_structural_audit(tmp_path)


def test_structural_audit_accepts_public_release_instances() -> None:
    """The public release instances must not contain protected real-order-book blocks."""
    dist = ROOT / "release" / "dist"
    if not dist.exists():
        pytest.skip("release/dist has not been built")
    result = audit.run_structural_audit(dist)
    assert result.status == "passed"
    assert result.representations_examined == 120
