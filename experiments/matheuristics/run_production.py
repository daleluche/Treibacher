"""Run Sprint 3 production grades with window logging and resumability."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Iterable

import pandas as pd

if __package__ in (None, ""):
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))

from experiments.matheuristics.psp_instance import load_instance
from experiments.matheuristics.rf_fo_psp import RunParams, make_windows, run_matheuristic, write_result, write_window_log

ROOT = Path(__file__).resolve().parents[2]
GAMSPY_DIR = ROOT / "experiments" / "GAMSPy"
RESULTS_DIR = ROOT / "experiments" / "matheuristics" / "results_production"

TUNED_OMEGA = 20
TUNED_STEP_FO = 10
TUNED_TL_FO = 30.0


def method_label(method: str) -> str:
    """Return a filename-safe method label."""
    return method.replace("+", "_")


def dataset_instances(dataset: str) -> list[Path]:
    """Return sorted instance paths for a dataset."""
    return sorted((GAMSPY_DIR / dataset).glob("*.py"), key=lambda path: path.stem.lower())


def real_to_5x_instances() -> list[Path]:
    """Return the 50 Real--5X instance paths."""
    paths: list[Path] = []
    for dataset in ("Real", "2X", "3X", "4X", "5X"):
        paths.extend(dataset_instances(dataset))
    return paths


def all_60_instances() -> list[Path]:
    """Return the 60 production instance paths."""
    paths = real_to_5x_instances()
    for dataset in ("8X", "10X"):
        paths.extend(dataset_instances(dataset))
    return paths


def grade_c_instances() -> list[Path]:
    """Return the 12 Grade C variability instances."""
    names = [
        ("3X", "IncT3x_3"),
        ("3X", "IncT3x_7"),
        ("4X", "IncT4x_3"),
        ("4X", "IncT4x_7"),
        ("5X", "IncT5x_3"),
        ("5X", "IncT5x_10"),
        *[("8X", f"IncT8x_{idx}") for idx in range(2, 7)],
        ("10X", "IncT10x_5"),
    ]
    return [GAMSPY_DIR / dataset / f"{name}.py" for dataset, name in names]


def jobs_for_grade(grade: str) -> tuple[Path, float, list[int], list[str], list[Path]]:
    """Return output directory, budget, seeds, methods, and instances for a grade."""
    if grade == "B":
        return RESULTS_DIR / "b600", 600.0, [1], ["mip", "rf+fo", "rf+mip"], all_60_instances()
    if grade == "A":
        return RESULTS_DIR / "a3600", 3600.0, [1], ["rf+fo"], real_to_5x_instances()
    if grade == "C":
        return RESULTS_DIR / "c_seeds", 3600.0, [2, 3], ["rf+fo"], grade_c_instances()
    raise ValueError(f"Unknown grade {grade}.")


def result_path(output_dir: Path, instance_name: str, method: str, seed: int, budget: float) -> Path:
    """Return the expected result path."""
    return output_dir / f"{instance_name}_{method_label(method)}_seed{seed}_b{int(budget)}.json"


def params_for(method: str, budget: float, threads: int, log_windows: bool) -> RunParams:
    """Build production parameters for one run."""
    return RunParams(
        budget=budget,
        sigma=10,
        step=5,
        omega=TUNED_OMEGA,
        step_fo=TUNED_STEP_FO,
        tl_rf=120.0,
        tl_fo=TUNED_TL_FO,
        method=method,
        start_from=None,
        threads=threads,
        output_suffix=f"_b{int(budget)}",
        log_windows=log_windows,
    )


def result_matches(path: Path, method: str, seed: int, budget: float, threads: int, log_windows: bool) -> bool:
    """Return whether an existing JSON matches the requested job."""
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
        and bool(params.get("log_windows", False)) == log_windows
    )


def run_one(instance_path: Path, method: str, seed: int, budget: float, output_dir: Path, threads: int, log_windows: bool) -> Path:
    """Run one production job and write result JSON and window log."""
    params = params_for(method, budget, threads, log_windows)
    wall_start = time.perf_counter()
    result = run_matheuristic(instance_path, params, seed)
    output_path = write_result(instance_path, params, seed, result, output_dir=output_dir)
    data = json.loads(output_path.read_text(encoding="utf-8"))
    data["wall_time_total"] = round(time.perf_counter() - wall_start, 3)
    data["window_log_path"] = None
    if log_windows:
        log_path = write_window_log(output_path, result.window_log_rows)
        data["window_log_path"] = None if log_path is None else str(log_path)
        data["instrumentation_overhead_percent"] = (
            round(100.0 * result.instrumentation_wall_time / data["wall_time_total"], 6)
            if data["wall_time_total"]
            else 0.0
        )
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return output_path


def parse_only(tokens: list[str] | None) -> set[str]:
    """Normalize optional filters."""
    if not tokens:
        return set()
    selected: set[str] = set()
    for token in tokens:
        selected.update(part.strip() for part in token.split(",") if part.strip())
    return selected


def should_run(instance: str, method: str, selected: set[str]) -> bool:
    """Return whether a job passes the filter."""
    if not selected:
        return True
    keys = {instance, method, method_label(method), f"{instance}:{method}", f"{instance}:{method_label(method)}"}
    return bool(keys & selected)


def rf_budget_guard(instance_path: Path, budget: float) -> float:
    """Return the RF wall-clock guard for an instance."""
    inst = load_instance(instance_path)
    return min(0.25 * budget, len(make_windows(inst.T, 10, 5)) * 120.0)


def build_summary(output_dir: Path, grade: str, budget: float, jobs: list[tuple[Path, str, int]]) -> tuple[pd.DataFrame, list[dict]]:
    """Build a summary table and RF guard validation records."""
    rows = []
    guard_violations = []
    for instance_path, method, seed in jobs:
        instance = instance_path.stem
        path = result_path(output_dir, instance, method, seed, budget)
        if not path.exists():
            rows.append({"grade": grade, "instance": instance, "method": method, "seed": seed, "status": "missing"})
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        guard = rf_budget_guard(instance_path, budget)
        rf_wall = float(data.get("rf_wall_time_s", data.get("rf_wall_time", 0.0)))
        if method != "mip" and rf_wall > guard + 1e-6:
            guard_violations.append({"instance": instance, "method": method, "seed": seed, "rf_wall_time_s": rf_wall, "guard_s": guard})
        rows.append(
            {
                "grade": grade,
                "dataset": data.get("dataset"),
                "instance": instance,
                "method": method,
                "seed": seed,
                "budget_s": budget,
                "Z_final": data.get("Z_final"),
                "construction_used": data.get("construction_used"),
                "rf_wall_time_s": rf_wall,
                "wall_time_total": data.get("wall_time_total"),
                "window_log_rows": data.get("window_log_rows"),
                "early_stop_reason": data.get("early_stop_reason"),
                "status": "ok",
            }
        )
    summary = pd.DataFrame(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_dir / f"grade_{grade.lower()}_summary.csv", index=False)
    lines = [
        f"# Production Grade {grade}",
        "",
        f"Budget: {int(budget)} seconds.",
        "",
        summary.to_markdown(index=False),
        "",
        "## RF Guard Validation",
        "",
    ]
    if guard_violations:
        lines.append(pd.DataFrame(guard_violations).to_markdown(index=False))
    else:
        lines.append("No RF wall-clock guard violations found.")
    (output_dir / f"grade_{grade.lower()}_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary, guard_violations


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="Run Sprint 3 production grades.")
    parser.add_argument("--grade", choices=["B", "A", "C"], required=True)
    parser.add_argument("--only", nargs="*", default=None, help="Instances, methods, or instance:method filters.")
    parser.add_argument("--force", action="store_true", help="Rerun matching JSONs.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned jobs without running.")
    parser.add_argument("--threads", type=int, default=0, help="CPLEX threads option; 0 lets CPLEX use all.")
    parser.add_argument("--no-log-windows", action="store_true", help="Disable window logging.")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    """Run the selected production grade."""
    args = parse_args(argv)
    output_dir, budget, seeds, methods, instances = jobs_for_grade(args.grade)
    selected = parse_only(args.only)
    log_windows = not args.no_log_windows
    output_dir.mkdir(parents=True, exist_ok=True)

    jobs = [
        (instance_path, method, seed)
        for instance_path in instances
        for seed in seeds
        for method in methods
        if should_run(instance_path.stem, method, selected)
    ]
    print(f"Selected {len(jobs)} Grade {args.grade} job(s). log_windows={log_windows}")

    for idx, (instance_path, method, seed) in enumerate(jobs, start=1):
        out_path = result_path(output_dir, instance_path.stem, method, seed, budget)
        label = f"{idx}/{len(jobs)} {instance_path.parent.name}/{instance_path.stem} {method} seed={seed}"
        if not args.force and result_matches(out_path, method, seed, budget, args.threads, log_windows):
            print(f"[SKIP] {label}: {out_path}")
            continue
        if args.dry_run:
            print(f"[DRY] {label}: {instance_path}")
            continue
        print(f"[RUN] {label}: budget={budget:.0f}s")
        written = run_one(instance_path, method, seed, budget, output_dir, args.threads, log_windows)
        print(f"[DONE] {label}: {written}")

    if not args.dry_run:
        summary, violations = build_summary(output_dir, args.grade, budget, jobs)
        print(summary[["dataset", "instance", "method", "seed", "Z_final", "rf_wall_time_s", "wall_time_total", "early_stop_reason"]].to_string(index=False))
        if violations:
            print("RF guard violations:")
            print(pd.DataFrame(violations).to_string(index=False))
            return 2
        print("No RF wall-clock guard violations found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
