"""
Run GRASP+TS+PR on all PSP instances (50 .gms files x 10 runs each).

Usage:
    python run_grasp_all.py [--time 1800] [--runs 10] [--workers N]
                            [--datasets 2X 3X 4X 5X Real]
                            [--seed 42] [--instance NAME]

Each run produces:
    GRASP/{dataset}/results/{instance}_run{k:02d}.json

After all runs for an instance complete:
    GRASP/{dataset}/results/{instance}_summary.json

Consolidated table:
    GRASP/results_summary.csv

Resumable: existing run JSONs are skipped on re-launch.
"""

import argparse
import csv
import json
import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from statistics import mean, stdev
from typing import Optional

logging.basicConfig(
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

HERE = Path(__file__).parent

def _find_gms_root():
    if "GMS_ROOT" in os.environ:
        return Path(os.environ["GMS_ROOT"])
    # Explicit known path (CORSAIR drive, sibling of the OneDrive Documentos tree)
    _known = HERE.parents[4] / "CORSAIR" / "GRASP_PathRelink_2024" / "GAMS" / "GMS"
    if _known.is_dir() and (_known / "Real").is_dir():
        return _known
    # Generic search: walk up from HERE looking for a GMS/ sibling with Real/ inside
    for ancestor in [HERE.parent, HERE.parent.parent, HERE.parent.parent.parent,
                     HERE.parent.parent.parent.parent]:
        candidate = ancestor / "GMS"
        if candidate.is_dir() and (candidate / "Real").is_dir():
            return candidate
    return HERE.parent / "GMS"   # last-resort (will warn at runtime if not found)

GMS_ROOT    = _find_gms_root()
RESULT_ROOT = HERE

DS_GMS_FOLDER = {"2X":"2X","3X":"3X","4X":"4X","5X":"5X","Real":"Real"}


def load_mip_bounds(grasp_root):
    bounds = {}
    gamspy_root = grasp_root.parent / "GAMSPy"
    if not gamspy_root.is_dir():
        return bounds
    for ds_dir in gamspy_root.iterdir():
        results_dir = ds_dir / "results"
        if not results_dir.is_dir():
            continue
        for jf in results_dir.glob("*.json"):
            try:
                data = json.loads(jf.read_text())
                name = data.get("instance") or jf.stem
                bb   = data.get("best_bound")
                if bb is not None:
                    bounds[name] = float(bb)
            except Exception:
                pass
    return bounds


def _run_job(job):
    """Worker: one GRASP run. Top-level so it is picklable on Windows."""
    sys.path.insert(0, str(Path(__file__).parent))
    from grasp_psp import load_instance, run_grasp

    gms_path   = Path(job["gms_path"])
    inst       = load_instance(gms_path, gms_path.stem, job["dataset"])
    result     = run_grasp(
        inst,
        time_limit_s = job["time_limit"],
        run_id       = job["run_id"],
        seed         = job["seed"],
        mip_bound    = job["mip_bound"],
    )

    d = dict(
        instance     = result.instance,
        dataset      = result.dataset,
        run_id       = result.run_id,
        seed         = result.seed,
        objective    = result.objective,
        shortage     = result.shortage,
        excess       = result.excess,
        gap_vs_mip   = result.gap_vs_mip,
        time_to_best = result.time_to_best,
        total_time   = result.total_time,
        iterations   = result.iterations,
        improvements = result.improvements,
        scheduling   = result.scheduling,
        T=inst.T, J=inst.J, I=inst.I,
    )
    out = Path(job["out_path"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(d, indent=2))
    return d


def _write_instance_summary(inst_name, dataset, run_results, result_dir, mip_bound):
    objectives = [r["objective"]    for r in run_results]
    t2bests    = [r["time_to_best"] for r in run_results]
    iters_list = [r["iterations"]   for r in run_results]
    best_run   = min(run_results, key=lambda r: r["objective"])
    summary = dict(
        instance        = inst_name,
        dataset         = dataset,
        T               = run_results[0].get("T", 0),
        J               = run_results[0].get("J", 0),
        I               = run_results[0].get("I", 0),
        n_runs          = len(run_results),
        Z_best          = round(min(objectives), 6),
        Z_mean          = round(mean(objectives), 6),
        Z_std           = round(stdev(objectives), 6) if len(objectives) > 1 else 0.0,
        Z_worst         = round(max(objectives), 6),
        t2best_best     = round(min(t2bests), 3),
        t2best_mean     = round(mean(t2bests), 3),
        iters_mean      = round(mean(iters_list), 1),
        mip_bound       = mip_bound,
        gap_best_vs_mip = best_run["gap_vs_mip"],
    )
    (result_dir / f"{inst_name}_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--time",     type=float, default=1800.0)
    parser.add_argument("--runs",     type=int,   default=10)
    parser.add_argument("--workers",  type=int,   default=max(1, os.cpu_count() - 1))
    parser.add_argument("--datasets", nargs="+",  default=list(DS_GMS_FOLDER.keys()))
    parser.add_argument("--seed",     type=int,   default=42)
    parser.add_argument("--instance", type=str,   default=None)
    args = parser.parse_args()

    total_jobs = args.runs * sum(
        len(list((GMS_ROOT / DS_GMS_FOLDER[d]).glob("*.gms")))
        for d in args.datasets if (GMS_ROOT / DS_GMS_FOLDER.get(d,d)).is_dir()
    )
    wall_h = total_jobs * args.time / 3600 / args.workers
    logger.info("GRASP+TS+PR -- Process Selection Problem")
    logger.info(f"  time/run={args.time:.0f}s  runs={args.runs}  workers={args.workers}")
    logger.info(f"  ~{total_jobs} jobs  est. wall time ~{wall_h:.1f}h  (GMS: {GMS_ROOT})")

    mip_bounds = load_mip_bounds(RESULT_ROOT)
    logger.info(f"  Loaded {len(mip_bounds)} MIP bounds from GAMSPy results")

    rng  = __import__("random").Random(args.seed)
    jobs = []

    for ds in args.datasets:
        gms_dir    = GMS_ROOT / DS_GMS_FOLDER.get(ds, ds)
        result_dir = RESULT_ROOT / ds / "results"
        result_dir.mkdir(parents=True, exist_ok=True)
        if not gms_dir.is_dir():
            logger.warning(f"GMS folder not found: {gms_dir}"); continue
        for gms_path in sorted(gms_dir.glob("*.gms")):
            inst_name = gms_path.stem
            if args.instance and inst_name != args.instance:
                continue
            mip_bound = mip_bounds.get(inst_name)
            for k in range(1, args.runs + 1):
                out_path = result_dir / f"{inst_name}_run{k:02d}.json"
                if out_path.exists():
                    logger.info(f"  SKIP {inst_name} run {k:02d}")
                    continue
                jobs.append(dict(
                    gms_path   = str(gms_path),
                    dataset    = ds,
                    run_id     = k,
                    seed       = rng.randint(1, 2**31 - 1),
                    time_limit = args.time,
                    mip_bound  = mip_bound,
                    out_path   = str(out_path),
                ))

    logger.info(f"\n  Submitting {len(jobs)} pending jobs ...")

    completed = {}
    # Pre-load already-finished runs
    for ds in args.datasets:
        result_dir = RESULT_ROOT / ds / "results"
        if not result_dir.is_dir():
            continue
        for jf in sorted(result_dir.glob("*_run??.json")):
            try:
                d = json.loads(jf.read_text())
                completed.setdefault(d["instance"], []).append(d)
            except Exception:
                pass

    done_count = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_run_job, job): job for job in jobs}
        for future in as_completed(futures):
            job = futures[future]
            inst_name = Path(job["gms_path"]).stem
            try:
                d = future.result()
                completed.setdefault(inst_name, []).append(d)
                done_count += 1
                gap_str = f"  gap={d['gap_vs_mip']:.2f}%" if d["gap_vs_mip"] is not None else ""
                logger.info(
                    f"  [{done_count}/{len(jobs)}] {inst_name} run{d['run_id']:02d} "
                    f"Z={d['objective']:.3f}  t2b={d['time_to_best']:.1f}s"
                    f"  iters={d['iterations']}{gap_str}"
                )
            except Exception as exc:
                logger.error(f"  FAILED {inst_name} run {job['run_id']:02d}: {exc}", exc_info=True)

    # Per-instance summaries + consolidated CSV
    all_summaries = []
    for ds in args.datasets:
        result_dir = RESULT_ROOT / ds / "results"
        gms_dir    = GMS_ROOT / DS_GMS_FOLDER.get(ds, ds)
        if not gms_dir.is_dir():
            continue
        for gms_path in sorted(gms_dir.glob("*.gms")):
            inst_name = gms_path.stem
            if args.instance and inst_name != args.instance:
                continue
            runs_done = completed.get(inst_name, [])
            if not runs_done:
                continue
            mip_bound = mip_bounds.get(inst_name)
            summary   = _write_instance_summary(inst_name, ds, runs_done, result_dir, mip_bound)
            all_summaries.append(summary)
            gap_s = f"  gap={summary['gap_best_vs_mip']:.2f}%" if summary["gap_best_vs_mip"] else ""
            logger.info(
                f"  {ds:5s} {inst_name:14s} "
                f"Z_best={summary['Z_best']:.3f}  Z_mean={summary['Z_mean']:.3f}"
                f"  Z_std={summary['Z_std']:.3f}{gap_s}"
            )

    if all_summaries:
        csv_path = RESULT_ROOT / "results_summary.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_summaries[0].keys()))
            writer.writeheader()
            writer.writerows(all_summaries)
        logger.info(f"\nCSV: {csv_path}")

    logger.info("Done.")


if __name__ == "__main__":
    main()
