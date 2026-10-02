"""Generate and run gamma=0 PSP variant scripts for IncT datasets."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VARIANT_DIR = Path(__file__).resolve().parent
SCRIPT_DIR = VARIANT_DIR / "scripts"
RESULTS_DIR = VARIANT_DIR / "results_gamma0"
DATASETS = ["2X", "3X", "4X", "5X"]
RESLIM = 10800


def source_instances() -> list[Path]:
    """Return the 40 original IncT GAMSPy source scripts."""
    paths: list[Path] = []
    for dataset in DATASETS:
        paths.extend(sorted((ROOT / "experiments" / "GAMSPy" / dataset).glob("*.py")))
    return paths


def write_wrapper(source_path: Path) -> Path:
    """Write a thin, resumable wrapper script for one gamma=0 solve."""
    rel_source = source_path.relative_to(ROOT).as_posix()
    target_dir = SCRIPT_DIR / source_path.parent.name
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{source_path.stem}_gamma0.py"
    body = f'''"""Gamma=0 variant wrapper for {source_path.parent.name}/{source_path.stem}."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.GAMSPy.variant_gamma0.solve_gamma0 import solve_instance


if __name__ == "__main__":
    solve_instance(ROOT / "{rel_source}", ROOT / "experiments/GAMSPy/variant_gamma0/results_gamma0")
'''
    target.write_text(body, encoding="utf-8")
    return target


def generate_scripts() -> list[Path]:
    """Generate all gamma=0 wrapper scripts."""
    scripts = [write_wrapper(path) for path in source_instances()]
    print(f"Generated {len(scripts)} gamma=0 wrapper scripts in {SCRIPT_DIR}")
    return scripts


def run_scripts(scripts: list[Path], reslim: int = RESLIM, threads: int = 0) -> None:
    """Run all wrapper scripts sequentially with resume semantics."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    total = len(scripts)
    for index, script in enumerate(scripts, start=1):
        instance = script.stem.replace("_gamma0", "")
        result_path = RESULTS_DIR / f"{instance}.json"
        if result_path.exists():
            print(f"[{index}/{total}] skip {instance}: result exists")
            continue
        print(f"[{index}/{total}] run {instance}")
        cmd = [
            sys.executable,
            str(VARIANT_DIR / "solve_gamma0.py"),
            "--instance",
            str((ROOT / "experiments" / "GAMSPy" / script.parent.name / f"{instance}.py").resolve()),
            "--output-dir",
            str(RESULTS_DIR.resolve()),
            "--reslim",
            str(int(reslim)),
            "--threads",
            str(int(threads)),
        ]
        subprocess.run(cmd, cwd=str(ROOT), check=True)


def main(argv: list[str] | None = None) -> int:
    """Generate scripts and optionally run the full gamma=0 experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Run the generated scripts sequentially.")
    parser.add_argument("--reslim", type=int, default=RESLIM, help="CPLEX time limit per instance.")
    parser.add_argument("--threads", type=int, default=0, help="CPLEX threads option; 0 lets CPLEX use all.")
    args = parser.parse_args(argv)
    scripts = generate_scripts()
    if args.run:
        run_scripts(scripts, args.reslim, args.threads)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
