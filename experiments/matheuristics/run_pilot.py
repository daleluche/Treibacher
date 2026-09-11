"""Sequential pilot runner for the PSP RF/FO validation set."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MATHEURISTICS_DIR = ROOT / "experiments" / "matheuristics"
RESULTS_DIR = MATHEURISTICS_DIR / "results_pilot"
RF_FO_SCRIPT = MATHEURISTICS_DIR / "rf_fo_psp.py"
COMPARISON_TABLE = ROOT / "analysis" / "output" / "comparison_table.csv"

PILOT_INSTANCES = [
    ("Real", "Ale_1", ROOT / "experiments" / "GAMSPy" / "Real" / "Ale_1.py"),
    ("2X", "IncT2X_1", ROOT / "experiments" / "GAMSPy" / "2X" / "IncT2X_1.py"),
    ("3X", "IncT3x_3", ROOT / "experiments" / "GAMSPy" / "3X" / "IncT3x_3.py"),
    ("3X", "IncT3x_7", ROOT / "experiments" / "GAMSPy" / "3X" / "IncT3x_7.py"),
    ("4X", "IncT4x_3", ROOT / "experiments" / "GAMSPy" / "4X" / "IncT4x_3.py"),
    ("4X", "IncT4x_7", ROOT / "experiments" / "GAMSPy" / "4X" / "IncT4x_7.py"),
    ("5X", "IncT5x_3", ROOT / "experiments" / "GAMSPy" / "5X" / "IncT5x_3.py"),
    ("5X", "IncT5x_10", ROOT / "experiments" / "GAMSPy" / "5X" / "IncT5x_10.py"),
]
METHODS = ("rf", "rf+fo")


def result_path(instance: str, method: str, seed: int) -> Path:
    """Return the expected result JSON path for one pilot run."""
    return RESULTS_DIR / f"{instance}_{method.replace('+', '_')}_seed{seed}.json"


def result_matches(path: Path, method: str, seed: int, budget: float, threads: int) -> bool:
    """Return whether an existing JSON matches this pilot run configuration."""
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    params = data.get("params", {})
    return (
        data.get("method") == method
        and int(data.get("seed", -1)) == seed
        and abs(float(params.get("budget", -1.0)) - budget) < 1e-9
        and int(params.get("threads", -1)) == threads
    )


def parse_only(tokens: list[str] | None) -> set[str]:
    """Normalize --only tokens for instance or instance:method filtering."""
    if not tokens:
        return set()
    selected: set[str] = set()
    for token in tokens:
        for part in token.split(","):
            part = part.strip()
            if part:
                selected.add(part)
    return selected


def should_run(instance: str, method: str, selected: set[str]) -> bool:
    """Return whether an instance/method pair should be run."""
    if not selected:
        return True
    return instance in selected or f"{instance}:{method}" in selected


def run_one(instance_path: Path, method: str, budget: float, seed: int, threads: int) -> None:
    """Run one RF/FO command and stream output."""
    cmd = [
        sys.executable,
        str(RF_FO_SCRIPT),
        "--instance",
        str(instance_path),
        "--budget",
        str(int(budget) if budget.is_integer() else budget),
        "--seed",
        str(seed),
        "--method",
        method,
        "--threads",
        str(threads),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)


def load_references() -> pd.DataFrame:
    """Load reference values for the pilot table."""
    return pd.read_csv(COMPARISON_TABLE).set_index("instance")


def summarize_table(seed: int) -> pd.DataFrame:
    """Build the terminal summary table for completed pilot runs."""
    refs = load_references()
    rows = []
    for dataset, instance, _ in PILOT_INSTANCES:
        rf_path = result_path(instance, "rf", seed)
        rffo_path = result_path(instance, "rf+fo", seed)
        rf_data = json.loads(rf_path.read_text(encoding="utf-8")) if rf_path.exists() else {}
        rffo_data = json.loads(rffo_path.read_text(encoding="utf-8")) if rffo_path.exists() else {}
        ref = refs.loc[instance]
        rows.append(
            {
                "dataset": dataset,
                "instance": instance,
                "Z_rf": rf_data.get("Z_final"),
                "Z_rf+fo": rffo_data.get("Z_final"),
                "CPLEX@1h": ref.get("cplex_Z_1h"),
                "CPLEX@3h": ref.get("cplex_Z"),
                "ILS_v2_best": ref.get("ils2_Z_best"),
            }
        )
    return pd.DataFrame(rows)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="Run the 8-instance RF/FO pilot.")
    parser.add_argument("--budget", type=float, default=3600.0)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--only", nargs="*", default=None, help="Instances or instance:method pairs to run.")
    parser.add_argument("--force", action="store_true", help="Rerun matching JSONs instead of resuming.")
    parser.add_argument("--dry-run", action="store_true", help="Print selected runs without executing.")
    parser.add_argument("--threads", type=int, default=0, help="CPLEX threads option; 0 lets CPLEX use all.")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    """Run all selected pilot jobs sequentially."""
    args = parse_args(argv)
    selected = parse_only(args.only)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    planned = [
        (dataset, instance, path, method)
        for dataset, instance, path in PILOT_INSTANCES
        for method in METHODS
        if should_run(instance, method, selected)
    ]
    print(f"Selected {len(planned)} run(s).")

    for idx, (dataset, instance, path, method) in enumerate(planned, start=1):
        out_path = result_path(instance, method, args.seed)
        label = f"{idx}/{len(planned)} {dataset}/{instance} {method}"
        if not args.force and result_matches(out_path, method, args.seed, args.budget, args.threads):
            print(f"[SKIP] {label}: {out_path}")
            continue
        if args.dry_run:
            print(f"[DRY] {label}: {path}")
            continue
        print(f"[RUN] {label}: budget={args.budget:.0f}s seed={args.seed}")
        run_one(path, method, args.budget, args.seed, args.threads)

    table = summarize_table(args.seed)
    print("\nPilot summary")
    print(table.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
