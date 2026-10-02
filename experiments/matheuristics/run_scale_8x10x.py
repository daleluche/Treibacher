"""Run the 8X/10X scale experiment for RF+FO, RF+MIP, and cold MIP."""
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

from experiments.matheuristics.rf_fo_psp import RunParams, run_matheuristic, write_result

ROOT = Path(__file__).resolve().parents[2]
MATHEURISTICS_DIR = ROOT / "experiments" / "matheuristics"
RESULTS_DIR = MATHEURISTICS_DIR / "results_scale_8x10x"

SCALE_INSTANCES = [
    (dataset, f"IncT{dataset.lower()}_{idx}", ROOT / "experiments" / "GAMSPy" / dataset / f"IncT{dataset.lower()}_{idx}.py")
    for dataset in ("8X", "10X")
    for idx in range(2, 7)
]
METHODS = ("rf+fo", "rf+mip", "mip")
DEFAULT_BUDGET = 3600.0
TUNED_OMEGA = 20
TUNED_STEP_FO = 10
TUNED_TL_FO = 30.0


def method_label(method: str) -> str:
    """Return a filename-safe method label."""
    return method.replace("+", "_")


def result_path(instance: str, method: str, seed: int, results_dir: Path = RESULTS_DIR, budget: float = DEFAULT_BUDGET) -> Path:
    """Return the expected scale-experiment JSON path."""
    return results_dir / f"{instance}_{method_label(method)}_seed{seed}_b{int(budget)}.json"


def parse_only(tokens: list[str] | None) -> set[str]:
    """Normalize --only tokens for instance, method, or instance:method filters."""
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
    """Return whether an instance/method job should be selected."""
    if not selected:
        return True
    keys = {instance, method, method_label(method), f"{instance}:{method}", f"{instance}:{method_label(method)}"}
    return bool(keys & selected)


def result_matches(path: Path, method: str, budget: float, seed: int, threads: int) -> bool:
    """Return whether an existing JSON matches this scale-experiment configuration."""
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
    """Build RF/FO parameters for one scale run."""
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
    )


def run_one(instance_path: Path, method: str, budget: float, seed: int, threads: int, results_dir: Path) -> Path:
    """Run one scale-experiment job and write its JSON output."""
    params = params_for(method, budget, threads)
    wall_start = time.perf_counter()
    result = run_matheuristic(instance_path, params, seed)
    output_path = write_result(instance_path, params, seed, result, output_dir=results_dir)
    data = json.loads(output_path.read_text(encoding="utf-8"))
    data["wall_time_total"] = round(time.perf_counter() - wall_start, 3)
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return output_path


def build_summary_rows(seed: int, results_dir: Path, budget: float, methods: tuple[str, ...]) -> list[dict]:
    """Build consolidated rows for completed scale runs."""
    rows = []
    for dataset, instance, _ in SCALE_INSTANCES:
        values: dict[str, float | None] = {}
        paths: dict[str, str | None] = {}
        for method in METHODS:
            path = result_path(instance, method, seed, results_dir, budget)
            if method == "mip" and not path.exists():
                path = result_path(instance, method, seed, RESULTS_DIR, budget)
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                values[method] = float(data["Z_final"])
                paths[method] = str(path)
            else:
                values[method] = None
                paths[method] = None
        candidates = {method: value for method, value in values.items() if value is not None and method in methods}
        if values["mip"] is not None:
            candidates.setdefault("mip", values["mip"])
        decomp_candidates = {
            method: values[method]
            for method in ("rf+fo", "rf+mip")
            if values.get(method) is not None and method in methods
        }
        best_method = min(candidates, key=candidates.get) if candidates else None
        best_decomp_method = min(decomp_candidates, key=decomp_candidates.get) if decomp_candidates else None
        best_decomp_z = decomp_candidates.get(best_decomp_method) if best_decomp_method else None
        rows.append(
            {
                "dataset": dataset,
                "instance": instance,
                "Z_rf_fo": values["rf+fo"],
                "Z_rf_mip": values["rf+mip"],
                "Z_mip": values["mip"],
                "best_decomp_method": best_decomp_method,
                "best_decomp_Z": best_decomp_z,
                "decomp_beats_mip": bool(best_decomp_z is not None and values["mip"] is not None and best_decomp_z < values["mip"]),
                "best_method": best_method,
                "best_Z": candidates.get(best_method) if best_method else None,
                "path_rf_fo": paths["rf+fo"],
                "path_rf_mip": paths["rf+mip"],
                "path_mip": paths["mip"],
            }
        )
    return rows


def format_float(value: float | None) -> str:
    """Format optional float values for markdown tables."""
    return "" if value is None else f"{float(value):.6f}"


def write_outputs(rows: list[dict], results_dir: Path, budget: float, methods: tuple[str, ...]) -> tuple[Path, Path]:
    """Write the consolidated CSV and markdown report."""
    results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = results_dir / "scale_8x10x_summary.csv"
    report_path = results_dir / "scale_8x10x_report.md"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    lines = [
        "# 8X/10X scale experiment",
        "",
        "Instances: IncT8x_2..IncT8x_6 and IncT10x_2..IncT10x_6.",
        f"Budget: {int(budget)} seconds. Seed: 1.",
        "",
        "RF+FO uses omega=20, step_fo=10, and tl_window_fo=30s.",
        "RF+MIP uses the RF incumbent as a MIP start for the full monolithic model.",
        "MIP is the cold monolithic CPLEX baseline; when this is a decomposition-only rerun, the MIP column is read from the registered Sprint 2.5 results.",
        f"Executed methods in this directory: {', '.join(methods)}.",
        "",
        "| instance | rf+fo | rf+mip | mip | best_decomp | decomp_beats_mip | best_method | best_Z |",
        "|---|---:|---:|---:|---|---|---|---:|",
    ]
    for row in rows:
        lines.append(
            "| {instance} | {rf_fo} | {rf_mip} | {mip} | {best_decomp} | {beats} | {best_method} | {best_z} |".format(
                instance=row["instance"],
                rf_fo=format_float(row["Z_rf_fo"]),
                rf_mip=format_float(row["Z_rf_mip"]),
                mip=format_float(row["Z_mip"]),
                best_decomp=row["best_decomp_method"] or "",
                beats=str(row["decomp_beats_mip"]).lower(),
                best_method=row["best_method"] or "",
                best_z=format_float(row["best_Z"]),
            )
        )
    ten_x_rows = [row for row in rows if row["dataset"] == "10X"]
    ten_x_wins = sum(1 for row in ten_x_rows if row["decomp_beats_mip"])
    lines.extend(
        [
            "",
            "Post-hoc H2 comparison for 10X:",
            "",
            f"- Corrected decomposition wins: {ten_x_wins}/5.",
            f"- Exploratory post-fix H2 criterion met: {str(ten_x_wins >= 3).lower()}.",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path, report_path


def print_table(rows: list[dict]) -> None:
    """Print the consolidated scale-experiment table."""
    columns = [
        "instance",
        "Z_rf_fo",
        "Z_rf_mip",
        "Z_mip",
        "best_decomp_method",
        "best_decomp_Z",
        "decomp_beats_mip",
        "best_method",
        "best_Z",
    ]
    print("\n8X/10X scale summary")
    print(pd.DataFrame(rows)[columns].to_string(index=False))


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="Run the 8X/10X PSP scale experiment.")
    parser.add_argument("--budget", type=float, default=DEFAULT_BUDGET)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--only", nargs="*", default=None, help="Instances, methods, or instance:method pairs.")
    parser.add_argument("--methods", nargs="*", default=list(METHODS), choices=list(METHODS), help="Methods to run.")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR, help="Directory for JSONs and summaries.")
    parser.add_argument("--force", action="store_true", help="Rerun matching JSONs instead of resuming.")
    parser.add_argument("--dry-run", action="store_true", help="Print selected runs without executing.")
    parser.add_argument("--threads", type=int, default=0, help="CPLEX threads option; 0 lets CPLEX use all.")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    """Run all selected scale jobs sequentially."""
    args = parse_args(argv)
    selected = parse_only(args.only)
    methods = tuple(args.methods)
    args.results_dir.mkdir(parents=True, exist_ok=True)

    planned = [
        (dataset, instance, path, method)
        for dataset, instance, path in SCALE_INSTANCES
        for method in methods
        if should_run(instance, method, selected)
    ]
    print(f"Selected {len(planned)} 8X/10X scale run(s).")

    for idx, (dataset, instance, path, method) in enumerate(planned, start=1):
        out_path = result_path(instance, method, args.seed, args.results_dir, args.budget)
        label = f"{idx}/{len(planned)} {dataset}/{instance} {method}"
        if not args.force and result_matches(out_path, method, args.budget, args.seed, args.threads):
            print(f"[SKIP] {label}: {out_path}")
            continue
        if args.dry_run:
            print(f"[DRY] {label}: {path}")
            continue
        print(f"[RUN] {label}: budget={args.budget:.0f}s seed={args.seed}")
        written = run_one(path, method, args.budget, args.seed, args.threads, args.results_dir)
        print(f"[DONE] {label}: {written}")

    rows = build_summary_rows(args.seed, args.results_dir, args.budget, methods)
    csv_path, report_path = write_outputs(rows, args.results_dir, args.budget, methods)
    print_table(rows)
    print(f"\nSummary CSV written to {csv_path}")
    print(f"Report written to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
