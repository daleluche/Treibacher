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
from analysis.release_scope import (
    PUBLIC_DATASETS,
    canonicalize_json_value,
    canonical_instance_name,
    canonicalize_public_text,
    canonicalize_relative_path,
    has_absolute_path,
    is_private_instance_label,
    is_private_path,
    is_public_record,
)


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
        writer = csv.DictWriter(fh, fieldnames=["private_label", "public_code"], lineterminator="\n")
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
        "experiments/GAMSPy/Real/results/Ale_*.json",
        "experiments/GAMSPy/Real/results_3horas/Ale_*.json",
        "experiments/GAMSPy/2X/results/*.json",
        "experiments/GAMSPy/2X/results_3horas/*.json",
        "experiments/GAMSPy/3X/results/*.json",
        "experiments/GAMSPy/3X/results_3horas/*.json",
        "experiments/GAMSPy/4X/results/*.json",
        "experiments/GAMSPy/4X/results_3horas/*.json",
        "experiments/GAMSPy/5X/results/*.json",
        "experiments/GAMSPy/5X/results_3horas/*.json",
        "experiments/GRASP/Real/results/Ale_*.json",
        "experiments/GRASP/2X/results/*.json",
        "experiments/GRASP/3X/results/*.json",
        "experiments/GRASP/4X/results/*.json",
        "experiments/GRASP/5X/results/*.json",
        "experiments/GRASP/results_ils_v2/*.json",
        "experiments/GRASP/results_ils/*.json",
        "experiments/GAMSPy/variant_gamma0/results_gamma0/*.json",
        "experiments/matheuristics/results_pilot/*.json",
        "experiments/matheuristics/results_tuning/*.json",
        "experiments/matheuristics/results_short_budget/*.json",
        "experiments/matheuristics/results_short_budget/*.csv",
        "experiments/matheuristics/results_short_budget_v2/*.json",
        "experiments/matheuristics/results_scale_8x10x/*.json",
        "experiments/matheuristics/results_scale_8x10x/*.csv",
        "experiments/matheuristics/results_scale_8x10x_v2/*.json",
        "experiments/matheuristics/results_scale_8x10x_v2/*.csv",
        "experiments/matheuristics/results_scale_8x10x_mip10800/*.json",
        "experiments/matheuristics/results_production/b600/*.json",
        "experiments/matheuristics/results_production/b600/*.csv",
        "experiments/matheuristics/results_production/a3600/*.json",
        "experiments/matheuristics/results_production/a3600/*.csv",
        "experiments/matheuristics/results_production/c_seeds/*.json",
        "experiments/matheuristics/results_production/c_seeds/*.csv",
        "experiments/matheuristics/results_production/c_seeds/window_logs/*.parquet",
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
            if "synthetic_tiny" in path.name or "Synthetic" in path.parts:
                continue
            if is_private_instance_label(path.name) or is_private_path(path):
                continue
            paths.append(path)
    return paths


def stage_text_file(src: Path, mapping: dict[str, str]) -> Path:
    """Write one text artifact with coded identifiers to staging."""
    rel_path = canonicalize_relative_path(src.relative_to(ROOT))
    dst = STAGING / rel_path
    if src.suffix.lower() == ".parquet":
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return dst
    if src.suffix.lower() == ".json":
        data = json.loads(src.read_text(encoding="utf-8"))
        coded = canonicalize_json_value(data)
        if isinstance(coded, dict) and not is_public_record(coded):
            raise ValueError(f"Private JSON record reached staging: {src.relative_to(ROOT)}")
        text = replace_labels(json.dumps(coded, ensure_ascii=False, indent=2), mapping)
    elif src.suffix.lower() == ".csv":
        frame = pd.read_csv(src)
        frame = filter_and_canonicalize_frame(frame)
        text = replace_labels(frame.to_csv(index=False, lineterminator="\n"), mapping)
    elif src.suffix.lower() in {".md", ".txt"}:
        text = replace_labels(canonicalize_public_text(src.read_text(encoding="utf-8")), mapping)
    else:
        text = replace_labels(canonicalize_public_text(src.read_text(encoding="utf-8")), mapping)
    if src in derived_instance_paths():
        text = rewrite_public_instance_objective(text)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and dst.read_text(encoding="utf-8") != text:
        raise RuntimeError(f"Name collision after public canonicalization: {dst.relative_to(STAGING)}")
    dst.write_text(text, encoding="utf-8", newline="\n")
    return dst


def rewrite_public_instance_objective(text: str) -> str:
    """Clarify the weighted objective in public instance scripts."""
    old = "Modelo MIP: minimiza falta de producao ao longo de"
    new = "Modelo MIP: minimiza falta e 0.001 vezes o estoque excedente ao longo de"
    return text.replace(old, new)


def filter_and_canonicalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Filter private rows and canonicalize public string columns."""
    if frame.empty:
        return frame
    frame = frame.copy()
    if "instance" in frame.columns:
        frame["instance"] = frame["instance"].map(
            lambda value: canonical_instance_name(str(value)) if pd.notna(value) else value
        )
    for column in ["name", "run_id"]:
        if column in frame.columns:
            frame[column] = frame[column].map(
                lambda value: canonicalize_public_text(str(value)) if pd.notna(value) else value
            )
    if "dataset" in frame.columns:
        if "instance" in frame.columns:
            public_s = frame["instance"].astype(str).str.fullmatch(r"S_(?:[2-9]|10)")
            frame.loc[(frame["dataset"].astype(str) == "Real") & public_s, "dataset"] = "S"
        frame["dataset"] = frame["dataset"].map(
            lambda value: canonicalize_public_text(str(value)) if pd.notna(value) else value
        )
        if not is_analytic_dataset_schema(frame):
            frame = frame[frame["dataset"].astype(str).isin(PUBLIC_DATASETS)]
    keep = pd.Series(True, index=frame.index)
    for column in frame.columns:
        if column in {"dataset", "instance", "name", "run_id"}:
            keep &= ~frame[column].map(is_private_instance_label)
        if column in {"source_path", "window_log_path", "path", "file", "source_file", "bks_source"}:
            keep &= ~frame[column].map(is_private_path)
    out = frame.loc[keep].copy().reset_index(drop=True)
    for column in out.columns:
        if out[column].dtype == object:
            out[column] = out[column].map(
                lambda value: canonicalize_public_text(str(value)) if pd.notna(value) else value
            )
    return out


def is_analytic_dataset_schema(frame: pd.DataFrame) -> bool:
    """Return whether a table may contain non-instance aggregate dataset labels."""
    return bool({"scope", "analysis_role", "test_note", "comparison"}.intersection(frame.columns))


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
    staged_text = staged.read_text(encoding="utf-8")
    weighted_description = "minimiza falta e 0.001 vezes o estoque excedente"
    shortage_only_description = "minimiza falta de producao"
    if weighted_description not in staged_text:
        raise AssertionError(f"Missing weighted objective description in {staged}")
    if shortage_only_description in staged_text:
        raise AssertionError(f"Residual shortage-only objective description in {staged}")
    if "0.001*E" not in staged_text:
        raise AssertionError(f"Objective coefficient changed or missing in {staged}")
    if "EK8" in staged_text:
        raise AssertionError(f"Residual private product label in {staged}")
    if "ALCOA" in staged_text or "Treibacher" in staged_text:
        raise AssertionError(f"Residual private public-text marker in {staged}")
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
        original = canonicalize_json_value(original)
        coded = json.loads(staged.read_text(encoding="utf-8"))
        restored = normalize_result_json(coded, mapping)
        if restored != original:
            raise AssertionError(f"Decoded JSON differs from canonical original: {src}")
    elif staged.suffix.lower() == ".csv":
        original_text = filter_and_canonicalize_frame(pd.read_csv(src)).to_csv(index=False, lineterminator="\n")
        restored_text = restore_labels(staged.read_text(encoding="utf-8"), mapping)
        if restored_text.replace("\r\n", "\n") != original_text.replace("\r\n", "\n"):
            raise AssertionError(f"Decoded CSV differs from canonical original: {src}")
    elif staged.suffix.lower() == ".parquet":
        if src.read_bytes() != staged.read_bytes():
            raise AssertionError(f"Parquet bytes differ from original: {src}")
        return ValidationResult(src, staged, "result", "passed", "binary content invariant")
    else:
        restored = restore_labels(staged.read_text(encoding="utf-8"), mapping)
        original = canonicalize_public_text(src.read_text(encoding="utf-8"))
        if restored != original:
            raise AssertionError(f"Decoded text differs from original: {src}")
    if "EK8" in staged.read_text(encoding="utf-8"):
        raise AssertionError(f"Residual private product label in {staged}")
    if "ALCOA" in staged.read_text(encoding="utf-8"):
        raise AssertionError(f"Residual corporate model identifier in {staged}")
    if "Treibacher" in staged.read_text(encoding="utf-8"):
        raise AssertionError(f"Residual repository name in {staged}")
    if staged.suffix.lower() == ".json" and any(has_absolute_path(value) for value in iter_json_strings(staged)):
        raise AssertionError(f"Residual absolute path in {staged}")
    return ValidationResult(src, staged, "result", "passed", "decoded content invariant")


def iter_json_strings(path: Path) -> list[str]:
    """Return all string values in a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    values: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str):
            values.append(value)

    walk(data)
    return values


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
