"""Run the original real order-book experiment suite with resumability."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Iterable

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from experiments.GRASP.grasp_ils_psp import run_instance
from experiments.matheuristics.rf_fo_psp import RunParams, run_matheuristic, write_result, write_window_log

ROOT = Path(__file__).resolve().parents[2]
INSTANCE_NAME = "REAL_1"
INSTANCE_PATH = ROOT / "experiments" / "GAMSPy" / "S" / f"{INSTANCE_NAME}.py"
RESULTS_DIR = ROOT / "experiments" / "matheuristics" / "results_production" / "real"

TUNED_OMEGA = 20
TUNED_STEP_FO = 10
TUNED_TL_FO = 30.0

MATHEURISTIC_JOBS = [
    ("mip", 600.0, False),
    ("mip", 3600.0, False),
    ("mip", 10800.0, False),
    ("rf+fo", 3600.0, True),
    ("rf+fo", 600.0, True),
    ("rf+mip", 600.0, True),
]


def method_label(method: str) -> str:
    """Return the filename-safe method label used by ``rf_fo_psp``."""
    return method.replace("+", "_")


def result_path(method: str, budget: float, seed: int, output_dir: Path) -> Path:
    """Return the expected JSON path for a matheuristic or cold-MIP run."""
    return output_dir / f"{INSTANCE_NAME}_{method_label(method)}_seed{seed}_b{int(budget)}.json"


def result_matches(path: Path, method: str, budget: float, seed: int, threads: int, log_windows: bool) -> bool:
    """Return whether a previous run can be reused."""
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    params = data.get("params", {})
    return (
        data.get("instance") == INSTANCE_NAME
        and data.get("method") == method
        and int(data.get("seed", -1)) == seed
        and abs(float(params.get("budget", -1.0)) - budget) < 1e-9
        and int(params.get("threads", -1)) == threads
        and bool(params.get("log_windows", False)) == log_windows
        and data.get("Z_final") is not None
    )


def params_for(method: str, budget: float, threads: int, log_windows: bool) -> RunParams:
    """Build run parameters for one real order-book job."""
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


def run_solver_job(method: str, budget: float, seed: int, threads: int, log_windows: bool, output_dir: Path) -> Path:
    """Run one cold-MIP or matheuristic job and write its outputs."""
    params = params_for(method, budget, threads, log_windows)
    wall_start = time.perf_counter()
    result = run_matheuristic(INSTANCE_PATH, params, seed)
    output_path = write_result(INSTANCE_PATH, params, seed, result, output_dir=output_dir)
    data = json.loads(output_path.read_text(encoding="utf-8"))
    data["wall_time_total"] = round(time.perf_counter() - wall_start, 3)
    data["real_order_book"] = True
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


def ils_summary_matches(path: Path, n_runs: int, time_limit_s: float) -> bool:
    """Return whether an existing ILS summary satisfies the requested run."""
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return (
        data.get("instance") == INSTANCE_NAME
        and int(data.get("n_runs", 0)) >= n_runs
        and abs(float(data.get("time_limit_s", -1.0)) - time_limit_s) < 1e-9
        and data.get("Z_best") is not None
    )


def run_ils(output_dir: Path, n_runs: int, time_limit_s: float, base_seed: int, workers: int) -> Path:
    """Run ILS v2 for the real order-book instance and return the summary path."""
    run_instance(
        py_path=str(INSTANCE_PATH),
        name=INSTANCE_NAME,
        dataset="Real order book",
        out_dir=str(output_dir),
        mip_bound=None,
        n_runs=n_runs,
        time_limit_s=time_limit_s,
        base_seed=base_seed,
        n_workers=workers,
    )
    return output_dir / f"{INSTANCE_NAME}_summary.json"


def parse_only(tokens: list[str] | None) -> set[str]:
    """Normalize optional job filters."""
    if not tokens:
        return set()
    selected: set[str] = set()
    for token in tokens:
        selected.update(part.strip() for part in token.split(",") if part.strip())
    return selected


def should_run(method: str, budget: float, selected: set[str]) -> bool:
    """Return whether a solver job passes the optional filter."""
    keys = {method, method_label(method), f"{method}:{int(budget)}", f"{method_label(method)}:{int(budget)}"}
    return not selected or bool(keys & selected)


def main(argv: Iterable[str] | None = None) -> int:
    """Run the real order-book suite."""
    parser = argparse.ArgumentParser(description="Run real order-book production jobs.")
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--threads", type=int, default=0)
    parser.add_argument("--ils-runs", type=int, default=10)
    parser.add_argument("--ils-time", type=float, default=3600.0)
    parser.add_argument("--ils-seed", type=int, default=0)
    parser.add_argument("--ils-workers", type=int, default=1)
    parser.add_argument("--only", nargs="*", default=None, help="Filter jobs, e.g. mip:600 rf_fo:3600 ils.")
    parser.add_argument("--skip-ils", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    selected = parse_only(args.only)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for method, budget, log_windows in MATHEURISTIC_JOBS:
        if not should_run(method, budget, selected):
            continue
        out_path = result_path(method, budget, args.seed, args.output_dir)
        if not args.force and result_matches(out_path, method, budget, args.seed, args.threads, log_windows):
            logging.info("SKIP %s @ %.0fs: %s", method, budget, out_path)
            continue
        logging.info("RUN %s %s @ %.0fs", INSTANCE_NAME, method, budget)
        written = run_solver_job(method, budget, args.seed, args.threads, log_windows, args.output_dir)
        logging.info("WROTE %s", written)

    if not args.skip_ils and (not selected or "ils" in selected or "ILS" in selected):
        summary_path = args.output_dir / f"{INSTANCE_NAME}_summary.json"
        if not args.force and ils_summary_matches(summary_path, args.ils_runs, args.ils_time):
            logging.info("SKIP ILS: %s", summary_path)
        else:
            logging.info(
                "RUN %s ILS v2: runs=%d time=%.0fs workers=%d",
                INSTANCE_NAME,
                args.ils_runs,
                args.ils_time,
                args.ils_workers,
            )
            written = run_ils(args.output_dir, args.ils_runs, args.ils_time, args.ils_seed, args.ils_workers)
            logging.info("WROTE %s", written)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
