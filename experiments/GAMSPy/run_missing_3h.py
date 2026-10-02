"""Run missing 3X GAMSPy instances with a three-hour CPLEX budget.

The generated instance scripts are treated as immutable inputs. This runner
loads each source file as text, patches the time limit and output directory in
memory, and executes the patched program in an isolated Python subprocess.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GAMSPY_DIR = ROOT / "experiments" / "GAMSPy"
SOURCE_DIR = GAMSPY_DIR / "3X"
REAL_OUTPUT_DIR = SOURCE_DIR / "results_3horas"
MISSING_INSTANCES = ("IncT3x_7", "IncT3x_8", "IncT3x_9")


def patch_source(source: str, budget_s: int, output_dir: Path) -> str:
    """Patch RESLIM and the output directory in a generated instance script."""
    patched, count = re.subn(
        r"RESLIM,\s*ITERLIM,\s*OPTCR\s*=\s*3600\s*,\s*10000000\s*,\s*0\.0",
        f"RESLIM, ITERLIM, OPTCR = {budget_s}, 10000000, 0.0",
        source,
        count=1,
    )
    if count != 1:
        raise ValueError("Could not patch RESLIM, ITERLIM, OPTCR assignment.")

    output_literal = repr(str(output_dir))
    patched, count = re.subn(
        r'out_dir\s*=\s*os\.path\.join\(\s*os\.path\.dirname\(os\.path\.abspath\(__file__\)\)\s*,\s*"results"\s*\)',
        lambda _match: f"out_dir = {output_literal}",
        patched,
        count=1,
    )
    if count != 1:
        raise ValueError("Could not patch the output directory assignment.")

    return patched


def execute_patched_source(instance: str, budget_s: int, output_dir: Path) -> Path:
    """Execute one patched source file and validate the generated JSON."""
    source_path = SOURCE_DIR / f"{instance}.py"
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    source = source_path.read_text(encoding="utf-8")
    patched = patch_source(source, budget_s=budget_s, output_dir=output_dir)

    with tempfile.TemporaryDirectory(prefix=f"{instance}_patched_") as tmp:
        patched_path = Path(tmp) / f"{instance}_patched.py"
        patched_path.write_text(patched, encoding="utf-8")
        subprocess.run(
            [sys.executable, str(patched_path)],
            cwd=ROOT,
            check=True,
        )

    json_path = output_dir / f"{instance}.json"
    if not json_path.exists():
        raise FileNotFoundError(f"Expected JSON was not created: {json_path}")

    with json_path.open("r", encoding="utf-8") as fh:
        result = json.load(fh)
    if result.get("reslim_s") != budget_s:
        raise ValueError(
            f"{json_path} has reslim_s={result.get('reslim_s')}, expected {budget_s}."
        )

    return json_path


def run_smoke_test() -> None:
    """Run a 60-second temporary execution to verify the patch mechanism."""
    temp_output = Path(tempfile.mkdtemp(prefix="treibacher_gamspy_smoke_"))
    try:
        json_path = execute_patched_source(
            MISSING_INSTANCES[0],
            budget_s=60,
            output_dir=temp_output,
        )
        print(f"Smoke test passed: {json_path}")
    finally:
        shutil.rmtree(temp_output, ignore_errors=True)


def run_real_instances() -> None:
    """Run the missing three-hour jobs, skipping completed JSON files."""
    for instance in MISSING_INSTANCES:
        json_path = REAL_OUTPUT_DIR / f"{instance}.json"
        if json_path.exists():
            with json_path.open("r", encoding="utf-8") as fh:
                result = json.load(fh)
            if result.get("reslim_s") == 10800:
                print(f"Skipping {instance}: existing 3h JSON found.")
                continue
            raise ValueError(f"{json_path} exists but is not a 3h result.")

        created = execute_patched_source(instance, budget_s=10800, output_dir=REAL_OUTPUT_DIR)
        print(f"Created {created}")


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(
        description="Run missing 3X GAMSPy instances at a 3h CPLEX budget."
    )
    parser.add_argument(
        "--smoke-only",
        action="store_true",
        help="Run only the 60-second temporary smoke test.",
    )
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip the 60-second temporary smoke test before real runs.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the smoke test and, unless requested otherwise, the real jobs."""
    args = parse_args()
    if not args.skip_smoke:
        run_smoke_test()
    if args.smoke_only:
        return 0
    run_real_instances()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
