"""
run_all_ils.py — Batch runner for GRASP+ILS v2.0 on all 50 PSP instances.

Usage:
    python run_all_ils.py [options]

Options:
    --out_dir   DIR     Output directory (default: results_ils_v2)
    --n_runs    N       Runs per instance (default: 10)
    --time      T       Time limit per run in seconds (default: 3600)
    --seed      S       Base random seed (default: 0)
    --datasets  DS...   Subset of datasets to run (default: all)
                        Choices: 2X 3X 4X 5X Real
    --instances I...    Subset of instance names to run (default: all)
    --resume            Skip instances that already have a complete summary
    --workers   W       Parallel workers per instance (0 = all CPU cores)

Standard time: 3600 s (60 min) — matches GAMSPy/CPLEX22 runs for fair comparison.

Examples:
    # Full production run (50 instances × 10 runs × 60 min = ~500 CPU-hours)
    python run_all_ils.py

    # Quick test: 2 runs × 120 seconds on Real only
    python run_all_ils.py --datasets Real --n_runs 2 --time 120

    # Resume interrupted run
    python run_all_ils.py --resume

    # Run only 5X instances (7 still missing from v1 run)
    python run_all_ils.py --datasets 5X

    # Use 8 parallel workers
    python run_all_ils.py --workers 8
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from pathlib import Path

# ── Path setup ──────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from grasp_ils_psp import load_instance_from_py, run_instance

# ── MIP bounds from CPLEX22 (best_bound, used for gap reporting) ─────────────
# None = CPLEX22 did not return a bound for this instance (gap not computed)
MIP_BOUNDS: dict[str, float | None] = {
    # ── Real ─────────────────────────────────────────────────────────────────
    "Ale_1":    86264.683,
    "Ale_2":    99950.709,
    "Ale_3":    39695.173,
    "Ale_4":   127725.976,
    "Ale_5":    35426.141,
    "Ale_6":    66677.463,
    "Ale_7":    10568.618,
    "Ale_8":   160911.938,
    "Ale_9":    15627.917,
    "Ale_10":    5639.568,
    # ── 2X ───────────────────────────────────────────────────────────────────
    "IncT2X_1":  40179.544,
    "IncT2X_2":  None,          # CPLEX22 bound not available
    "IncT2X_3":  42938.570,
    "IncT2X_4": 131571.000,
    "IncT2X_5":  38183.994,
    "IncT2X_6":  70335.169,
    "IncT2X_7":  13506.887,
    "IncT2X_8": 169018.311,
    "IncT2X_9":  18632.113,
    "IncT2X_10":  8335.230,
    # ── 3X ───────────────────────────────────────────────────────────────────
    "IncT3x_1":  42979.183,
    "IncT3x_2": 108415.299,
    "IncT3x_3":  45689.573,
    "IncT3x_4": 134218.018,
    "IncT3x_5":  40503.384,
    "IncT3x_6":  73092.751,
    "IncT3x_7":  None,
    "IncT3x_8":  None,
    "IncT3x_9":  None,
    "IncT3x_10": 10501.363,
    # ── 4X ───────────────────────────────────────────────────────────────────
    "IncT4x_1":  45448.029,
    "IncT4x_2": 110607.976,
    "IncT4x_3":  48583.051,
    "IncT4x_4": 136586.186,
    "IncT4x_5":  42873.136,
    "IncT4x_6":  75649.648,
    "IncT4x_7":  16244.250,
    "IncT4x_8": 174178.667,
    "IncT4x_9":  23391.565,
    "IncT4x_10": 12515.284,
    # ── 5X ───────────────────────────────────────────────────────────────────
    "IncT5x_1":  47662.707,
    "IncT5x_2": 112895.177,
    "IncT5x_3":  51461.816,
    "IncT5x_4": 138997.566,
    "IncT5x_5":  45181.148,
    "IncT5x_6":  77922.383,
    "IncT5x_7":  18546.294,
    "IncT5x_8": 175931.402,
    "IncT5x_9":  24011.330,
    "IncT5x_10": 13779.689,
}

# ── Instance catalogue ────────────────────────────────────────────────────────
# (dataset, name, py_file_stem)  — stem must match GAMSPy/<dataset>/<stem>.py
INSTANCES: list[tuple[str, str]] = [
    # Real
    ("Real", "Ale_1"), ("Real", "Ale_2"),  ("Real", "Ale_3"),
    ("Real", "Ale_4"), ("Real", "Ale_5"),  ("Real", "Ale_6"),
    ("Real", "Ale_7"), ("Real", "Ale_8"),  ("Real", "Ale_9"),
    ("Real", "Ale_10"),
    # 2X
    ("2X", "IncT2X_1"),  ("2X", "IncT2X_2"),  ("2X", "IncT2X_3"),
    ("2X", "IncT2X_4"),  ("2X", "IncT2X_5"),  ("2X", "IncT2X_6"),
    ("2X", "IncT2X_7"),  ("2X", "IncT2X_8"),  ("2X", "IncT2X_9"),
    ("2X", "IncT2X_10"),
    # 3X
    ("3X", "IncT3x_1"),  ("3X", "IncT3x_2"),  ("3X", "IncT3x_3"),
    ("3X", "IncT3x_4"),  ("3X", "IncT3x_5"),  ("3X", "IncT3x_6"),
    ("3X", "IncT3x_7"),  ("3X", "IncT3x_8"),  ("3X", "IncT3x_9"),
    ("3X", "IncT3x_10"),
    # 4X
    ("4X", "IncT4x_1"),  ("4X", "IncT4x_2"),  ("4X", "IncT4x_3"),
    ("4X", "IncT4x_4"),  ("4X", "IncT4x_5"),  ("4X", "IncT4x_6"),
    ("4X", "IncT4x_7"),  ("4X", "IncT4x_8"),  ("4X", "IncT4x_9"),
    ("4X", "IncT4x_10"),
    # 5X
    ("5X", "IncT5x_1"),  ("5X", "IncT5x_2"),  ("5X", "IncT5x_3"),
    ("5X", "IncT5x_4"),  ("5X", "IncT5x_5"),  ("5X", "IncT5x_6"),
    ("5X", "IncT5x_7"),  ("5X", "IncT5x_8"),  ("5X", "IncT5x_9"),
    ("5X", "IncT5x_10"),
]

# ── Resolve GAMSPy .py file path ──────────────────────────────────────────────
def _resolve_py(dataset: str, name: str) -> Path:
    """Return path to the GAMSPy instance file."""
    gamspy_dir = SCRIPT_DIR.parent / "GAMSPy" / dataset
    candidate = gamspy_dir / f"{name}.py"
    if not candidate.exists():
        raise FileNotFoundError(
            f"Instance file not found: {candidate}\n"
            f"Expected: GAMSPy/{dataset}/{name}.py"
        )
    return candidate


# ── CSV summary helpers ───────────────────────────────────────────────────────
CSV_FIELDS = [
    "dataset", "instance",
    "Z_best", "Z_mean", "Z_std", "Z_worst",
    "gap_best_vs_mip", "gap_mean_vs_mip",
    "mip_bound", "n_runs",
    "t2best_best", "t2best_mean",
    "ils_iters_mean",
]


def _append_csv(row: dict, csv_path: Path) -> None:
    """Append one row to the master CSV, writing header if file is new."""
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row)


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch GRASP+ILS runner — all 50 PSP instances"
    )
    parser.add_argument("--out_dir",   default="results_ils_v2",
                        help="Output directory (default: results_ils_v2)")
    parser.add_argument("--n_runs",    type=int,   default=10,
                        help="Runs per instance (default: 10)")
    parser.add_argument("--time",      type=float, default=3600.0,
                        help="Time limit per run in seconds (default: 3600)")
    parser.add_argument("--seed",      type=int,   default=0,
                        help="Base random seed (default: 0)")
    parser.add_argument("--datasets",  nargs="+",  default=None,
                        choices=["2X", "3X", "4X", "5X", "Real"],
                        help="Limit run to these datasets")
    parser.add_argument("--instances", nargs="+",  default=None,
                        help="Limit run to these instance names")
    parser.add_argument("--resume",    action="store_true",
                        help="Skip instances with a complete summary JSON")
    parser.add_argument("--workers",   type=int,   default=0,
                        help="Parallel workers per instance (0 = all CPU cores, 1 = sequential)")
    args = parser.parse_args()

    # ── logging ────────────────────────────────────────────────────────────
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    log_file = out_dir / "run_all_ils.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, mode="a"),
        ],
    )
    log = logging.getLogger(__name__)

    csv_path = out_dir / "results_summary.csv"

    # ── Build work list ─────────────────────────────────────────────────────
    work = [
        (ds, name) for ds, name in INSTANCES
        if (args.datasets is None or ds in args.datasets)
        and (args.instances is None or name in args.instances)
    ]

    log.info(f"{'='*60}")
    log.info(f"GRASP+ILS v2.0 — Batch Run")
    log.info(f"  Instances  : {len(work)}")
    log.info(f"  Runs/inst  : {args.n_runs}")
    log.info(f"  Time/run   : {args.time:.0f}s")
    log.info(f"  Total (est): {len(work) * args.n_runs * args.time / 3600:.1f} CPU-h")
    log.info(f"  Output dir : {out_dir.resolve()}")
    log.info(f"{'='*60}")

    wall_start = time.time()
    done = 0
    errors = []

    for idx, (dataset, name) in enumerate(work, 1):
        summary_file = out_dir / f"{name}_summary.json"

        # --resume: skip if summary exists and has the right number of runs
        if args.resume and summary_file.exists():
            try:
                with open(summary_file) as f:
                    existing = json.load(f)
                if existing.get("n_runs", 0) >= args.n_runs:
                    log.info(f"[{idx}/{len(work)}] SKIP {name} — resume (summary exists)")
                    continue
            except Exception:
                pass  # corrupted summary → redo

        log.info(f"[{idx}/{len(work)}] START {name} ({dataset})")

        try:
            py_path = _resolve_py(dataset, name)
        except FileNotFoundError as e:
            log.error(str(e))
            errors.append((name, str(e)))
            continue

        mip_bound = MIP_BOUNDS.get(name)
        t0 = time.time()

        try:
            summary = run_instance(
                py_path=str(py_path),
                name=name,
                dataset=dataset,
                out_dir=str(out_dir),
                mip_bound=mip_bound,
                n_runs=args.n_runs,
                time_limit_s=args.time,
                base_seed=args.seed,
                n_workers=args.workers,
            )
        except Exception as exc:
            elapsed = time.time() - t0
            log.error(f"  ERROR in {name} after {elapsed:.0f}s: {exc}", exc_info=True)
            errors.append((name, str(exc)))
            continue

        elapsed = time.time() - t0
        done += 1

        # Append to master CSV
        csv_row = {
            "dataset":         dataset,
            "instance":        name,
            "Z_best":          summary.get("Z_best"),
            "Z_mean":          summary.get("Z_mean"),
            "Z_std":           summary.get("Z_std"),
            "Z_worst":         summary.get("Z_worst"),
            "gap_best_vs_mip": summary.get("gap_best_vs_mip"),
            "gap_mean_vs_mip": summary.get("gap_mean_vs_mip"),
            "mip_bound":       summary.get("mip_bound"),
            "n_runs":          summary.get("n_runs"),
            "t2best_best":     summary.get("t2best_best"),
            "t2best_mean":     summary.get("t2best_mean"),
            "ils_iters_mean":  summary.get("ils_iters_mean"),
        }
        _append_csv(csv_row, csv_path)

        log.info(
            f"  DONE {name}: Z_best={summary.get('Z_best'):.3f}  "
            f"gap={summary.get('gap_best_vs_mip')}%  "
            f"elapsed={elapsed:.0f}s"
        )

    # ── Final report ────────────────────────────────────────────────────────
    total_wall = time.time() - wall_start
    log.info(f"\n{'='*60}")
    log.info(f"Batch complete: {done}/{len(work)} instances OK, {len(errors)} errors")
    log.info(f"Wall time: {total_wall/3600:.2f}h  ({total_wall:.0f}s)")
    log.info(f"Results  : {out_dir.resolve()}")
    if errors:
        log.warning(f"Errors ({len(errors)}):")
        for name, msg in errors:
            log.warning(f"  {name}: {msg}")
    log.info(f"{'='*60}")


if __name__ == "__main__":
    main()
