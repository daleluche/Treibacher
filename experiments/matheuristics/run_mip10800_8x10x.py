"""Run cold monolithic MIP at 10800 seconds for the 8X/10X PSP scale sets."""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Iterable

import pandas as pd

if __package__ in (None, ""):
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))

from experiments.matheuristics.rf_fo_psp import RunParams, run_matheuristic, write_result, write_window_log

ROOT = Path(__file__).resolve().parents[2]
MATHEURISTICS_DIR = ROOT / "experiments" / "matheuristics"
RESULTS_DIR = MATHEURISTICS_DIR / "results_scale_8x10x_mip10800"
DEFAULT_BUDGET = 10800.0
DEFAULT_SEED = 1
METHOD = "mip"

SCALE_INSTANCES = [
    (dataset, f"IncT{dataset.lower()}_{idx}", ROOT / "experiments" / "GAMSPy" / dataset / f"IncT{dataset.lower()}_{idx}.py")
    for dataset in ("8X", "10X")
    for idx in range(2, 7)
]


def result_path(instance: str, seed: int, results_dir: Path, budget: float) -> Path:
    """Return the expected JSON path for one 10800-second MIP run."""
    return results_dir / f"{instance}_{METHOD}_seed{seed}_b{int(budget)}.json"


def parse_only(tokens: list[str] | None) -> set[str]:
    """Normalize --only tokens for instance or dataset filters."""
    if not tokens:
        return set()
    selected: set[str] = set()
    for token in tokens:
        for part in token.split(","):
            part = part.strip()
            if part:
                selected.add(part)
    return selected


def should_run(dataset: str, instance: str, selected: set[str]) -> bool:
    """Return whether an instance is selected by --only."""
    return not selected or bool({dataset, instance, f"{dataset}/{instance}"} & selected)


def finite(value: object) -> bool:
    """Return whether value is a finite number."""
    try:
        numeric = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return math.isfinite(numeric)


def result_matches(path: Path, budget: float, seed: int, threads: int) -> bool:
    """Return whether an existing JSON is a complete matching 10800-second MIP run."""
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    params = data.get("params", {})
    return (
        data.get("method") == METHOD
        and int(data.get("seed", -1)) == seed
        and abs(float(params.get("budget", -1.0)) - budget) < 1e-9
        and int(params.get("threads", -1)) == threads
        and finite(data.get("Z_final"))
        and data.get("model_status") is not None
        and finite(data.get("best_bound"))
    )


def params_for(budget: float, threads: int) -> RunParams:
    """Build cold MIP parameters for rf_fo_psp."""
    return RunParams(
        budget=budget,
        sigma=10,
        step=5,
        omega=20,
        step_fo=10,
        tl_rf=120.0,
        tl_fo=30.0,
        method=METHOD,
        start_from=None,
        threads=threads,
        output_suffix=f"_b{int(budget)}",
        log_windows=True,
    )


def run_one(instance_path: Path, budget: float, seed: int, threads: int, results_dir: Path) -> Path:
    """Run one cold MIP job and write the JSON plus optional window log."""
    params = params_for(budget, threads)
    wall_start = time.perf_counter()
    result = run_matheuristic(instance_path, params, seed)
    output_path = write_result(instance_path, params, seed, result, output_dir=results_dir)
    data = json.loads(output_path.read_text(encoding="utf-8"))
    data["wall_time_total"] = round(time.perf_counter() - wall_start, 3)
    log_path = write_window_log(output_path, result.window_log_rows)
    data["window_log_path"] = None if log_path is None else str(log_path)
    data["instrumentation_overhead_percent"] = (
        round(100.0 * result.instrumentation_wall_time / data["wall_time_total"], 6)
        if data["wall_time_total"]
        else 0.0
    )
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if not result_matches(output_path, budget, seed, threads):
        raise RuntimeError(f"Incomplete or invalid result JSON: {output_path}")
    return output_path


def build_summary(results_dir: Path, budget: float, seed: int) -> list[dict]:
    """Build summary rows from completed 10800-second MIP JSONs."""
    rows = []
    for dataset, instance, _ in SCALE_INSTANCES:
        path = result_path(instance, seed, results_dir, budget)
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        rows.append(
            {
                "dataset": dataset,
                "instance": instance,
                "Z_mip_10800": data.get("Z_final"),
                "best_bound": data.get("best_bound"),
                "gap_solver_pct": data.get("gap_solver_pct"),
                "model_status": data.get("model_status"),
                "solve_status": data.get("solve_status"),
                "wall_time_total": data.get("wall_time_total"),
                "source_path": str(path.relative_to(ROOT)) if path.exists() else None,
            }
        )
    return rows


def write_summary(rows: list[dict], results_dir: Path) -> tuple[Path, Path]:
    """Write CSV and Markdown summaries for the 10800-second MIP experiment."""
    csv_path = results_dir / "mip10800_summary.csv"
    report_path = results_dir / "mip10800_report.md"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    lines = [
        "# Cold MIP 10800s on 8X/10X",
        "",
        "Method: `rf_fo_psp.py --method mip --budget 10800 --seed 1 --threads 0 --log-windows`.",
        "",
        "| instance | Z_mip_10800 | best_bound | gap_pct | model_status | solve_status | wall_s |",
        "|---|---:|---:|---:|---|---|---:|",
    ]
    for row in rows:
        lines.append(
            "| {instance} | {z} | {bound} | {gap} | {model_status} | {solve_status} | {wall} |".format(
                instance=row["instance"],
                z="" if row["Z_mip_10800"] is None else f"{float(row['Z_mip_10800']):.6f}",
                bound="" if row["best_bound"] is None else f"{float(row['best_bound']):.6f}",
                gap="" if row["gap_solver_pct"] is None else f"{float(row['gap_solver_pct']):.6f}",
                model_status=row["model_status"] or "",
                solve_status=row["solve_status"] or "",
                wall="" if row["wall_time_total"] is None else f"{float(row['wall_time_total']):.3f}",
            )
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path, report_path


def validate_completed(rows: list[dict]) -> None:
    """Validate the expected ten JSONs and required MIP audit fields."""
    failures = [
        row["instance"]
        for row in rows
        if not finite(row.get("Z_mip_10800")) or row.get("model_status") is None or not finite(row.get("best_bound"))
    ]
    if len(rows) != 10 or failures:
        raise RuntimeError(f"MIP10800 validation failed; incomplete rows: {failures}")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="Run cold MIP at 10800s for IncT8x/IncT10x instances.")
    parser.add_argument("--budget", type=float, default=DEFAULT_BUDGET)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--threads", type=int, default=0, help="CPLEX threads option; 0 lets CPLEX use all.")
    parser.add_argument("--only", nargs="*", default=None, help="Datasets or instances to run.")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--force", action="store_true", help="Rerun matching JSONs instead of resuming.")
    parser.add_argument("--dry-run", action="store_true", help="Print selected runs without executing.")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    """Run all selected 10800-second MIP jobs sequentially with resume support."""
    args = parse_args(argv)
    selected = parse_only(args.only)
    args.results_dir.mkdir(parents=True, exist_ok=True)

    planned = [
        (dataset, instance, path)
        for dataset, instance, path in SCALE_INSTANCES
        if should_run(dataset, instance, selected)
    ]
    print(f"Selected {len(planned)} cold MIP 10800s run(s).")
    for idx, (dataset, instance, path) in enumerate(planned, start=1):
        out_path = result_path(instance, args.seed, args.results_dir, args.budget)
        label = f"{idx}/{len(planned)} {dataset}/{instance} {METHOD}"
        if not args.force and result_matches(out_path, args.budget, args.seed, args.threads):
            print(f"[SKIP] {label}: {out_path}")
            continue
        if args.dry_run:
            print(f"[DRY] {label}: {path}")
            continue
        print(f"[RUN] {label}: budget={args.budget:.0f}s seed={args.seed} threads={args.threads}")
        written = run_one(path, args.budget, args.seed, args.threads, args.results_dir)
        print(f"[DONE] {label}: {written}")

    rows = build_summary(args.results_dir, args.budget, args.seed)
    if not args.dry_run:
        validate_completed(rows)
    csv_path, report_path = write_summary(rows, args.results_dir)
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"\nSummary CSV written to {csv_path}")
    print(f"Report written to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
