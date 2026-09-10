"""Verify a public release candidate using package-local files only."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Iterable

import pandas as pd

from release_compare import compare_output_dirs, manifest_outputs

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".json", ".csv", ".md", ".txt", ".sha256"}
PUBLIC_DATASETS = {"S", "2X", "3X", "4X", "5X", "8X", "10X"}
EXPECTED_INSTANCE_COUNTS = {"S": 10, "2X": 10, "3X": 10, "4X": 10, "5X": 10, "8X": 5, "10X": 5}
FORBIDDEN_SCOPE_RE = r"(?<![A-Za-z0-9_])" + "Ale" + r"_1(?!\d)|REAL" + r"_1|synthetic_tiny|Synthetic"
AUXILIARY_OUTPUTS = {
    "gamma_effect_note.md",
    "ils_equal_budget_600_report.md",
    "ils_equal_budget_report.md",
    "sprint3_bks_changes_after_mip10800.csv",
    "sprint3_report.md",
}


def private_text_re() -> re.Pattern[str]:
    """Return the private-token scanner without embedding those tokens contiguously."""
    private_terms = [
        "E" + "K8",
        "Trei" + "bacher",
        "AL" + "COA",
        "REAL" + "_1",
        r"(?<![A-Za-z0-9_])" + "Ale" + r"_1(?!\d)",
        r"results_production[\\/]real",
        "add_real" + "_order_book",
        "product" + "_code_map",
        r"analysis[\\/]private_release",
    ]
    return re.compile("|".join(private_terms), re.IGNORECASE)


def local_path_re() -> re.Pattern[str]:
    """Return the local-path scanner without private lexical tokens."""
    path_terms = [
        r"(?<![A-Za-z])[A-Za-z]:[\\/]",
        r"(?:^|[\s\"'=,])\\\\[A-Za-z0-9_.-]+[\\/]",
        "file" + "://",
        "/" + "home" + "/",
        "/" + "Users" + "/",
        "/" + "workspace" + "/",
        "/" + "tmp" + "/",
    ]
    return re.compile("|".join(path_terms), re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-root", type=Path, default=ROOT / "reproduced_analysis")
    parser.add_argument("--reference-root", type=Path, default=ROOT / "analysis_output")
    parser.add_argument("--negative-test", action="store_true")
    return parser.parse_args()


def iter_files() -> list[Path]:
    """Return package files excluding generated reproduction work."""
    excluded = {"reproduced_analysis", ".reproduce_work", "__pycache__", ".venv", "venv"}
    return sorted(
        path for path in ROOT.rglob("*")
        if path.is_file() and not any(part in excluded for part in path.relative_to(ROOT).parts)
    )


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
    actual = sorted(path.relative_to(ROOT).as_posix() for path in iter_files())
    if actual != sorted(expected):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise AssertionError(f"Inventory mismatch. Missing={missing[:10]} Extra={extra[:10]}")


def scan_private_content() -> None:
    """Reject private labels and local paths in public text artifacts."""
    offenders: list[str] = []
    private_re = private_text_re()
    path_re = local_path_re()
    for path in iter_files():
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        normalized = text.replace("\\\\", "\\")
        if private_re.search(text) or private_re.search(normalized) or path_re.search(normalized):
            offenders.append(path.relative_to(ROOT).as_posix())
        if path.suffix.lower() == ".json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            for value in iter_json_strings(data):
                normalized_value = value.replace("\\\\", "\\")
                if private_re.search(normalized_value) or path_re.search(normalized_value):
                    offenders.append(path.relative_to(ROOT).as_posix())
                    break
    if offenders:
        raise AssertionError(f"Private content or absolute paths found: {offenders[:20]}")
    scan_parquet_content()


def scan_parquet_content() -> None:
    """Reject private tokens and invalid datasets in textual parquet columns."""
    private_re = private_text_re()
    path_re = local_path_re()
    offenders: list[str] = []
    for path in iter_files():
        if path.suffix.lower() != ".parquet":
            continue
        try:
            frame = pd.read_parquet(path)
        except Exception as exc:  # pragma: no cover - exercised by release validation
            raise AssertionError(f"Could not read parquet file {path.relative_to(ROOT).as_posix()}: {exc}") from exc
        validate_frame_scope(frame, path.relative_to(ROOT).as_posix(), offenders)
        for column in frame.select_dtypes(include=["object", "string", "category"]).columns:
            for value in frame[column].dropna().astype(str):
                normalized = value.replace("\\\\", "\\")
                if private_re.search(normalized) or path_re.search(normalized):
                    offenders.append(f"{path.relative_to(ROOT).as_posix()}:{column}")
                    break
    if offenders:
        raise AssertionError(f"Forbidden parquet content found: {offenders[:20]}")


def iter_json_strings(value: object) -> list[str]:
    """Return all string values from a decoded JSON object."""
    strings: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            strings.extend(iter_json_strings(item))
    elif isinstance(value, list):
        for item in value:
            strings.extend(iter_json_strings(item))
    elif isinstance(value, str):
        strings.append(value)
    return strings


def verify_public_scope() -> None:
    """Check instance families and canonical S labels."""
    meta = pd.read_csv(ROOT / "instances" / "instance_metadata.csv")
    counts = meta.groupby("dataset")["instance"].nunique().to_dict()
    if counts != EXPECTED_INSTANCE_COUNTS:
        raise AssertionError(f"Unexpected public instance counts: {counts}")
    if set(meta["I"]) != {50} or set(meta["J"]) != {159}:
        raise AssertionError("Unexpected instance dimensions.")
    expected_s = {f"S_{i}" for i in range(1, 11)}
    observed_s = set(meta.loc[meta["dataset"] == "S", "instance"])
    if observed_s != expected_s:
        raise AssertionError(f"S labels are not canonical: {sorted(observed_s)}")
    py_files = list((ROOT / "instances" / "gamspy_py").glob("*/*.py"))
    json_files = list((ROOT / "instances" / "json").glob("*/*.json"))
    if len(py_files) != 60 or len(json_files) != 60:
        raise AssertionError(f"Expected 60 Python and 60 JSON instance representations, found {len(py_files)} and {len(json_files)}")
    validate_public_scope_everywhere()


def validate_public_scope_everywhere() -> None:
    """Reject unauthorized datasets or instances in public CSV, JSON, and parquet artifacts."""
    offenders: list[str] = []
    for path in iter_files():
        rel = path.relative_to(ROOT).as_posix()
        if path.suffix.lower() == ".csv":
            validate_frame_scope(pd.read_csv(path), rel, offenders)
        elif path.suffix.lower() == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            validate_json_scope(data, rel, offenders)
        elif path.suffix.lower() == ".parquet":
            validate_frame_scope(pd.read_parquet(path), rel, offenders)
    if offenders:
        raise AssertionError(f"Unauthorized public-scope values found: {offenders[:20]}")


def validate_frame_scope(frame: pd.DataFrame, rel: str, offenders: list[str]) -> None:
    """Validate dataset and instance labels in one tabular artifact."""
    if "dataset" in frame.columns:
        invalid = sorted(set(frame["dataset"].dropna().astype(str)) - PUBLIC_DATASETS)
        allowed_analytic = {"scale", "scope", "budget", "method", "metric"}
        if invalid and not allowed_analytic.intersection(frame.columns):
            offenders.append(f"{rel}:dataset={invalid[:5]}")
        elif invalid:
            forbidden = [value for value in invalid if value in {"Synthetic", "Real"} or value.startswith("Ale_")]
            if forbidden:
                offenders.append(f"{rel}:dataset={forbidden[:5]}")
    for column in [col for col in frame.columns if col in {"instance", "name", "run_id"}]:
        values = frame[column].dropna().astype(str)
        bad = values[values.str.contains(FORBIDDEN_SCOPE_RE, regex=True)]
        if not bad.empty:
            offenders.append(f"{rel}:{column}={bad.iloc[0]}")


def validate_json_scope(value: object, rel: str, offenders: list[str]) -> None:
    """Validate dataset and instance labels in one decoded JSON artifact."""
    if isinstance(value, dict):
        if "dataset" in value and str(value["dataset"]) not in PUBLIC_DATASETS:
            offenders.append(f"{rel}:dataset={value['dataset']!r}")
        for key in ("instance", "name", "run_id"):
            if key in value and re.search(FORBIDDEN_SCOPE_RE, str(value[key])):
                offenders.append(f"{rel}:{key}={value[key]!r}")
        for item in value.values():
            validate_json_scope(item, rel, offenders)
    elif isinstance(value, list):
        for item in value:
            validate_json_scope(item, rel, offenders)


def verify_window_log_metadata() -> None:
    """Validate that JSON window-log metadata exactly matches staged files."""
    staged_logs = {
        path.relative_to(ROOT).as_posix()
        for path in iter_files()
        if "window_logs" in path.parts and path.suffix.lower() in {".csv", ".parquet"}
    }
    log_refs: dict[str, int] = {}
    included = missing = invalid = 0
    for path in iter_files():
        if path.suffix.lower() != ".json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict) or "window_log_path" not in data:
            continue
        rel = path.relative_to(ROOT).as_posix()
        flag = data.get("window_log_included")
        log_path = data.get("window_log_path")
        valid = isinstance(log_path, str) and log_path in staged_logs and not Path(log_path).is_absolute() and ".." not in Path(log_path).parts
        if flag is True:
            included += 1
            if not valid:
                invalid += 1
                raise AssertionError(f"{rel}: included window log does not resolve inside package: {log_path!r}")
            log_refs[log_path] = log_refs.get(log_path, 0) + 1
        elif flag is False:
            missing += 1
            if log_path is not None:
                invalid += 1
                raise AssertionError(f"{rel}: missing window log must use null path, found {log_path!r}")
        else:
            invalid += 1
            raise AssertionError(f"{rel}: window_log_included must be true or false")
    if invalid:
        raise AssertionError(f"Invalid window-log metadata count: {invalid}")
    unreferenced = sorted(staged_logs - set(log_refs))
    shared = {path: count for path, count in log_refs.items() if count != 1}
    if unreferenced or shared:
        raise AssertionError(f"Unexpected window-log reference cardinality. Unreferenced={unreferenced[:5]} shared={shared}")


def verify_raw_source_coverage() -> None:
    """Check that raw evidence required by public outputs is present."""
    required_dirs = [
        ROOT / "instances" / "gamspy_py",
        ROOT / "results" / "experiments" / "GAMSPy",
        ROOT / "results" / "experiments" / "GRASP" / "results_ils_v2",
        ROOT / "results" / "experiments" / "matheuristics",
    ]
    missing = [path.as_posix() for path in required_dirs if not path.exists()]
    if missing:
        raise AssertionError(f"Missing raw source directories: {missing}")
    if len(list((ROOT / "results" / "experiments" / "GAMSPy" / "variant_gamma0" / "results_gamma0").glob("*.json"))) != 40:
        raise AssertionError("Expected 40 gamma=0 result JSONs.")


def verify_sentinels(reference_root: Path) -> None:
    """Check public scientific sentinel counts."""
    q5 = pd.read_csv(reference_root / "sprint3_q5_verdict.csv")
    if int(q5["mip10800_wins"].sum()) != 7:
        raise AssertionError("Q5 total win count drifted.")
    by_family = dict(zip(q5["dataset"], q5["mip10800_wins"]))
    if by_family.get("8X") != 4 or by_family.get("10X") != 3:
        raise AssertionError(f"Q5 family win counts drifted: {by_family}")
    gamma = pd.read_csv(reference_root / "gamma_tradeoff_2x.csv")
    gamma_instances = gamma[~gamma["instance"].isin(["MEDIAN", "AGGREGATE"])]
    if int((gamma_instances["delta_shortage"] > 1e-9).sum()) != 7:
        raise AssertionError("2X gamma shortage-increase count drifted.")
    tradeoff_all = pd.read_csv(reference_root / "gamma_tradeoff_all.csv")
    subset = tradeoff_all[tradeoff_all["dataset"].isin(["2X", "3X", "4X", "5X"])]
    if int((subset["delta_shortage"] > 1e-9).sum()) != 31:
        raise AssertionError("Gamma descriptive direction count drifted.")
    bks = pd.read_csv(reference_root / "sprint3_bks_audit.csv")
    previous = pd.read_csv(reference_root / "bks_counterfactual_without_mip10800.csv")
    merged = bks.merge(previous, on=["dataset", "instance"], how="left")
    improvements = merged["counterfactual_BKS"].notna() & (merged["BKS"] < merged["counterfactual_BKS"] - 1e-9)
    if int(improvements.sum()) != 6:
        raise AssertionError("BKS improvement count drifted.")


def run_negative_test(args: argparse.Namespace) -> None:
    """Verify that deliberate comparison and scope defects are detected."""
    with tempfile.TemporaryDirectory(prefix="psp_negative_reference_") as tmp:
        mutated = Path(tmp) / "analysis_output"
        shutil.copytree(args.reference_root, mutated)
        target = mutated / "sprint3_q5_verdict.csv"
        frame = pd.read_csv(target)
        frame.loc[0, "mip10800_wins"] = int(frame.loc[0, "mip10800_wins"]) + 1
        frame.to_csv(target, index=False)
        try:
            compare_output_dirs(args.analysis_root, mutated, ROOT / "MANIFEST.public_analysis_outputs.txt")
        except AssertionError:
            print("Negative comparison test failed as expected.")
        else:
            raise AssertionError("Negative comparison test did not detect the injected cell drift.")
    with tempfile.TemporaryDirectory(prefix="psp_negative_scope_") as tmp:
        sandbox = Path(tmp)
        shutil.copytree(ROOT, sandbox / "pkg")
        bad = sandbox / "pkg" / "results" / "bad_synthetic.json"
        bad.write_text(json.dumps({"dataset": "Synthetic", "instance": "synthetic_tiny"}), encoding="utf-8")
        old_root = globals()["ROOT"]
        globals()["ROOT"] = sandbox / "pkg"
        try:
            try:
                scan_private_content()
                verify_public_scope()
            except AssertionError:
                print("Negative raw-dataset test failed as expected.")
            else:
                raise AssertionError("Negative raw-dataset test did not detect unauthorized dataset.")
            bad.unlink()
            target = globals()["ROOT"] / "analysis_output" / "master_instances.csv"
            frame = pd.read_csv(target)
            frame.loc[len(frame)] = {column: None for column in frame.columns}
            frame.loc[len(frame) - 1, "dataset"] = "UnknownSet"
            if "instance" in frame.columns:
                frame.loc[len(frame) - 1, "instance"] = "bad_instance"
            frame.to_csv(target, index=False)
            try:
                verify_public_scope()
            except AssertionError:
                print("Negative analytic-dataset test failed as expected.")
                return
            raise AssertionError("Negative analytic-dataset test did not detect unauthorized dataset.")
        finally:
            globals()["ROOT"] = old_root


def main() -> int:
    """Run all public release checks."""
    args = parse_args()
    verify_checksums()
    verify_inventory()
    scan_private_content()
    verify_public_scope()
    verify_raw_source_coverage()
    verify_window_log_metadata()
    expected_names = set(manifest_outputs(ROOT / "MANIFEST.public_analysis_outputs.txt"))
    observed_names = {path.relative_to(args.analysis_root).as_posix() for path in args.analysis_root.iterdir() if path.is_file()}
    if not expected_names.issubset(observed_names):
        raise AssertionError(f"Missing reproduced outputs: {sorted(expected_names - observed_names)}")
    unexpected = observed_names - expected_names - AUXILIARY_OUTPUTS
    if unexpected:
        raise AssertionError(f"Unexpected reproduced outputs: {sorted(unexpected)}")
    compare_output_dirs(args.analysis_root, args.reference_root, ROOT / "MANIFEST.public_analysis_outputs.txt")
    verify_sentinels(args.reference_root)
    if args.negative_test:
        run_negative_test(args)
    print("Public release verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
