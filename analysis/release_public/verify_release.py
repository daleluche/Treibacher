"""Verify a public release candidate using package-local files only."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

import pandas as pd

from release_compare import compare_output_dirs, manifest_outputs

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".json", ".csv", ".md", ".txt", ".sha256"}


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
    expected_counts = {"S": 10, "2X": 10, "3X": 10, "4X": 10, "5X": 10, "8X": 5, "10X": 5}
    counts = meta.groupby("dataset")["instance"].nunique().to_dict()
    if counts != expected_counts:
        raise AssertionError(f"Unexpected public instance counts: {counts}")
    if set(meta["I"]) != {50} or set(meta["J"]) != {159}:
        raise AssertionError("Unexpected instance dimensions.")
    expected_s = {f"S_{i}" for i in range(1, 11)}
    observed_s = set(meta.loc[meta["dataset"] == "S", "instance"])
    if observed_s != expected_s:
        raise AssertionError(f"S labels are not canonical: {sorted(observed_s)}")


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
    """Verify that output comparison fails after a deliberate reference-cell edit."""
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
            return
        raise AssertionError("Negative comparison test did not detect the injected cell drift.")


def main() -> int:
    """Run all public release checks."""
    args = parse_args()
    verify_checksums()
    verify_inventory()
    scan_private_content()
    verify_public_scope()
    verify_raw_source_coverage()
    expected_names = set(manifest_outputs(ROOT / "MANIFEST.public_analysis_outputs.txt"))
    observed_names = {path.relative_to(args.analysis_root).as_posix() for path in args.analysis_root.glob("*.csv")}
    if not expected_names.issubset(observed_names):
        raise AssertionError(f"Missing reproduced outputs: {sorted(expected_names - observed_names)}")
    compare_output_dirs(args.analysis_root, args.reference_root, ROOT / "MANIFEST.public_analysis_outputs.txt")
    verify_sentinels(args.reference_root)
    if args.negative_test:
        run_negative_test(args)
    print("Public release verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
