"""Tests for the private structural disclosure audit."""
from __future__ import annotations

from pathlib import Path

import pytest

from analysis.structural_disclosure_audit import (
    check_instance_against_private_signature,
    load_private_real_order_book,
    run_structural_audit,
)


ROOT = Path(__file__).resolve().parents[2]


def test_structural_audit_rejects_private_signature_fixture() -> None:
    """A fixture containing the protected demand matrix must fail."""
    real = load_private_real_order_book()
    assert check_instance_against_private_signature(real, real) == "D_FULL_MATRIX"


def test_structural_audit_accepts_public_release_instances() -> None:
    """The 60 public instances must not contain protected real-order-book blocks."""
    dist = ROOT / "release" / "dist"
    if not dist.exists():
        pytest.skip("release/dist has not been built")
    result = run_structural_audit(dist)
    assert result.status == "passed"
    assert result.files_examined == 60
