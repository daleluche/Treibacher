"""Private structural disclosure audit for the public release candidate.

The audit deliberately keeps protected signatures in memory. Reports contain
only rule identifiers, examined-file counts, and pass/fail status.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.matheuristics.psp_instance import PSPInstance, load_instance


PRIVATE_REPORT = ROOT / "analysis" / "private_release" / "r4_1_structural_audit.md"
PUBLIC_RULES = [
    "D_FULL_MATRIX",
    "D_CONTIGUOUS_19_PERIOD_BLOCK",
    "AD_JOINT_FULL_OR_BLOCK",
]


@dataclass(frozen=True)
class StructuralAuditResult:
    """Outcome of a structural disclosure audit."""

    files_examined: int
    status: str
    failed_rule: str | None = None
    failed_file: str | None = None


def load_private_real_order_book() -> PSPInstance:
    """Load the private real order-book instance."""
    return load_instance(ROOT / "experiments" / "GAMSPy" / "S" / "REAL_1.py")


def public_instance_paths(public_root: Path) -> list[Path]:
    """Return public instance files from a release distribution root."""
    paths = sorted((public_root / "instances" / "gamspy_py").glob("*/*.py"))
    if len(paths) != 60:
        raise RuntimeError(f"Expected 60 public instance scripts, found {len(paths)}")
    return paths


def _same_d_block(candidate: np.ndarray, protected: np.ndarray) -> bool:
    """Return whether candidate contains the protected D matrix as a full block."""
    if candidate.shape[0] != protected.shape[0] or candidate.shape[1] < protected.shape[1]:
        return False
    width = protected.shape[1]
    for start in range(candidate.shape[1] - width + 1):
        if np.array_equal(candidate[:, start : start + width], protected):
            return True
    return False


def check_instance_against_private_signature(inst: PSPInstance, real: PSPInstance) -> str | None:
    """Return a failed rule identifier, or ``None`` when the instance passes."""
    if inst.D.shape == real.D.shape and np.array_equal(inst.D, real.D):
        return "D_FULL_MATRIX"
    if _same_d_block(inst.D, real.D):
        return "D_CONTIGUOUS_19_PERIOD_BLOCK"
    if np.array_equal(inst.A, real.A) and (
        (inst.D.shape == real.D.shape and np.array_equal(inst.D, real.D))
        or _same_d_block(inst.D, real.D)
    ):
        return "AD_JOINT_FULL_OR_BLOCK"
    return None


def run_structural_audit(public_root: Path) -> StructuralAuditResult:
    """Audit all public instances in a release distribution root."""
    real = load_private_real_order_book()
    paths = public_instance_paths(public_root)
    for path in paths:
        inst = load_instance(path)
        failed = check_instance_against_private_signature(inst, real)
        if failed:
            return StructuralAuditResult(
                files_examined=len(paths),
                status="failed",
                failed_rule=failed,
                failed_file=path.relative_to(public_root).as_posix(),
            )
    return StructuralAuditResult(files_examined=len(paths), status="passed")


def write_private_report(result: StructuralAuditResult) -> None:
    """Write the private structural-audit report without signatures."""
    PRIVATE_REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# R4.1 Structural Disclosure Audit",
        "",
        "Protected signatures were built in memory from the private real order book.",
        "No signature values, hashes, product labels, demand records, or reverse map are written here.",
        "",
        f"Files examined: {result.files_examined}",
        f"Status: {result.status}",
        "",
        "| Rule | Status |",
        "|---|---|",
    ]
    for rule in PUBLIC_RULES:
        status = "failed" if result.failed_rule == rule else ("passed" if result.status == "passed" else "not reached")
        lines.append(f"| {rule} | {status} |")
    if result.failed_rule:
        lines.extend(["", f"Failed rule: {result.failed_rule}", f"Failed file: {result.failed_file}"])
    PRIVATE_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def public_summary(result: StructuralAuditResult) -> str:
    """Return a public-safe structural-audit summary."""
    rows = "\n".join(
        f"| {rule} | {'passed' if result.status == 'passed' else 'failed'} |"
        for rule in PUBLIC_RULES
    )
    return (
        "# Structural Disclosure Audit Summary\n\n"
        f"Files examined: {result.files_examined}\n\n"
        "| Rule | Status |\n"
        "|---|---|\n"
        f"{rows}\n"
    )


def main(argv: list[str] | None = None) -> int:
    """Run the structural audit against a release distribution."""
    argv = argv or sys.argv[1:]
    public_root = Path(argv[0]) if argv else ROOT / "release" / "dist"
    result = run_structural_audit(public_root)
    write_private_report(result)
    print(f"structural_audit_status={result.status} files_examined={result.files_examined}")
    if result.status != "passed":
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
