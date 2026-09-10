"""Create de-identified public artifact copies with coded product labels.

The original PSP artifacts contain product labels that are meaningful in the
private repository. This script never edits those artifacts in place. It writes
coded copies under ``release/staging`` and stores the reversible mapping under
``analysis/private_release`` for private audit only.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.matheuristics.psp_instance import load_instance


SALT = "treibacher-psp-private-release-coding-v1"
DATASETS = ["S", "2X", "3X", "4X", "5X", "8X", "10X"]
PRIVATE_DIR = ROOT / "analysis" / "private_release"
STAGING = ROOT / "release" / "staging"
REPORT = PRIVATE_DIR / "identifier_coding_invariance_report.md"


@dataclass(frozen=True)
class ValidationResult:
    """Summary of one file-level invariance validation."""

    source: Path
    staged: Path
    kind: str
    status: str
    detail: str


def stable_product_map(labels: list[str]) -> dict[str, str]:
    """Return a deterministic bijection from product labels to ``P01``--``P50``."""
    if len(labels) != 50:
        raise ValueError(f"Expected 50 product labels, found {len(labels)}")
    if len(set(labels)) != len(labels):
        raise ValueError("Product labels are not unique.")
    ranked = sorted(
        labels,
        key=lambda label: hashlib.sha256(
            (SALT + "\0" + unicodedata.normalize("NFC", label)).encode("utf-8")
        ).hexdigest(),
    )
    return {label: f"P{index:02d}" for index, label in enumerate(ranked, start=1)}


def load_labels() -> list[str]:
    """Load the private product labels from a representative instance."""
    inst = load_instance(ROOT / "experiments" / "GAMSPy" / "S" / "S_1.py")
    return list(inst.products)


def write_private_map(mapping: dict[str, str]) -> None:
    """Write the reversible private mapping."""
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    with (PRIVATE_DIR / "product_code_map.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["private_label", "public_code"])
        writer.writeheader()
        for label, code in sorted(mapping.items(), key=lambda item: item[1]):
            writer.writerow({"private_label": label, "public_code": code})


def replace_labels(text: str, mapping: dict[str, str]) -> str:
    """Replace private product labels by public codes using exact string matches."""
    coded = text
    for label in sorted(mapping, key=len, reverse=True):
        coded = coded.replace(label, mapping[label])
    return coded


def restore_labels(text: str, mapping: dict[str, str]) -> str:
    """Restore public codes to private product labels for invariance checks."""
    restored = text
    reverse = {code: label for label, code in mapping.items()}
    for code in sorted(reverse, key=len, reverse=True):
        restored = restored.replace(code, reverse[code])
    return restored


def reset_staging() -> None:
    """Create a clean staging directory."""
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)


def derived_instance_paths() -> list[Path]:
    """Return the 60 derived instance scripts eligible for public staging."""
    paths: list[Path] = []
    for dataset in DATASETS:
        for path in sorted((ROOT / "experiments" / "GAMSPy" / dataset).glob("*.py")):
            if path.name == "REAL_1.py":
                continue
            paths.append(path)
    if len(paths) != 60:
        raise RuntimeError(f"Expected 60 derived instance scripts, found {len(paths)}")
    return paths


def result_paths() -> list[Path]:
    """Return JSON/CSV/Markdown/parquet result artifacts eligible for staging."""
    patterns = [
        "analysis/output/*.csv",
        "experiments/GRASP/results_ils_v2/*.json",
        "experiments/GRASP/results_ils/*.json",
        "experiments/GAMSPy/variant_gamma0/results_gamma0/*.json",
        "experiments/matheuristics/results_pilot/*.json",
        "experiments/matheuristics/results_tuning/*.json",
        "experiments/matheuristics/results_short_budget/*.json",
        "experiments/matheuristics/results_short_budget_v2/*.json",
        "experiments/matheuristics/results_scale_8x10x/*.json",
        "experiments/matheuristics/results_scale_8x10x_v2/*.json",
        "experiments/matheuristics/results_scale_8x10x_mip10800/*.json",
        "experiments/matheuristics/results_production/b600/*.json",
        "experiments/matheuristics/results_production/a3600/*.json",
        "experiments/matheuristics/results_production/c_seeds/*.json",
        "experiments/matheuristics/results_production/s1/*.json",
    ]
    blocked = {
        ROOT / "experiments" / "matheuristics" / "results_production" / "real",
    }
    paths: list[Path] = []
    for pattern in patterns:
        for path in sorted(ROOT.glob(pattern)):
            if any(parent in path.parents for parent in blocked):
                continue
            if path.name == "real_instance_crosscheck.md":
                continue
            if path.stem == "REAL_1" or path.stem.startswith("REAL_1_"):
                continue
            paths.append(path)
    return paths


def stage_text_file(src: Path, mapping: dict[str, str]) -> Path:
    """Write one text artifact with coded identifiers to staging."""
    dst = STAGING / src.relative_to(ROOT)
    dst.parent.mkdir(parents=True, exist_ok=True)
    text = src.read_text(encoding="utf-8")
    dst.write_text(replace_labels(text, mapping), encoding="utf-8")
    return dst


def validate_instance(src: Path, staged: Path, mapping: dict[str, str]) -> ValidationResult:
    """Validate that a coded instance preserves all numeric data."""
    original = load_instance(src)
    coded = load_instance(staged)
    restored_products = [restore_labels(product, mapping) for product in coded.products]
    if restored_products != original.products:
        raise AssertionError(f"Product order changed in {src}")
    if (original.T, original.J, original.I) != (coded.T, coded.J, coded.I):
        raise AssertionError(f"Dimensions changed in {src}")
    if not (original.A == coded.A).all():
        raise AssertionError(f"A matrix changed in {src}")
    if not (original.D == coded.D).all():
        raise AssertionError(f"D matrix changed in {src}")
    if "EK8" in staged.read_text(encoding="utf-8"):
        raise AssertionError(f"Residual private product label in {staged}")
    return ValidationResult(src, staged, "instance", "passed", "dimensions, products, A, and D invariant")


def normalize_result_json(value: object, mapping: dict[str, str]) -> object:
    """Restore coded JSON string values for structural comparison."""
    if isinstance(value, dict):
        return {key: normalize_result_json(val, mapping) for key, val in value.items()}
    if isinstance(value, list):
        return [normalize_result_json(val, mapping) for val in value]
    if isinstance(value, str):
        return restore_labels(value, mapping)
    return value


def validate_result(src: Path, staged: Path, mapping: dict[str, str]) -> ValidationResult:
    """Validate that a coded result artifact decodes to the original content."""
    if staged.suffix.lower() == ".json":
        original = json.loads(src.read_text(encoding="utf-8"))
        coded = json.loads(staged.read_text(encoding="utf-8"))
        restored = normalize_result_json(coded, mapping)
        if restored != original:
            raise AssertionError(f"Decoded JSON differs from original: {src}")
    elif staged.suffix.lower() == ".csv":
        original = pd.read_csv(src)
        restored_text = restore_labels(staged.read_text(encoding="utf-8"), mapping)
        temp = PRIVATE_DIR / "_restored_check.csv"
        temp.write_text(restored_text, encoding="utf-8")
        restored = pd.read_csv(temp)
        temp.unlink()
        pd.testing.assert_frame_equal(original, restored, check_dtype=False)
    else:
        restored = restore_labels(staged.read_text(encoding="utf-8"), mapping)
        if restored != src.read_text(encoding="utf-8"):
            raise AssertionError(f"Decoded text differs from original: {src}")
    if "EK8" in staged.read_text(encoding="utf-8"):
        raise AssertionError(f"Residual private product label in {staged}")
    return ValidationResult(src, staged, "result", "passed", "decoded content invariant")


def write_report(results: list[ValidationResult], mapping: dict[str, str]) -> None:
    """Write a private invariance report."""
    lines = [
        "# Identifier Coding Invariance Report",
        "",
        f"R3 base SHA: {(ROOT / 'R3_BASE_SHA').read_text(encoding='utf-8').strip()}",
        f"Product mapping size: {len(mapping)}",
        f"Files validated: {len(results)}",
        "",
        "All validations compare decoded staged files with their private sources.",
        "",
        "| Kind | Status | Source | Staged | Detail |",
        "|---|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| {kind} | {status} | `{source}` | `{staged}` | {detail} |".format(
                kind=result.kind,
                status=result.status,
                source=result.source.relative_to(ROOT).as_posix(),
                staged=result.staged.relative_to(ROOT).as_posix(),
                detail=result.detail,
            )
        )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    """Generate staged coded artifacts and validate file-level invariance."""
    labels = load_labels()
    mapping = stable_product_map(labels)
    write_private_map(mapping)
    reset_staging()

    results: list[ValidationResult] = []
    for src in derived_instance_paths():
        staged = stage_text_file(src, mapping)
        results.append(validate_instance(src, staged, mapping))
    for src in result_paths():
        staged = stage_text_file(src, mapping)
        results.append(validate_result(src, staged, mapping))

    write_report(results, mapping)
    print(f"Mapped {len(mapping)} product labels.")
    print(f"Validated {len(results)} staged files.")
    print(f"Private map: {PRIVATE_DIR / 'product_code_map.csv'}")
    print(f"Report: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
