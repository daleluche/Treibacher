"""Run short-budget operational PSP experiments for RF+FO, RF+MIP, and MIP."""
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

from experiments.matheuristics.rf_fo_psp import RunParams, run_matheuristic, write_result

ROOT = Path(__file__).resolve().parents[2]
MATHEURISTICS_DIR = ROOT / "experiments" / "matheuristics"
RESULTS_DIR = MATHEURISTICS_DIR / "results_short_budget"
ILS_V2_DIR = ROOT / "experiments" / "GRASP" / "results_ils_v2"

SHORT_INSTANCES = [
    ("3X", "IncT3x_3", ROOT / "experiments" / "GAMSPy" / "3X" / "IncT3x_3.py"),
    ("3X", "IncT3x_7", ROOT / "experiments" / "GAMSPy" / "3X" / "IncT3x_7.py"),
    ("4X", "IncT4x_3", ROOT / "experiments" / "GAMSPy" / "4X" / "IncT4x_3.py"),
    ("4X", "IncT4x_7", ROOT / "experiments" / "GAMSPy" / "4X" / "IncT4x_7.py"),
    ("5X", "IncT5x_3", ROOT / "experiments" / "GAMSPy" / "5X" / "IncT5x_3.py"),
    ("5X", "IncT5x_10", ROOT / "experiments" / "GAMSPy" / "5X" / "IncT5x_10.py"),
]
BUDGETS = (300.0, 600.0)
METHODS = ("rf+fo", "rf+mip", "mip")

TUNED_OMEGA = 20
TUNED_STEP_FO = 10
TUNED_TL_FO = 30.0


def budget_label(budget: float) -> str:
    """Return a compact budget label for filenames."""
    return f"b{int(budget)}" if float(budget).is_integer() else f"b{budget:g}"


def method_label(method: str) -> str:
    """Return a filename-safe method label."""
    return method.replace("+", "_")


def result_path(instance: str, method: str, budget: float, seed: int) -> Path:
    """Return the expected short-budget result path."""
    return RESULTS_DIR / f"{instance}_{method_label(method)}_seed{seed}_{budget_label(budget)}.json"


def parse_only(tokens: list[str] | None) -> set[str]:
    """Normalize --only tokens for instance, method, budget, or combinations."""
    if not tokens:
        return set()
    selected: set[str] = set()
    for token in tokens:
        for part in token.split(","):
            part = part.strip()
            if part:
                selected.add(part)
    return selected


def should_run(instance: str, method: str, budget: float, selected: set[str]) -> bool:
    """Return whether an instance/method/budget job should be selected."""
    if not selected:
        return True
    b_label = budget_label(budget)
    keys = {
        instance,
        method,
        method_label(method),
        b_label,
        f"{instance}:{method}",
        f"{instance}:{method_label(method)}",
        f"{instance}:{b_label}",
        f"{method}:{b_label}",
        f"{method_label(method)}:{b_label}",
        f"{instance}:{method}:{b_label}",
        f"{instance}:{method_label(method)}:{b_label}",
    }
    return bool(keys & selected)


def result_matches(path: Path, method: str, budget: float, seed: int, threads: int) -> bool:
    """Return whether an existing JSON matches this short-budget configuration."""
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
        and (
            method != "rf+fo"
            or (
                int(params.get("omega", -1)) == TUNED_OMEGA
                and int(params.get("step_fo", -1)) == TUNED_STEP_FO
                and abs(float(params.get("tl_fo", -1.0)) - TUNED_TL_FO) < 1e-9
            )
        )
    )


def params_for(method: str, budget: float, threads: int) -> RunParams:
    """Build RF/FO parameters for one short-budget method."""
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
        output_suffix=f"_{budget_label(budget)}",
    )


def run_one(instance_path: Path, method: str, budget: float, seed: int, threads: int) -> Path:
    """Run one short-budget method and write its JSON output."""
    params = params_for(method, budget, threads)
    wall_start = time.perf_counter()
    result = run_matheuristic(instance_path, params, seed)
    output_path = write_result(instance_path, params, seed, result, output_dir=RESULTS_DIR)
    data = json.loads(output_path.read_text(encoding="utf-8"))
    data["wall_time_total"] = round(time.perf_counter() - wall_start, 3)
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return output_path


def ils_best_until(instance: str, budget: float) -> tuple[float | None, int | None, float | None]:
    """Return the best ILS v2 objective reached by any run by the given time."""
    best_z = math.inf
    best_run: int | None = None
    best_time: float | None = None
    for path in sorted(ILS_V2_DIR.glob(f"{instance}_run*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        run_id = int(data.get("run_id", path.stem.rsplit("run", 1)[-1]))
        for item in data.get("improvements", []):
            time_s = float(item.get("time_s", math.inf))
            z_value = float(item.get("Z", math.inf))
            if time_s <= budget and z_value < best_z:
                best_z = z_value
                best_run = run_id
                best_time = time_s
    if best_z == math.inf:
        return None, None, None
    return best_z, best_run, best_time


def load_result(path: Path) -> dict:
    """Load a short-budget result JSON if present."""
    return json.loads(path.read_text(encoding="utf-8"))


def build_summary_rows(seed: int) -> list[dict]:
    """Build consolidated rows for completed short-budget runs."""
    rows = []
    for dataset, instance, _ in SHORT_INSTANCES:
        for budget in BUDGETS:
            ils_z, ils_run, ils_time = ils_best_until(instance, budget)
            method_values: dict[str, float | None] = {}
            method_accepts: dict[str, int | None] = {}
            method_paths: dict[str, str | None] = {}
            for method in METHODS:
                path = result_path(instance, method, budget, seed)
                if path.exists():
                    data = load_result(path)
                    method_values[method] = float(data["Z_final"])
                    method_accepts[method] = int(data.get("fo_accepts", 0))
                    method_paths[method] = str(path)
                else:
                    method_values[method] = None
                    method_accepts[method] = None
                    method_paths[method] = None
            candidates = {k: v for k, v in method_values.items() if v is not None}
            if ils_z is not None:
                candidates["ils_v2"] = ils_z
            best_method = min(candidates, key=candidates.get) if candidates else None
            rows.append(
                {
                    "dataset": dataset,
                    "instance": instance,
                    "budget_s": int(budget),
                    "Z_rf_fo": method_values["rf+fo"],
                    "Z_rf_mip": method_values["rf+mip"],
                    "Z_mip": method_values["mip"],
                    "Z_ils_v2_best_until_budget": ils_z,
                    "ils_v2_run_id": ils_run,
                    "ils_v2_time_to_best_s": ils_time,
                    "best_method": best_method,
                    "best_Z": candidates.get(best_method) if best_method else None,
                    "fo_accepts_rf_fo": method_accepts["rf+fo"],
                    "path_rf_fo": method_paths["rf+fo"],
                    "path_rf_mip": method_paths["rf+mip"],
                    "path_mip": method_paths["mip"],
                }
            )
    return rows


def write_outputs(rows: list[dict]) -> tuple[Path, Path]:
    """Write the consolidated CSV and markdown report."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    table_path = RESULTS_DIR / "short_budget_summary.csv"
    report_path = RESULTS_DIR / "short_budget_report.md"
    df = pd.DataFrame(rows)
    df.to_csv(table_path, index=False)

    lines = [
        "# Short-budget operational regime experiment",
        "",
        "Instances: IncT3x_3, IncT3x_7, IncT4x_3, IncT4x_7, IncT5x_3, IncT5x_10.",
        "Budgets: 300s and 600s. Seed: 1.",
        "",
        "RF+FO uses the Tarefa 2.2 recommendation: omega=20, step_fo=10, tl_window_fo=30s.",
        "RF+MIP runs RF and then solves the full monolithic MIP with the RF incumbent as a MIP start.",
        "MIP is the cold monolithic CPLEX baseline with the same wall-clock budget and no RF.",
        "",
        "ILS v2 references were not rerun. For each instance and budget, the script scans the ten existing",
        "experiments/GRASP/results_ils_v2/<instance>_run*.json files and selects the minimum Z among",
        "improvements entries with time_s <= budget.",
        "",
        "## Consolidated Table",
        "",
        "| instance | budget_s | rf+fo | rf+mip | mip | ils_v2_until_budget | best_method | best_Z |",
        "|---|---:|---:|---:|---:|---:|---|---:|",
    ]
    for row in rows:
        lines.append(
            "| {instance} | {budget} | {rf_fo} | {rf_mip} | {mip} | {ils} | {best_method} | {best_z} |".format(
                instance=row["instance"],
                budget=row["budget_s"],
                rf_fo=format_float(row["Z_rf_fo"]),
                rf_mip=format_float(row["Z_rf_mip"]),
                mip=format_float(row["Z_mip"]),
                ils=format_float(row["Z_ils_v2_best_until_budget"]),
                best_method=row["best_method"] or "",
                best_z=format_float(row["best_Z"]),
            )
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return table_path, report_path


def format_float(value: float | None) -> str:
    """Format optional float values for markdown tables."""
    return "" if value is None else f"{float(value):.6f}"


def print_table(rows: list[dict]) -> None:
    """Print the consolidated short-budget table."""
    df = pd.DataFrame(rows)
    columns = [
        "instance",
        "budget_s",
        "Z_rf_fo",
        "Z_rf_mip",
        "Z_mip",
        "Z_ils_v2_best_until_budget",
        "best_method",
        "best_Z",
    ]
    print("\nShort-budget summary")
    print(df[columns].to_string(index=False))


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="Run the short-budget operational PSP experiment.")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--only", nargs="*", default=None, help="Instances, methods, budgets, or combinations.")
    parser.add_argument("--force", action="store_true", help="Rerun matching JSONs instead of resuming.")
    parser.add_argument("--dry-run", action="store_true", help="Print selected runs without executing.")
    parser.add_argument("--threads", type=int, default=0, help="CPLEX threads option; 0 lets CPLEX use all.")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    """Run all selected short-budget jobs sequentially."""
    args = parse_args(argv)
    selected = parse_only(args.only)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    planned = [
        (dataset, instance, path, budget, method)
        for dataset, instance, path in SHORT_INSTANCES
        for budget in BUDGETS
        for method in METHODS
        if should_run(instance, method, budget, selected)
    ]
    print(f"Selected {len(planned)} short-budget run(s).")

    for idx, (dataset, instance, path, budget, method) in enumerate(planned, start=1):
        out_path = result_path(instance, method, budget, args.seed)
        label = f"{idx}/{len(planned)} {dataset}/{instance} {method} {budget_label(budget)}"
        if not args.force and result_matches(out_path, method, budget, args.seed, args.threads):
            print(f"[SKIP] {label}: {out_path}")
            continue
        if args.dry_run:
            print(f"[DRY] {label}: {path}")
            continue
        print(f"[RUN] {label}: seed={args.seed}")
        written = run_one(path, method, budget, args.seed, args.threads)
        print(f"[DONE] {label}: {written}")

    rows = build_summary_rows(args.seed)
    table_path, report_path = write_outputs(rows)
    print_table(rows)
    print(f"\nSummary CSV written to {table_path}")
    print(f"Report written to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
