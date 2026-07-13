"""
build_master_dataset.py
=======================
Consolidates all computational results in the Treibacher repository into
two tidy datasets:

  analysis/output/master_runs.csv       one row per run (exact or heuristic)
  analysis/output/master_instances.csv  one row per (instance x method)

Methods:
  CPLEX22_1h  experiments/GAMSPy/<ds>/results/*.json          (reslim_s = 3600)
  CPLEX22_3h  experiments/GAMSPy/<ds>/results_3horas/*.json   (reslim_s = 10800)
  GRASP_v1    experiments/GRASP/<ds>/results/*_run*.json      (~1800 s budget)
  ILS_v1      experiments/GRASP/results_ils/*_run*.json       (~1800 s budget)
  ILS_v2      experiments/GRASP/results_ils_v2/*_run*.json    (3600 s budget)

Time budgets are read from JSON fields (reslim_s / time_limit_s) when
available; otherwise inferred as the ceiling of observed total_time.

Run from the repository root:  python analysis/build_master_dataset.py
"""
from __future__ import annotations

import glob
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from experiments.matheuristics.psp_instance import load_instance

OUT = os.path.join(ROOT, "analysis", "output")
os.makedirs(OUT, exist_ok=True)

DATASETS = ["Real", "2X", "3X", "4X", "5X", "8X", "10X"]
EXACT_DATASETS = ["Real", "2X", "3X", "4X", "5X"]
EPS = 1e-6


def _load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _method_label(method: str, budget: float | None) -> str:
    """Return a stable method label that preserves the time budget."""
    safe = str(method).replace("+", "_").replace("-", "_")
    if budget is None or math.isnan(float(budget)):
        return f"MAT_{safe}"
    return f"MAT_{safe}_{int(round(float(budget)))}s"


def instance_metadata() -> dict[str, dict]:
    """Load T, J, and I metadata from GAMSPy instance scripts."""
    meta: dict[str, dict] = {}
    for dataset in DATASETS:
        for path in sorted((Path(ROOT) / "experiments" / "GAMSPy" / dataset).glob("*.py")):
            inst = load_instance(path)
            meta[inst.name] = {
                "dataset": inst.dataset,
                "T": inst.T,
                "J": inst.J,
                "I": inst.I,
            }
    return meta


# --------------------------------------------------------------------------- #
# 1. Exact runs (GAMSPy / CPLEX 22)
# --------------------------------------------------------------------------- #
def collect_exact() -> list[dict]:
    rows = []
    for ds in EXACT_DATASETS:
        for folder, method in [("results", "CPLEX22_1h"),
                               ("results_3horas", "CPLEX22_3h")]:
            for f in sorted(glob.glob(
                    os.path.join(ROOT, "experiments", "GAMSPy", ds, folder, "*.json"))):
                d = _load(f)
                rows.append({
                    "method": method,
                    "dataset": ds,
                    "instance": d["instance"],
                    "run_id": 1,
                    "seed": None,
                    "Z": d.get("objective_value"),
                    "bound": d.get("best_bound"),
                    "gap_solver_pct": d.get("gap_pct"),
                    "time_to_best_s": None,
                    "total_time_s": d.get("wall_time_s"),
                    "time_budget_s": d.get("reslim_s"),
                    "model_status": str(d.get("model_status", "")).replace("ModelStatus.", ""),
                    "iterations": d.get("num_iterations"),
                    "T": d.get("num_periods"),
                    "J": d.get("num_processes"),
                    "I": d.get("num_products"),
                })
    return rows


# --------------------------------------------------------------------------- #
# 2. Heuristic runs
# --------------------------------------------------------------------------- #
HEURISTIC_SOURCES = [
    # (method, glob pattern for run files, glob pattern for summary files)
    ("GRASP_v1", "experiments/GRASP/*/results/*_run*.json",
     "experiments/GRASP/*/results/*_summary.json"),
    ("ILS_v1", "experiments/GRASP/results_ils/*_run*.json",
     "experiments/GRASP/results_ils/*_summary.json"),
    ("ILS_v2", "experiments/GRASP/results_ils_v2/*_run*.json",
     "experiments/GRASP/results_ils_v2/*_summary.json"),
]


def collect_heuristics() -> tuple[list[dict], dict]:
    rows = []
    budgets: dict[str, float] = {}

    for method, run_pat, sum_pat in HEURISTIC_SOURCES:
        # explicit budget from summaries when available
        budget = None
        for f in glob.glob(os.path.join(ROOT, sum_pat)):
            d = _load(f)
            if d.get("time_limit_s"):
                budget = float(d["time_limit_s"])
                break

        observed_max = 0.0
        for f in sorted(glob.glob(os.path.join(ROOT, run_pat))):
            d = _load(f)
            observed_max = max(observed_max, float(d.get("total_time", 0.0)))
            rows.append({
                "method": method,
                "dataset": d.get("dataset"),
                "instance": d.get("instance"),
                "run_id": d.get("run_id"),
                "seed": d.get("seed"),
                "Z": d.get("objective"),
                "bound": None,
                "gap_solver_pct": None,
                "time_to_best_s": d.get("time_to_best"),
                "total_time_s": d.get("total_time"),
                "time_budget_s": budget,     # filled below if None
                "model_status": None,
                "iterations": d.get("iterations"),
                "T": d.get("T"),
                "J": d.get("J"),
                "I": d.get("I"),
            })
        if budget is None:
            # infer: round observed max up to nearest 100 s
            budget = math.ceil(observed_max / 100.0) * 100.0
            for r in rows:
                if r["method"] == method and r["time_budget_s"] is None:
                    r["time_budget_s"] = budget
        budgets[method] = budget
    return rows, budgets


# --------------------------------------------------------------------------- #
# 3. Matheuristic runs
# --------------------------------------------------------------------------- #
MATHEURISTIC_RESULT_DIRS = [
    "results_pilot",
    "results_tuning",
    "results_short_budget",
    "results_short_budget_v2",
    "results_scale_8x10x",
    "results_scale_8x10x_v2",
    os.path.join("results_production", "b600"),
    os.path.join("results_production", "a3600"),
    os.path.join("results_production", "c_seeds"),
]


def collect_matheuristics(meta: dict[str, dict]) -> list[dict]:
    """Collect matheuristic JSON outputs from all sprint result folders."""
    rows = []
    base = Path(ROOT) / "experiments" / "matheuristics"
    for rel_dir in MATHEURISTIC_RESULT_DIRS:
        directory = base / rel_dir
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            data = _load(str(path))
            if "Z_final" not in data or "method" not in data:
                continue
            params = data.get("params", {})
            budget = float(params.get("budget", np.nan))
            instance = data.get("instance")
            inst_meta = meta.get(instance, {})
            method = _method_label(data.get("method"), budget)
            improvements = data.get("improvements") or []
            time_to_best = None
            if improvements:
                best = min(improvements, key=lambda item: item.get("Z", math.inf))
                time_to_best = best.get("time_s")
            rows.append({
                "method": method,
                "dataset": data.get("dataset") or inst_meta.get("dataset"),
                "instance": instance,
                "run_id": data.get("run_id") or path.stem,
                "seed": data.get("seed"),
                "Z": data.get("Z_final"),
                "bound": data.get("dual_bound"),
                "gap_solver_pct": data.get("gap_solver_pct"),
                "time_to_best_s": time_to_best,
                "total_time_s": data.get("wall_time_total"),
                "time_budget_s": budget,
                "model_status": data.get("status"),
                "iterations": None,
                "T": inst_meta.get("T"),
                "J": inst_meta.get("J"),
                "I": inst_meta.get("I"),
                "source_path": str(path.relative_to(Path(ROOT))),
                "raw_method": data.get("method"),
                "construction_used": data.get("construction_used"),
                "Z_construction": data.get("construction", {}).get("Z")
                if isinstance(data.get("construction"), dict)
                else data.get("Z_rf"),
                "rf_wall_time_s": data.get("rf_wall_time_s"),
            })
    return rows


# --------------------------------------------------------------------------- #
# 3. Build, validate, aggregate
# --------------------------------------------------------------------------- #
def main() -> int:
    meta = instance_metadata()
    exact = collect_exact()
    heur, budgets = collect_heuristics()
    matheur = collect_matheuristics(meta)
    runs = pd.DataFrame(exact + heur + matheur)

    runs = runs.sort_values(["method", "dataset", "instance", "run_id"]).reset_index(drop=True)
    runs.to_csv(os.path.join(OUT, "master_runs.csv"), index=False)

    # instance-level aggregation
    def agg(g: pd.DataFrame) -> pd.Series:
        return pd.Series({
            "n_runs": len(g),
            "Z_best": g["Z"].min(),
            "Z_mean": g["Z"].mean(),
            "Z_std": g["Z"].std(ddof=1) if len(g) > 1 else 0.0,
            "Z_worst": g["Z"].max(),
            "t2b_mean": g["time_to_best_s"].mean(),
            "total_time_mean": g["total_time_s"].mean(),
            "time_budget_s": g["time_budget_s"].max(),
            "bound": g["bound"].max(),
            "gap_solver_pct": g["gap_solver_pct"].max(),
            "model_status": g["model_status"].dropna().iloc[0] if g["model_status"].notna().any() else None,
            "T": g["T"].dropna().max(),
            "J": g["J"].dropna().max(),
            "I": g["I"].dropna().max(),
            "source_path": g["source_path"].dropna().iloc[0] if "source_path" in g and g["source_path"].notna().any() else None,
            "raw_method": g["raw_method"].dropna().iloc[0] if "raw_method" in g and g["raw_method"].notna().any() else None,
        })

    inst = (runs.groupby(["method", "dataset", "instance"])
                .apply(agg, include_groups=False).reset_index())
    inst.to_csv(os.path.join(OUT, "master_instances.csv"), index=False)

    # ------------------------------------------------------------------ #
    # Validation report
    # ------------------------------------------------------------------ #
    print("=" * 72)
    print("VALIDATION REPORT — master dataset")
    print("=" * 72)
    ok = True

    for method in ["CPLEX22_3h", "ILS_v2"]:
        n = inst.loc[inst.method == method, "instance"].nunique()
        expected = 50
        flag = "OK" if n == expected else "FAIL"
        if flag == "FAIL":
            ok = False
        print(f"[{flag}] {method}: {n} distinct instances (expected {expected})")

    n_v2 = len(runs[runs.method == "ILS_v2"])
    flag = "OK" if n_v2 == 500 else "FAIL"
    ok &= (n_v2 == 500)
    print(f"[{flag}] ILS_v2 runs: {n_v2} (expected 500)")

    bad_z = runs[(runs.Z.isna()) | (runs.Z < -EPS)]
    flag = "OK" if bad_z.empty else "FAIL"
    ok &= bad_z.empty
    print(f"[{flag}] null/negative Z values: {len(bad_z)}")

    ex = runs[runs.method.str.startswith("CPLEX")]
    viol = ex[ex.bound > ex.Z + EPS]
    flag = "OK" if viol.empty else "FAIL"
    ok &= viol.empty
    print(f"[{flag}] exact rows with bound > Z: {len(viol)}")

    # sanity: heuristic best >= dual bound of proven-optimal instances
    opt = inst[(inst.method == "CPLEX22_3h") & (inst.model_status == "OptimalGlobal")]
    v2 = inst[inst.method == "ILS_v2"].set_index("instance")
    n_viol = 0
    for _, r in opt.iterrows():
        if r.instance in v2.index and v2.loc[r.instance, "Z_best"] < r.bound - 1e-4:
            n_viol += 1
            print(f"    !! {r.instance}: ILS_v2 Z_best {v2.loc[r.instance, 'Z_best']:.3f}"
                  f" < optimal bound {r.bound:.3f}")
    flag = "OK" if n_viol == 0 else "FAIL"
    ok &= (n_viol == 0)
    print(f"[{flag}] ILS_v2 Z_best below proven-optimal bound: {n_viol} instances")

    n_mat = len(runs[runs.method.astype(str).str.startswith("MAT_")])
    flag = "OK" if n_mat > 0 else "FAIL"
    ok &= (n_mat > 0)
    print(f"[{flag}] matheuristic rows collected: {n_mat}")

    print("\nInferred/declared time budgets (s):", budgets)

    print("\nSummary: n runs and mean Z by method x dataset")
    piv = runs.pivot_table(index="method", columns="dataset", values="Z",
                           aggfunc=["count", "mean"])
    print(piv.round(1).to_string())

    print("\n" + ("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
