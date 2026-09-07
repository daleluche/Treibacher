"""
compute_gaps.py
===============
Builds the master comparison table from analysis/output/master_runs.csv.

The Sprint 3 table has one row per instance across the real order book, S,
2X, 3X, 4X, 5X, 8X, and 10X. Best-known solutions (BKS) are computed from CPLEX, ILS, and
matheuristic runs collected in master_runs.csv. GRASP_v1 remains in the raw
master dataset but is excluded from comparison tables because the BKS
safeguard detected legacy evaluator inconsistencies. The legacy Ale_1 record
remains in master_runs.csv for provenance but is outside the paper comparison
set and cannot enter any S-instance BKS.

Run from the repository root:  python analysis/compute_gaps.py
"""
from __future__ import annotations

import math
import os
import sys
import warnings

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "analysis", "output")
EPS = 1e-6
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from analysis.families import BENCHMARK_FAMILY_ORDER, FULL_FAMILY_ORDER, public_benchmark, write_table

warnings.filterwarnings("ignore", message="Mean of empty slice", category=RuntimeWarning)


def pct(num: float, den: float) -> float:
    """Return a percentage with a stable denominator guard."""
    if pd.isna(num) or pd.isna(den):
        return np.nan
    return 100.0 * num / max(abs(den), 1.0)


def best_row(
    runs: pd.DataFrame,
    instance: str,
    methods: list[str] | None = None,
    min_feasible_bound: float | None = None,
) -> pd.Series | None:
    """Return the best row for an instance, optionally restricted by methods."""
    subset = runs[(runs["instance"] == instance) & (runs["method"] != "GRASP_v1")].dropna(subset=["Z"])
    if methods is not None:
        subset = subset[subset["method"].isin(methods)]
    if min_feasible_bound is not None and pd.notna(min_feasible_bound):
        subset = subset[subset["Z"] >= float(min_feasible_bound) - 1e-4]
    if subset.empty:
        return None
    return subset.sort_values(["Z", "time_budget_s", "method", "source_path"], na_position="last").iloc[0]


def get_value(wide: dict[str, pd.DataFrame], method: str, instance: str, column: str) -> float:
    """Read a value from an instance-indexed method table."""
    if method not in wide or instance not in wide[method].index:
        return np.nan
    return wide[method].loc[instance, column]


def source_label(row: pd.Series | None) -> str | None:
    """Return a compact BKS source label."""
    if row is None:
        return None
    path = row.get("source_path")
    if isinstance(path, str) and path:
        return f"{row['method']} | {int(row['time_budget_s']) if pd.notna(row['time_budget_s']) else 'NA'}s | {path}"
    return f"{row['method']} | {int(row['time_budget_s']) if pd.notna(row['time_budget_s']) else 'NA'}s"


def main() -> int:
    runs = pd.read_csv(os.path.join(OUT, "master_runs.csv"))
    runs["Z"] = pd.to_numeric(runs["Z"], errors="coerce")
    inst = pd.read_csv(os.path.join(OUT, "master_instances.csv"))

    wide: dict[str, pd.DataFrame] = {
        m: inst[inst.method == m].set_index("instance")
        for m in inst.method.unique()
    }

    all_instances = (
        runs.dropna(subset=["instance", "dataset"])
        .loc[lambda frame: frame["dataset"].isin(FULL_FAMILY_ORDER)]
        .drop_duplicates("instance")[["dataset", "instance", "T", "J", "I"]]
        .copy()
    )
    all_instances["dataset_rank"] = all_instances["dataset"].map({d: i for i, d in enumerate(FULL_FAMILY_ORDER)})
    all_instances = all_instances.sort_values(["dataset_rank", "instance"])

    mat_methods = sorted(m for m in runs.method.dropna().unique() if str(m).startswith("MAT_"))

    rows = []
    for _, meta in all_instances.iterrows():
        name = meta["instance"]
        ds = meta["dataset"]

        cplex_3h = get_value(wide, "CPLEX22_3h", name, "Z_best")
        cplex_1h = get_value(wide, "CPLEX22_1h", name, "Z_best")
        bound_3h = get_value(wide, "CPLEX22_3h", name, "bound")
        bound_1h = get_value(wide, "CPLEX22_1h", name, "bound")
        status_3h = get_value(wide, "CPLEX22_3h", name, "model_status")
        gap_3h = get_value(wide, "CPLEX22_3h", name, "gap_solver_pct")
        mat_10800_mip = get_value(wide, "MAT_mip_10800s", name, "Z_best")
        mat_10800_bound = get_value(wide, "MAT_mip_10800s", name, "bound")
        mat_10800_gap = get_value(wide, "MAT_mip_10800s", name, "gap_solver_pct")
        mat_10800_status = get_value(wide, "MAT_mip_10800s", name, "model_status")

        cplex_budget = None
        cplex_Z = np.nan
        bound = np.nan
        cplex_gap = np.nan
        cplex_status = None
        if pd.notna(cplex_3h):
            cplex_budget = "3h"
            cplex_Z = cplex_3h
            bound = bound_3h
            cplex_gap = gap_3h
            cplex_status = status_3h
        elif pd.notna(cplex_1h):
            cplex_budget = "1h_fallback"
            cplex_Z = cplex_1h
            bound = bound_1h
            cplex_status = get_value(wide, "CPLEX22_1h", name, "model_status")
        elif pd.notna(mat_10800_mip):
            cplex_budget = "mip_10800s"
            cplex_Z = mat_10800_mip
            bound = mat_10800_bound
            cplex_gap = mat_10800_gap
            cplex_status = mat_10800_status

        ils2_best = get_value(wide, "ILS_v2", name, "Z_best")
        ils2_mean = get_value(wide, "ILS_v2", name, "Z_mean")
        ils2_std = get_value(wide, "ILS_v2", name, "Z_std")
        ils1_best = get_value(wide, "ILS_v1", name, "Z_best")
        mat_600_mip = get_value(wide, "MAT_mip_600s", name, "Z_best")
        mat_600_rf_fo = get_value(wide, "MAT_rf_fo_600s", name, "Z_best")
        mat_600_rf_mip = get_value(wide, "MAT_rf_mip_600s", name, "Z_best")
        mat_3600_mip = get_value(wide, "MAT_mip_3600s", name, "Z_best")
        mat_3600_rf_fo = get_value(wide, "MAT_rf_fo_3600s", name, "Z_best")
        mat_3600_rf_mip = get_value(wide, "MAT_rf_mip_3600s", name, "Z_best")

        bks_row = best_row(runs, name, min_feasible_bound=bound)
        bks = float(bks_row["Z"]) if bks_row is not None else np.nan

        rows.append({
            "dataset": ds,
            "instance": name,
            "T": int(meta["T"]) if pd.notna(meta["T"]) else np.nan,
            "J": int(meta["J"]) if pd.notna(meta["J"]) else np.nan,
            "I": int(meta["I"]) if pd.notna(meta["I"]) else np.nan,
            "cplex_budget_used": cplex_budget,
            "cplex_Z": cplex_Z,
            "cplex_Z_1h": cplex_1h,
            "cplex_bound": bound,
            "cplex_gap_pct": cplex_gap,
            "cplex_status": cplex_status,
            "cplex_mip_600_Z": mat_600_mip,
            "cplex_mip_3600_Z": mat_3600_mip,
            "cplex_mip_10800_Z": mat_10800_mip,
            "cplex_mip_10800_bound": mat_10800_bound,
            "cplex_mip_10800_gap_pct": mat_10800_gap,
            "rf_fo_600_Z": mat_600_rf_fo,
            "rf_mip_600_Z": mat_600_rf_mip,
            "rf_fo_3600_Z": mat_3600_rf_fo,
            "rf_mip_3600_Z": mat_3600_rf_mip,
            "ils2_Z_best": ils2_best,
            "ils2_Z_mean": ils2_mean,
            "ils2_Z_std": ils2_std,
            "ils1_Z_best": ils1_best,
            "BKS": bks,
            "bks_source": source_label(bks_row),
            "gap_ils2_vs_bound_pct": pct(ils2_best - bound, bound),
            "gap_ils2_vs_cplex_primal_pct": pct(ils2_best - cplex_Z, cplex_Z),
            "gap_ils2_vs_BKS_pct": pct(ils2_best - bks, bks),
            "gap_cplex_vs_BKS_pct": pct(cplex_Z - bks, bks),
            "gap_rf_fo_600_vs_BKS_pct": pct(mat_600_rf_fo - bks, bks),
            "gap_rf_mip_600_vs_BKS_pct": pct(mat_600_rf_mip - bks, bks),
            "gap_mip_600_vs_BKS_pct": pct(mat_600_mip - bks, bks),
            "gap_rf_fo_3600_vs_BKS_pct": pct(mat_3600_rf_fo - bks, bks),
            "gap_rf_mip_3600_vs_BKS_pct": pct(mat_3600_rf_mip - bks, bks),
            "gap_mip_3600_vs_BKS_pct": pct(mat_3600_mip - bks, bks),
            "ils2_wins": bool(pd.notna(ils2_best) and pd.notna(cplex_Z) and ils2_best < cplex_Z - EPS),
            "ties": bool(pd.notna(ils2_best) and pd.notna(cplex_Z) and abs(ils2_best - cplex_Z) <= EPS),
        })

    comp = pd.DataFrame(rows).sort_values(
        by=["dataset"],
        key=lambda col: col.map({d: i for i, d in enumerate(FULL_FAMILY_ORDER)}) if col.name == "dataset" else col,
    ).reset_index(drop=True)

    viol = comp[pd.notna(comp["cplex_bound"]) & (comp["BKS"] < comp["cplex_bound"] - 1e-4)]
    if not viol.empty:
        print("FATAL: BKS below available dual bound; check model/evaluator consistency:")
        print(viol[["instance", "BKS", "bks_source", "cplex_bound"]].to_string(index=False))
        return 1

    if len(comp) != 61:
        print(f"FATAL: comparison_table has {len(comp)} rows, expected 61.")
        return 1

    write_table(comp, os.path.join(OUT, "comparison_table.csv"), ["dataset", "instance"])

    def agg(g: pd.DataFrame) -> pd.Series:
        return pd.Series({
            "n": len(g),
            "n_cplex_optimal": (g.cplex_status == "OptimalGlobal").sum(),
            "cplex_gap_mean_pct": g.cplex_gap_pct.mean(),
            "gap_ils2_vs_bound_mean_pct": g.gap_ils2_vs_bound_pct.mean(),
            "gap_ils2_vs_bound_median_pct": g.gap_ils2_vs_bound_pct.median(),
            "gap_ils2_vs_primal_mean_pct": g.gap_ils2_vs_cplex_primal_pct.mean(),
            "gap_ils2_vs_primal_median_pct": g.gap_ils2_vs_cplex_primal_pct.median(),
            "rf_fo_600_gap_mean_pct": g.gap_rf_fo_600_vs_BKS_pct.mean(),
            "rf_fo_3600_gap_mean_pct": g.gap_rf_fo_3600_vs_BKS_pct.mean(),
            "ils2_wins": int(g.ils2_wins.sum()),
            "ties": int(g.ties.sum()),
            "cplex_wins": int((~g.ils2_wins & ~g.ties & g.cplex_Z.notna() & g.ils2_Z_best.notna()).sum()),
        })

    by_ds = public_benchmark(comp).groupby("dataset").apply(agg, include_groups=False).reindex(BENCHMARK_FAMILY_ORDER).reset_index()
    write_table(by_ds, os.path.join(OUT, "comparison_by_dataset.csv"), ["dataset"])

    print("=" * 88)
    print("COMPARISON BY DATASET — global BKS includes CPLEX, ILS, and matheuristics")
    print("=" * 88)
    print(by_ds.round(3).to_string(index=False))
    source_8x4 = comp.loc[comp.instance == "IncT8x_4", ["BKS", "bks_source"]]
    print("\nIncT8x_4 BKS audit:")
    print(source_8x4.to_string(index=False))
    print("All consistency checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
