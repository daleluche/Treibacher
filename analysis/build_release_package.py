"""Build the validated public release candidate from coded artifacts."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis import code_identifiers
from analysis.structural_disclosure_audit import public_summary, run_structural_audit, write_private_report
from analysis.release_scope import (
    canonicalize_public_text,
    has_absolute_path,
    is_private_instance_label,
    is_private_path,
)
from experiments.matheuristics.psp_instance import load_instance


RELEASE = ROOT / "release"
DIST = RELEASE / "dist"
ZIP_PATH = RELEASE / "psp_electrofused_benchmark_v1.zip"
SPEC = ROOT / "analysis" / "release_spec"
EXPECTED_INVENTORY = SPEC / "expected_inventory.txt"
PUBLIC_OUTPUTS = SPEC / "public_analysis_outputs.txt"
README_TEMPLATE = SPEC / "README.template.md"
DATASETS = ["S", "2X", "3X", "4X", "5X", "8X", "10X"]
TEXT_SUFFIXES = {".py", ".json", ".csv", ".md", ".txt", ".tex", ".bib", ".yml", ".yaml", ".sha256"}
PRIVATE_PATTERNS = [
    "EK8",
    "Treibacher",
    "add_real_order_book.py",
    "product_code_map.csv",
    "analysis/private_release",
    "analysis/code_identifiers.py",
    "verify_manuscript_numbers.py",
    "rebuild_s1.py",
    "REAL_1.py",
    "results_production/real",
    "experiments/GAMSPy/Real",
    "D:\\GitHub\\Treibacher",
    "D:/GitHub/Treibacher",
    "C:\\Users\\betoD",
    "C:/Users/betoD",
]


def reset_dist() -> None:
    """Create a clean release distribution directory."""
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)


def rel(path: Path) -> Path:
    """Return a repository-relative path."""
    return path.resolve().relative_to(ROOT)


def copy_file(src: Path, dst: Path) -> None:
    """Copy one file, creating parent directories."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def write_text(path: Path, text: str) -> None:
    """Write UTF-8 text, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def coded_path(src: Path) -> Path:
    """Return the staged coded copy of a repository path."""
    return code_identifiers.STAGING / rel(src)


def ensure_coded_staging() -> None:
    """Regenerate coded staging artifacts and private invariance report."""
    code_identifiers.main()


def public_analysis_outputs() -> list[str]:
    """Read the allowlist of public analysis outputs."""
    outputs: list[str] = []
    for line in PUBLIC_OUTPUTS.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        outputs.append(clean)
    return outputs


def write_open_instance_files() -> None:
    """Write coded instance scripts and open long-format instance files."""
    meta_rows: list[dict] = []
    a_rows: list[dict] = []
    d_rows: list[dict] = []
    for dataset in DATASETS:
        source_paths = sorted((ROOT / "experiments" / "GAMSPy" / dataset).glob("*.py"))
        for source in source_paths:
            if source.name == "REAL_1.py":
                continue
            staged = coded_path(source)
            if not staged.exists():
                raise FileNotFoundError(f"Missing coded staged instance: {staged}")
            dst = DIST / "instances" / "gamspy_py" / dataset / source.name
            copy_file(staged, dst)
            inst = load_instance(staged)
            json_data = {
                "name": inst.name,
                "dataset": dataset,
                "T": inst.T,
                "J": inst.J,
                "I": inst.I,
                "products": inst.products,
                "A_records": [
                    {"product": inst.products[i], "process": j + 1, "value": float(inst.A[i, j])}
                    for i in range(inst.I)
                    for j in range(inst.J)
                    if float(inst.A[i, j]) != 0.0
                ],
                "D_records": [
                    {"product": inst.products[i], "period": t + 1, "value": float(inst.D[i, t])}
                    for i in range(inst.I)
                    for t in range(inst.T)
                    if float(inst.D[i, t]) != 0.0
                ],
            }
            write_text(
                DIST / "instances" / "json" / dataset / f"{inst.name}.json",
                json.dumps(json_data, ensure_ascii=False, indent=2),
            )
            meta_rows.append(
                {
                    "dataset": dataset,
                    "instance": inst.name,
                    "T": inst.T,
                    "J": inst.J,
                    "I": inst.I,
                    "binary_variables": inst.J * inst.T,
                    "continuous_variables": 2 * inst.I * inst.T + 1,
                    "source_py": f"instances/gamspy_py/{dataset}/{source.name}",
                    "source_json": f"instances/json/{dataset}/{inst.name}.json",
                }
            )
            for rec in json_data["A_records"]:
                a_rows.append({"dataset": dataset, "instance": inst.name, **rec})
            for rec in json_data["D_records"]:
                d_rows.append({"dataset": dataset, "instance": inst.name, **rec})

    pd.DataFrame(meta_rows).to_csv(DIST / "instances" / "instance_metadata.csv", index=False)
    pd.DataFrame(a_rows).to_csv(DIST / "instances" / "production_matrix_long.csv", index=False)
    pd.DataFrame(d_rows).to_csv(DIST / "instances" / "demand_long.csv", index=False)


def copy_public_analysis_outputs() -> None:
    """Copy only allowlisted coded analysis outputs."""
    for relative in public_analysis_outputs():
        src = ROOT / "analysis" / "output" / relative
        staged = coded_path(src)
        if not src.exists():
            raise FileNotFoundError(f"Missing analysis output: {src}")
        if not staged.exists():
            raise FileNotFoundError(f"Missing coded staged analysis output: {staged}")
        dst = DIST / "analysis_output" / relative
        if staged.suffix.lower() == ".csv":
            frame = pd.read_csv(staged)
            frame = drop_private_rows(frame)
            dst.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(dst, index=False)
        else:
            copy_file(staged, dst)


def drop_private_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Drop rows that refer to excluded private real-order-book artifacts."""
    if frame.empty:
        return frame
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


def copy_public_results() -> None:
    """Copy coded result JSONs, trajectories, and window logs by allowlist."""
    patterns = [
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
        "experiments/matheuristics/**/window_logs/*.csv",
        "experiments/matheuristics/**/window_logs/*.parquet",
    ]
    for pattern in patterns:
        for src in sorted(ROOT.glob(pattern)):
            if "results_production\\real" in str(src) or "results_production/real" in str(src):
                continue
            if src.name.startswith("REAL_1"):
                continue
            staged = coded_path(src)
            if staged.exists():
                copy_file(staged, DIST / "results" / rel(src))


def copy_public_code() -> None:
    """Copy public reproduction code and add package-local entry points."""
    code_files = [
        "experiments/matheuristics/rf_fo_psp.py",
        "experiments/matheuristics/psp_instance.py",
        "experiments/GRASP/grasp_ils_psp.py",
        "analysis/build_master_dataset.py",
        "analysis/compute_gaps.py",
        "analysis/ils_equal_budget.py",
        "analysis/gamma_effect.py",
        "analysis/gamma_tradeoff.py",
        "analysis/sprint3_report.py",
        "analysis/make_paper_tables.py",
        "analysis/families.py",
    ]
    for relative in code_files:
        copy_file(ROOT / relative, DIST / "code" / relative)
    sanitize_public_code_copies()
    write_text(DIST / "code" / "requirements-analysis.txt", (ROOT / "analysis" / "requirements.txt").read_text(encoding="utf-8"))
    write_text(DIST / "code" / "reproduce_release.py", REPRODUCE_RELEASE)
    write_text(DIST / "code" / "verify_release.py", VERIFY_RELEASE)


def sanitize_public_code_copies() -> None:
    """Remove private real-order-book references from generated code copies."""
    replacements = {
        "REAL_1.py": "PRIVATE_REAL_ORDER_BOOK_EXCLUDED",
        "REAL_1": "PRIVATE_REAL_ORDER_BOOK",
        "Ale_1.py": "LEGACY_SCOPE_EXCLUDED.py",
        "Ale_1": "LEGACY_SCOPE_EXCLUDED",
        "Treibacher": "PSP",
        "results_production/real": "private_results_excluded",
        "results_production\\real": "private_results_excluded",
        "experiments/GAMSPy/Real": "private_instances_excluded",
        "experiments\\GAMSPy\\Real": "private_instances_excluded",
        "anonymization": "identifier coding",
        "anonymized": "coded",
        "Anonymization": "Identifier coding",
    }
    for path in (DIST / "code").rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        new_text = text
        for old, new in replacements.items():
            new_text = new_text.replace(old, new)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8", newline="\n")


def write_bks_counterfactual() -> None:
    """Write the counterfactual BKS table excluding MIP@10800 candidates."""
    master = pd.read_csv(ROOT / "analysis" / "output" / "master_instances.csv")
    candidates = master[master["Z_best"].notna()].copy()
    candidates = candidates[
        ~candidates["method"].isin(["GRASP_v1", "ILS_v1", "ILS_v2_pr", "MAT_mip_10800s"])
    ]
    rows = candidates.loc[candidates.groupby(["dataset", "instance"])["Z_best"].idxmin()]
    rows = rows[["dataset", "instance", "method", "Z_best"]].rename(
        columns={"method": "counterfactual_bks_method", "Z_best": "counterfactual_BKS"}
    )
    rows.to_csv(ROOT / "analysis" / "output" / "bks_counterfactual_without_mip10800.csv", index=False)


def write_release_metadata() -> None:
    """Write release README, manifest, license, and checksums."""
    readme = README_TEMPLATE.read_text(encoding="utf-8")
    write_text(DIST / "README.md", readme)
    license_text = (
        "# License\n\n"
        "Data files in this validated release candidate are prepared for CC BY 4.0.\n"
        "Code files are prepared for MIT licensing. Final license and DOI metadata\n"
        "will be filled at deposit time.\n"
    )
    write_text(DIST / "LICENSE.md", license_text)
    copy_file(EXPECTED_INVENTORY, DIST / "MANIFEST.expected_inventory.txt")
    copy_file(PUBLIC_OUTPUTS, DIST / "MANIFEST.public_analysis_outputs.txt")
    write_checksums()


def run_private_structural_audit() -> None:
    """Run the private structural audit and write the public-safe summary."""
    result = run_structural_audit(DIST)
    write_private_report(result)
    if result.status != "passed":
        raise RuntimeError(f"Structural disclosure audit failed: {result.failed_rule}")
    write_text(DIST / "STRUCTURAL_AUDIT.md", public_summary(result))


def iter_dist_files() -> list[Path]:
    """Return files in the distribution tree."""
    return sorted(path for path in DIST.rglob("*") if path.is_file())


def write_checksums() -> None:
    """Write a content-hash manifest for reproducibility checks."""
    rows = []
    checksum_path = DIST / "checksums.sha256"
    for path in iter_dist_files():
        if path == checksum_path:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append((digest, path.relative_to(DIST).as_posix()))
    with checksum_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=" ")
        writer.writerows(rows)


def current_inventory() -> list[str]:
    """Return the actual distribution inventory."""
    return sorted(path.relative_to(DIST).as_posix() for path in iter_dist_files())


def verify_inventory(refresh: bool = False) -> None:
    """Compare the distribution inventory with the versioned specification."""
    inventory = current_inventory()
    if refresh:
        write_text(EXPECTED_INVENTORY, "\n".join(inventory) + "\n")
        return
    expected = [line.strip() for line in EXPECTED_INVENTORY.read_text(encoding="utf-8").splitlines() if line.strip()]
    if inventory != expected:
        missing = sorted(set(expected) - set(inventory))
        extra = sorted(set(inventory) - set(expected))
        raise RuntimeError(f"Inventory mismatch. Missing={missing[:10]} Extra={extra[:10]}")


def scan_dist_content() -> None:
    """Fail if public artifacts contain private identifiers or local paths."""
    offenders: list[str] = []
    for path in iter_dist_files():
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        normalized = text.replace("\\\\", "\\")
        for candidate in {text, normalized, text.lower(), normalized.lower()}:
            for pattern in PRIVATE_PATTERNS:
                if pattern in candidate or pattern.lower() in candidate:
                    offenders.append(f"{path.relative_to(DIST).as_posix()}: {pattern}")
            if is_private_instance_label(candidate):
                offenders.append(f"{path.relative_to(DIST).as_posix()}: Ale_1 token")
        if path.suffix.lower() == ".json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = None
            if data is not None:
                for json_path, value in iter_json_strings(data):
                    if has_absolute_path(value) or is_private_path(value) or is_private_instance_label(value):
                        offenders.append(f"{path.relative_to(DIST).as_posix()}:{json_path}: private string")
    for path in iter_dist_files():
        rel_name = path.relative_to(DIST).as_posix()
        for pattern in PRIVATE_PATTERNS:
            if pattern.replace("\\", "/").lower() in rel_name.lower():
                offenders.append(f"{rel_name}: path")
    if offenders:
        raise RuntimeError("Private content found in release candidate:\n" + "\n".join(offenders[:50]))


def iter_json_strings(value: object, prefix: str = "$") -> list[tuple[str, str]]:
    """Return JSON string values with simple dotted paths."""
    rows: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            rows.extend(iter_json_strings(item, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(iter_json_strings(item, f"{prefix}[{index}]"))
    elif isinstance(value, str):
        rows.append((prefix, value))
    return rows


def create_zip() -> None:
    """Create a deterministic ZIP archive from the distribution tree."""
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in iter_dist_files():
            archive_name = path.relative_to(DIST).as_posix()
            info = zipfile.ZipInfo(archive_name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def self_test_zip() -> None:
    """Unpack the ZIP in an empty temporary directory and run public verifiers."""
    with tempfile.TemporaryDirectory(prefix="psp_release_check_") as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(ZIP_PATH) as zf:
            zf.extractall(tmp_path)
        subprocess.run([sys.executable, "code/reproduce_release.py"], cwd=tmp_path, check=True)
        subprocess.run([sys.executable, "code/verify_release.py"], cwd=tmp_path, check=True)


def main(argv: list[str] | None = None) -> int:
    """Build and validate the release candidate."""
    argv = argv or sys.argv[1:]
    refresh_inventory = "--refresh-inventory" in argv
    write_bks_counterfactual()
    ensure_coded_staging()
    reset_dist()
    write_open_instance_files()
    copy_public_analysis_outputs()
    copy_public_results()
    copy_public_code()
    run_private_structural_audit()
    write_release_metadata()
    if refresh_inventory:
        verify_inventory(refresh=True)
        write_release_metadata()
    verify_inventory(refresh=False)
    scan_dist_content()
    create_zip()
    self_test_zip()
    print(f"Release candidate written to {DIST}")
    print(f"ZIP written to {ZIP_PATH}")
    print(f"Files: {len(current_inventory())}")
    return 0


REPRODUCE_RELEASE = r'''"""Reproduce public release tables from packaged artifacts."""
from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis_output"
REPRO = ROOT / "reproduced_tables"


def main() -> int:
    """Regenerate compact public tables from release CSV artifacts."""
    if REPRO.exists():
        shutil.rmtree(REPRO)
    REPRO.mkdir()
    comparison = pd.read_csv(OUT / "comparison_by_dataset.csv")
    comparison.to_csv(REPRO / "comparison_by_dataset.csv", index=False)
    gamma = pd.read_csv(OUT / "gamma_effect_by_set.csv")
    gamma.to_csv(REPRO / "gamma_effect_by_set.csv", index=False)
    stats = pd.read_csv(OUT / "sprint3_statistical_tests.csv")
    stats.to_csv(REPRO / "sprint3_statistical_tests.csv", index=False)
    q5 = pd.read_csv(OUT / "sprint3_q5_verdict.csv")
    q5.to_csv(REPRO / "sprint3_q5_verdict.csv", index=False)
    print("Reproduced public analysis tables.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


VERIFY_RELEASE = r'''"""Verify the public release candidate using package-local files only."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def verify_checksums() -> None:
    """Validate SHA-256 content hashes."""
    for line in (ROOT / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split(" ", 1)
        observed = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        if observed != digest:
            raise AssertionError(f"Checksum mismatch for {name}")


def verify_inventory() -> None:
    """Validate the packaged inventory against the included manifest."""
    expected = [
        line.strip()
        for line in (ROOT / "MANIFEST.expected_inventory.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    actual = sorted(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file() and not path.relative_to(ROOT).as_posix().startswith("reproduced_tables/")
    )
    if actual != sorted(expected):
        raise AssertionError("Inventory mismatch inside release candidate.")


def verify_public_tables() -> None:
    """Check selected public table dimensions."""
    meta = pd.read_csv(ROOT / "instances" / "instance_metadata.csv")
    if len(meta) != 60:
        raise AssertionError(f"Expected 60 derived instances, found {len(meta)}")
    if set(meta["I"]) != {50} or set(meta["J"]) != {159}:
        raise AssertionError("Unexpected instance dimensions.")
    q5 = pd.read_csv(ROOT / "analysis_output" / "sprint3_q5_verdict.csv")
    if int(q5["mip10800_wins"].sum()) != 7:
        raise AssertionError("Q5 win count drifted.")


def main() -> int:
    """Run all public release checks."""
    verify_checksums()
    verify_inventory()
    verify_public_tables()
    print("Public release verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


if __name__ == "__main__":
    raise SystemExit(main())
