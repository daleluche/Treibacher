"""Run the fix-and-optimize tuning grid for the PSP matheuristic."""
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
RESULTS_DIR = MATHEURISTICS_DIR / "results_tuning"
COMPARISON_TABLE = ROOT / "analysis" / "output" / "comparison_table.csv"

TUNING_INSTANCES = [
    ("5X", "IncT5x_3", ROOT / "experiments" / "GAMSPy" / "5X" / "IncT5x_3.py"),
    ("5X", "IncT5x_10", ROOT / "experiments" / "GAMSPy" / "5X" / "IncT5x_10.py"),
]
OMEGAS = (12, 20, 28)
TL_FOS = (30.0, 60.0)


def config_label(omega: int, tl_fo: float) -> str:
    """Return a compact tuning configuration label."""
    tl_text = f"{tl_fo:g}"
    return f"omega{omega}_tlfo{tl_text}"


def result_path(instance: str, seed: int, omega: int, tl_fo: float) -> Path:
    """Return the expected tuning JSON path for one run."""
    return RESULTS_DIR / f"{instance}_rf_fo_seed{seed}_{config_label(omega, tl_fo)}.json"


def parse_only(tokens: list[str] | None) -> set[str]:
    """Normalize --only tokens for instance or instance:config filtering."""
    if not tokens:
        return set()
    selected: set[str] = set()
    for token in tokens:
        for part in token.split(","):
            part = part.strip()
            if part:
                selected.add(part)
    return selected


def should_run(instance: str, label: str, selected: set[str]) -> bool:
    """Return whether an instance/config pair should be run."""
    if not selected:
        return True
    return instance in selected or label in selected or f"{instance}:{label}" in selected


def result_matches(path: Path, seed: int, budget: float, omega: int, tl_fo: float, threads: int) -> bool:
    """Return whether an existing JSON matches this tuning configuration."""
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    params = data.get("params", {})
    return (
        data.get("method") == "rf+fo"
        and int(data.get("seed", -1)) == seed
        and abs(float(params.get("budget", -1.0)) - budget) < 1e-9
        and int(params.get("omega", -1)) == omega
        and int(params.get("step_fo", -1)) == omega // 2
        and abs(float(params.get("tl_fo", -1.0)) - tl_fo) < 1e-9
        and int(params.get("threads", -1)) == threads
    )


def run_one(instance_path: Path, budget: float, seed: int, omega: int, tl_fo: float, threads: int) -> Path:
    """Run one RF+FO tuning configuration and write its JSON output."""
    params = RunParams(
        budget=budget,
        sigma=10,
        step=5,
        omega=omega,
        step_fo=omega // 2,
        tl_rf=120.0,
        tl_fo=tl_fo,
        method="rf+fo",
        start_from=None,
        threads=threads,
        output_suffix=f"_{config_label(omega, tl_fo)}",
    )
    wall_start = time.perf_counter()
    result = run_matheuristic(instance_path, params, seed)
    output_path = write_result(instance_path, params, seed, result, output_dir=RESULTS_DIR)
    data = json.loads(output_path.read_text(encoding="utf-8"))
    data["wall_time_total"] = round(time.perf_counter() - wall_start, 3)
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return output_path


def load_result(path: Path) -> dict:
    """Load one tuning result JSON."""
    return json.loads(path.read_text(encoding="utf-8"))


def result_rows(seed: int) -> list[dict]:
    """Collect completed tuning result rows."""
    rows = []
    refs = pd.read_csv(COMPARISON_TABLE).set_index("instance")
    for dataset, instance, _ in TUNING_INSTANCES:
        bks = float(refs.loc[instance, "BKS"]) if instance in refs.index else float("nan")
        for omega in OMEGAS:
            for tl_fo in TL_FOS:
                path = result_path(instance, seed, omega, tl_fo)
                label = config_label(omega, tl_fo)
                if not path.exists():
                    rows.append(
                        {
                            "dataset": dataset,
                            "instance": instance,
                            "config": label,
                            "omega": omega,
                            "tl_fo": tl_fo,
                            "Z_final": None,
                            "fo_accepts": None,
                            "fo_sweeps_completed": None,
                            "gap_pct": None,
                            "path": path,
                        }
                    )
                    continue
                data = load_result(path)
                z_final = float(data["Z_final"])
                rows.append(
                    {
                        "dataset": dataset,
                        "instance": instance,
                        "config": label,
                        "omega": omega,
                        "tl_fo": tl_fo,
                        "Z_final": z_final,
                        "fo_accepts": int(data.get("fo_accepts", 0)),
                        "fo_sweeps_completed": int(data.get("fo_sweeps_completed", 0)),
                        "gap_pct": 100.0 * (z_final - bks) / bks if bks == bks and bks > 0 else None,
                        "path": path,
                    }
                )
    return rows


def print_table(rows: list[dict]) -> None:
    """Print the requested tuning table to stdout."""
    table = pd.DataFrame(rows)
    table = table[["instance", "config", "Z_final", "fo_accepts", "fo_sweeps_completed"]]
    print("\nTuning summary")
    print(table.to_string(index=False))


def write_summary(rows: list[dict]) -> Path:
    """Write the tuning recommendation markdown report."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    completed = [row for row in rows if row["Z_final"] is not None]
    if not completed:
        summary = RESULTS_DIR / "tuning_summary.md"
        summary.write_text("# F&O tuning summary\n\nNo completed tuning runs were found.\n", encoding="utf-8")
        return summary

    df = pd.DataFrame(completed)
    winners = df.sort_values(["instance", "Z_final"]).groupby("instance", as_index=False).first()
    mean_gap = df.groupby("config", as_index=False)["gap_pct"].mean().sort_values("gap_pct")
    recommendation = mean_gap.iloc[0]

    lines = [
        "# F&O tuning summary",
        "",
        "Grid: omega in {12, 20, 28}, tl_window_fo in {30, 60}, step_fo = omega / 2.",
        "Relative gaps use the BKS column from analysis/output/comparison_table.csv.",
        "",
        "## Winner by instance",
        "",
        "| instance | config | Z_final | fo_accepts | complete_sweeps | gap_to_BKS_pct |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in winners.iterrows():
        lines.append(
            "| {instance} | {config} | {z:.6f} | {accepts} | {sweeps} | {gap:.4f} |".format(
                instance=row["instance"],
                config=row["config"],
                z=float(row["Z_final"]),
                accepts=int(row["fo_accepts"]),
                sweeps=int(row["fo_sweeps_completed"]),
                gap=float(row["gap_pct"]),
            )
        )

    lines.extend(
        [
            "",
            "## Mean relative gap by config",
            "",
            "| config | mean_gap_to_BKS_pct |",
            "|---|---:|",
        ]
    )
    for _, row in mean_gap.iterrows():
        lines.append(f"| {row['config']} | {float(row['gap_pct']):.4f} |")

    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            (
                "Recommended configuration: "
                f"{recommendation['config']} "
                f"(mean gap to BKS = {float(recommendation['gap_pct']):.4f}%)."
            ),
            "",
        ]
    )
    summary = RESULTS_DIR / "tuning_summary.md"
    summary.write_text("\n".join(lines), encoding="utf-8")
    return summary


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="Run the two-instance RF+FO tuning grid.")
    parser.add_argument("--budget", type=float, default=3600.0)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--only", nargs="*", default=None, help="Instances, configs, or instance:config pairs.")
    parser.add_argument("--force", action="store_true", help="Rerun matching JSONs instead of resuming.")
    parser.add_argument("--dry-run", action="store_true", help="Print selected runs without executing.")
    parser.add_argument("--threads", type=int, default=0, help="CPLEX threads option; 0 lets CPLEX use all.")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    """Run all selected tuning jobs sequentially."""
    args = parse_args(argv)
    selected = parse_only(args.only)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    planned = [
        (dataset, instance, path, omega, tl_fo)
        for dataset, instance, path in TUNING_INSTANCES
        for omega in OMEGAS
        for tl_fo in TL_FOS
        if should_run(instance, config_label(omega, tl_fo), selected)
    ]
    print(f"Selected {len(planned)} tuning run(s).")

    for idx, (dataset, instance, path, omega, tl_fo) in enumerate(planned, start=1):
        label = config_label(omega, tl_fo)
        out_path = result_path(instance, args.seed, omega, tl_fo)
        progress = f"{idx}/{len(planned)} {dataset}/{instance} {label}"
        if not args.force and result_matches(out_path, args.seed, args.budget, omega, tl_fo, args.threads):
            print(f"[SKIP] {progress}: {out_path}")
            continue
        if args.dry_run:
            print(f"[DRY] {progress}: {path}")
            continue
        print(f"[RUN] {progress}: budget={args.budget:.0f}s seed={args.seed}")
        written = run_one(path, args.budget, args.seed, omega, tl_fo, args.threads)
        print(f"[DONE] {progress}: {written}")

    rows = result_rows(args.seed)
    print_table(rows)
    summary_path = write_summary(rows)
    print(f"\nSummary written to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
