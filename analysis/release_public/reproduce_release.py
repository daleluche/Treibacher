"""Reproduce public release analysis outputs from packaged raw evidence."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from release_compare import compare_output_dirs

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "reproduced_analysis"
DEFAULT_WORK = ROOT / ".reproduce_work"
SCRIPT_ORDER = [
    ["analysis/build_master_dataset.py"],
    ["analysis/compute_gaps.py"],
    ["analysis/gamma_effect.py"],
    ["analysis/gamma_tradeoff.py"],
    ["analysis/ils_equal_budget.py", "--cutoff", "600"],
    ["analysis/sprint3_report.py"],
]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instances-root", type=Path, default=ROOT / "instances")
    parser.add_argument("--results-root", type=Path, default=ROOT / "results")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--reference-root", type=Path, default=None)
    parser.add_argument("--work-root", type=Path, default=DEFAULT_WORK)
    parser.add_argument("--keep-work", action="store_true")
    return parser.parse_args()


def copy_tree(src: Path, dst: Path) -> None:
    """Copy a tree if it exists."""
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True)


def prepare_work_tree(args: argparse.Namespace) -> Path:
    """Build a temporary repository-shaped tree from package-local raw evidence."""
    work = args.work_root
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    copy_tree(ROOT / "code" / "analysis", work / "analysis")
    copy_tree(ROOT / "code" / "experiments", work / "experiments")
    copy_tree(args.instances_root / "gamspy_py", work / "experiments" / "GAMSPy")
    raw_experiments = args.results_root / "experiments"
    copy_tree(raw_experiments, work / "experiments")
    mirror_public_s_cplex_results(work)
    (work / "analysis" / "output").mkdir(parents=True, exist_ok=True)
    return work


def mirror_public_s_cplex_results(work: Path) -> None:
    """Mirror public S CPLEX results into the legacy lookup folder inside the work tree."""
    source = work / "experiments" / "GAMSPy" / "S"
    legacy = work / "experiments" / "GAMSPy" / "Real"
    for folder in ["results", "results_3horas"]:
        if (source / folder).exists():
            copy_tree(source / folder, legacy / folder)
    grasp_source = work / "experiments" / "GRASP" / "S"
    grasp_legacy = work / "experiments" / "GRASP" / "Real"
    if (grasp_source / "results").exists():
        copy_tree(grasp_source / "results", grasp_legacy / "results")


def run_public_pipeline(work: Path) -> None:
    """Run analysis scripts in dependency order inside the compatibility tree."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(work)
    env["PSP_PUBLIC_RELEASE"] = "1"
    for index, command in enumerate(SCRIPT_ORDER):
        subprocess.run([sys.executable, *command], cwd=work, env=env, check=True)
        if index == 1:
            write_bks_counterfactual(work)


def write_bks_counterfactual(work: Path) -> None:
    """Write the counterfactual BKS table excluding MIP@10800 candidates."""
    import pandas as pd

    out = work / "analysis" / "output"
    master = pd.read_csv(out / "master_instances.csv")
    candidates = master[master["Z_best"].notna()].copy()
    candidates = candidates[
        ~candidates["method"].isin(["GRASP_v1", "ILS_v1", "ILS_v2_pr", "MAT_mip_10800s"])
    ]
    rows = candidates.loc[candidates.groupby(["dataset", "instance"])["Z_best"].idxmin()]
    rows = rows[["dataset", "instance", "method", "Z_best"]].rename(
        columns={"method": "counterfactual_bks_method", "Z_best": "counterfactual_BKS"}
    )
    rows.to_csv(out / "bks_counterfactual_without_mip10800.csv", index=False)


def publish_outputs(work: Path, output_root: Path) -> None:
    """Replace the public reproduced output directory with regenerated artifacts."""
    if output_root.exists():
        shutil.rmtree(output_root)
    shutil.copytree(work / "analysis" / "output", output_root)
    canonicalize_reproduced_paths(output_root)


def canonicalize_reproduced_paths(output_root: Path) -> None:
    """Rewrite compatibility-tree legacy source paths to public package paths."""
    replacements = {
        ("experiments/GAMSPy/" + "Real" + "/results/S_"): "experiments/GAMSPy/S/results/S_",
        ("experiments/GAMSPy/" + "Real" + "/results_3horas/S_"): "experiments/GAMSPy/S/results_3horas/S_",
        ("experiments/GRASP/" + "Real" + "/results/S_"): "experiments/GRASP/S/results/S_",
        ("experiments\\GAMSPy\\" + "Real" + "\\results\\S_"): "experiments\\GAMSPy\\S\\results\\S_",
        ("experiments\\GAMSPy\\" + "Real" + "\\results_3horas\\S_"): "experiments\\GAMSPy\\S\\results_3horas\\S_",
        ("experiments\\GRASP\\" + "Real" + "\\results\\S_"): "experiments\\GRASP\\S\\results\\S_",
    }
    for path in output_root.glob("*.csv"):
        text = path.read_text(encoding="utf-8")
        updated = text
        for old, new in replacements.items():
            updated = updated.replace(old, new)
        if updated != text:
            path.write_text(updated, encoding="utf-8", newline="\n")


def main() -> int:
    """Reproduce all public analysis outputs and optionally compare them with references."""
    args = parse_args()
    if not args.instances_root.exists():
        raise FileNotFoundError(f"Missing instances root: {args.instances_root}")
    if not args.results_root.exists():
        raise FileNotFoundError(f"Missing results root: {args.results_root}")
    work = prepare_work_tree(args)
    try:
        run_public_pipeline(work)
        publish_outputs(work, args.output_root)
        if args.reference_root is not None:
            compare_output_dirs(
                args.output_root,
                args.reference_root,
                ROOT / "MANIFEST.public_analysis_outputs.txt",
            )
    finally:
        if not args.keep_work and work.exists():
            shutil.rmtree(work)
    print(f"Reproduced public analysis outputs in {args.output_root}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
