"""Private structural disclosure audit for the public release candidate.

The audit deliberately keeps protected signatures in memory. Reports contain
only rule identifiers, examined-representation counts, and pass/fail status.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

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

    representations_examined: int
    status: str
    rule_status: dict[str, str]
    python_json_equivalence: str
    failed_rules: list[str] = field(default_factory=list)
    failed_files: list[str] = field(default_factory=list)

    @property
    def files_examined(self) -> int:
        """Backward-compatible alias for examined representations."""
        return self.representations_examined


def load_private_real_order_book() -> PSPInstance:
    """Load the private real order-book instance."""
    return load_instance(ROOT / "experiments" / "GAMSPy" / "S" / "REAL_1.py")


def public_instance_pairs(public_root: Path) -> list[tuple[Path, Path]]:
    """Return paired public Python and JSON instance files."""
    py_paths = sorted((public_root / "instances" / "gamspy_py").glob("*/*.py"))
    json_paths = sorted((public_root / "instances" / "json").glob("*/*.json"))
    if len(py_paths) != 60 or len(json_paths) != 60:
        raise RuntimeError(f"Expected 60 Python and 60 JSON public instances, found {len(py_paths)} and {len(json_paths)}")
    json_by_key = {(path.parent.name, path.stem): path for path in json_paths}
    pairs: list[tuple[Path, Path]] = []
    for py_path in py_paths:
        key = (py_path.parent.name, py_path.stem)
        if key not in json_by_key:
            raise RuntimeError(f"Missing JSON representation for {py_path.relative_to(public_root).as_posix()}")
        pairs.append((py_path, json_by_key[key]))
    return pairs


def load_json_instance(path: Path) -> PSPInstance:
    """Load a PSP instance from the public JSON representation."""
    data = json.loads(path.read_text(encoding="utf-8"))
    products = list(data["products"])
    product_index = {product: index for index, product in enumerate(products)}
    inst = PSPInstance(
        name=str(data["name"]),
        dataset=str(data["dataset"]),
        T=int(data["T"]),
        J=int(data["J"]),
        I=int(data["I"]),
        products=products,
        A=np.zeros((int(data["I"]), int(data["J"])), dtype=np.float64),
        D=np.zeros((int(data["I"]), int(data["T"])), dtype=np.float64),
    )
    for record in data["A_records"]:
        inst.A[product_index[record["product"]], int(record["process"]) - 1] = float(record["value"])
    for record in data["D_records"]:
        inst.D[product_index[record["product"]], int(record["period"]) - 1] = float(record["value"])
    return inst


def assert_equivalent(py_inst: PSPInstance, json_inst: PSPInstance, rel_py: str, rel_json: str) -> None:
    """Assert that Python and JSON representations carry the same instance."""
    attrs = ("name", "dataset", "T", "J", "I", "products")
    for attr in attrs:
        if getattr(py_inst, attr) != getattr(json_inst, attr):
            raise RuntimeError(f"Python/JSON mismatch for {attr}: {rel_py} vs {rel_json}")
    if not np.array_equal(py_inst.A, json_inst.A):
        raise RuntimeError(f"Python/JSON A matrix mismatch: {rel_py} vs {rel_json}")
    if not np.array_equal(py_inst.D, json_inst.D):
        raise RuntimeError(f"Python/JSON D matrix mismatch: {rel_py} vs {rel_json}")


def _row_multiset(matrix: np.ndarray) -> tuple[tuple[float, ...], ...]:
    """Return an order-invariant multiset representation of matrix rows."""
    return tuple(sorted(tuple(float(value) for value in row) for row in matrix))


def _pair_multiset(a_matrix: np.ndarray, d_matrix: np.ndarray) -> tuple[tuple[tuple[float, ...], tuple[float, ...]], ...]:
    """Return an order-invariant multiset of paired A and D rows."""
    return tuple(
        sorted(
            (tuple(float(value) for value in a_row), tuple(float(value) for value in d_row))
            for a_row, d_row in zip(a_matrix, d_matrix)
        )
    )


def _same_d_full(candidate: np.ndarray, protected: np.ndarray) -> bool:
    """Return whether the candidate has the protected D matrix, ignoring row order."""
    return candidate.shape == protected.shape and _row_multiset(candidate) == _row_multiset(protected)


def _same_d_block(candidate: np.ndarray, protected: np.ndarray) -> bool:
    """Return whether candidate contains the protected D matrix as a contiguous block."""
    if candidate.shape[0] != protected.shape[0] or candidate.shape[1] < protected.shape[1]:
        return False
    width = protected.shape[1]
    protected_rows = _row_multiset(protected)
    for start in range(candidate.shape[1] - width + 1):
        if _row_multiset(candidate[:, start : start + width]) == protected_rows:
            return True
    return False


def _same_ad_block(candidate: PSPInstance, protected: PSPInstance) -> bool:
    """Return whether candidate contains protected paired A and D rows."""
    if candidate.I != protected.I or candidate.J != protected.J or candidate.T < protected.T:
        return False
    width = protected.T
    protected_pairs = _pair_multiset(protected.A, protected.D)
    for start in range(candidate.T - width + 1):
        if _pair_multiset(candidate.A, candidate.D[:, start : start + width]) == protected_pairs:
            return True
    return False


def check_instance_against_private_signature(inst: PSPInstance, real: PSPInstance) -> list[str]:
    """Return all failed structural-disclosure rules for one instance."""
    failed: list[str] = []
    if _same_d_full(inst.D, real.D):
        failed.append("D_FULL_MATRIX")
    if _same_d_block(inst.D, real.D):
        failed.append("D_CONTIGUOUS_19_PERIOD_BLOCK")
    if _same_ad_block(inst, real):
        failed.append("AD_JOINT_FULL_OR_BLOCK")
    return failed


def run_structural_audit(public_root: Path) -> StructuralAuditResult:
    """Audit all public instance representations in a release distribution root."""
    real = load_private_real_order_book()
    pairs = public_instance_pairs(public_root)
    failed_rules: set[str] = set()
    failed_files: list[str] = []
    equivalence = "passed"
    for py_path, json_path in pairs:
        py_inst = load_instance(py_path)
        json_inst = load_json_instance(json_path)
        rel_py = py_path.relative_to(public_root).as_posix()
        rel_json = json_path.relative_to(public_root).as_posix()
        try:
            assert_equivalent(py_inst, json_inst, rel_py, rel_json)
        except RuntimeError:
            equivalence = "failed"
            raise
        for rel_name, inst in [(rel_py, py_inst), (rel_json, json_inst)]:
            failures = check_instance_against_private_signature(inst, real)
            if failures:
                failed_rules.update(failures)
                failed_files.append(rel_name)
    rule_status = {rule: ("failed" if rule in failed_rules else "passed") for rule in PUBLIC_RULES}
    status = "failed" if failed_rules else "passed"
    return StructuralAuditResult(
        representations_examined=len(pairs) * 2,
        status=status,
        rule_status=rule_status,
        python_json_equivalence=equivalence,
        failed_rules=sorted(failed_rules),
        failed_files=failed_files,
    )


def write_private_report(result: StructuralAuditResult) -> None:
    """Write the private structural-audit report without signatures."""
    PRIVATE_REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# R4.1 Structural Disclosure Audit",
        "",
        "Protected signatures were built in memory from the private real order book.",
        "No signature values, hashes, product labels, demand records, or reverse map are written here.",
        "",
        f"Representations examined: {result.representations_examined}",
        f"Python/JSON equivalence: {result.python_json_equivalence}",
        f"Status: {result.status}",
        "",
        "| Rule | Status |",
        "|---|---|",
    ]
    for rule in PUBLIC_RULES:
        lines.append(f"| {rule} | {result.rule_status[rule]} |")
    if result.failed_rules:
        lines.extend(["", f"Failed rules: {', '.join(result.failed_rules)}"])
        lines.append(f"Failed representations: {len(result.failed_files)}")
    PRIVATE_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def public_summary(result: StructuralAuditResult) -> str:
    """Return a public-safe structural-audit summary."""
    rows = "\n".join(f"| {rule} | {result.rule_status[rule]} |" for rule in PUBLIC_RULES)
    return (
        "# Structural Disclosure Audit Summary\n\n"
        f"Representations examined: {result.representations_examined}\n"
        f"Python/JSON equivalence: {result.python_json_equivalence}\n\n"
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
    print(f"structural_audit_status={result.status} representations_examined={result.representations_examined}")
    if result.status != "passed":
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
