"""
compute_gaps.py
===============
Builds the master comparison table from analysis/output/master_instances.csv.

Outputs:
  analysis/output/comparison_table.csv       one row per instance
  analysis/output/comparison_by_dataset.csv  aggregates per dataset

Gap definitions (percent):
  gap_ils2_vs_bound   = 100 * (ILS2_best - dual_bound) / max(dual_bound, 1)
  gap_ils2_vs_primal  = 100 * (ILS2_best - CPLEX_Z)    / max(CPLEX_Z, 1)
  gap_ils2_vs_BKS     = 100 * (ILS2_best - BKS)        / max(BKS, 1)

CPLEX reference is the 3 h run. The 1 h primal is also reported and included
as a best-known-solution candidate because longer runs can occasionally return
a slightly worse incumbent.

Run from the repository root:  python analysis/compute_gaps.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "analysis", "output")
EPS = 1e-6


def pct(num: float, den: float) -> float:
    return 100.0 * num / max(abs(den), 1.0)


def main() -> int:
    inst = pd.read_csv(os.path.join(OUT, "master_instances.csv"))

    wide: dict[str, pd.DataFrame] = {
        m: inst[inst.method == m].set_index("instance")
        for m in inst.method.unique()
    }

    rows = []
    all_instances = sorted(inst.instance.unique())
    for name in all_instances:
        meta_src = wide["ILS_v2"] if name in wide["ILS_v2"].index else wide["CPLEX22_1h"]
        meta = meta_src.loc[name]
        ds = meta["dataset"]

        # --- CPLEX reference (3 h preferred, 1 h fallback) ---------------- #
        if name in wide["CPLEX22_3h"].index:
            cx = wide["CPLEX22_3h"].loc[name]
            cplex_budget = "3h"
        elif name in wide["CPLEX22_1h"].index:
            cx = wide["CPLEX22_1h"].loc[name]
            cplex_budget = "1h_fallback"
        else:
            cx, cplex_budget = None, None

        cplex_Z = cx["Z_best"] if cx is not None else np.nan
        bound = cx["bound"] if cx is not None else np.nan
        cplex_gap = cx["gap_solver_pct"] if cx is not None else np.nan
        status = cx["model_status"] if cx is not None else None
        cplex_Z_1h = (
            wide["CPLEX22_1h"].loc[name, "Z_best"]
            if "CPLEX22_1h" in wide and name in wide["CPLEX22_1h"].index
            else np.nan
        )

        # --- heuristics ---------------------------------------------------- #
        def get(m: str, col: str) -> float:
            return wide[m].loc[name, col] if name in wide[m].index else np.nan

        ils2_best, ils2_mean, ils2_std = (get("ILS_v2", c) for c in
                                          ("Z_best", "Z_mean", "Z_std"))
        ils1_best = get("ILS_v1", "Z_best")
        grasp1_best = get("GRASP_v1", "Z_best")

        # --- BKS ------------------------------------------------------------ #
        candidates = [v for v in (cplex_Z, cplex_Z_1h, ils2_best, ils1_best, grasp1_best)
                      if not np.isnan(v)]
        bks = min(candidates)

        rows.append({
            "dataset": ds, "instance": name,
            "T": int(meta["T"]), "J": int(meta["J"]), "I": int(meta["I"]),
            "cplex_budget_used": cplex_budget,
            "cplex_Z": cplex_Z, "cplex_Z_1h": cplex_Z_1h, "cplex_bound": bound,
            "cplex_gap_pct": cplex_gap, "cplex_status": status,
            "ils2_Z_best": ils2_best, "ils2_Z_mean": ils2_mean,
            "ils2_Z_std": ils2_std,
            "grasp1_Z_best": grasp1_best, "ils1_Z_best": ils1_best,
            "BKS": bks,
            "gap_ils2_vs_bound_pct": pct(ils2_best - bound, bound),
            "gap_ils2_vs_cplex_primal_pct": pct(ils2_best - cplex_Z, cplex_Z),
            "gap_ils2_vs_BKS_pct": pct(ils2_best - bks, bks),
            "gap_cplex_vs_BKS_pct": pct(cplex_Z - bks, bks),
            "ils2_wins": bool(ils2_best < cplex_Z - EPS),
            "ties": bool(abs(ils2_best - cplex_Z) <= EPS),
        })

    comp = pd.DataFrame(rows).sort_values(["dataset", "instance"]).reset_index(drop=True)

    # ---------------- consistency guard ---------------------------------- #
    viol = comp[comp.ils2_Z_best < comp.cplex_bound - 1e-4]
    if not viol.empty:
        print("FATAL: heuristic solution below dual bound — model/evaluator mismatch:")
        print(viol[["instance", "ils2_Z_best", "cplex_bound"]].to_string(index=False))
        return 1
    neg = comp[comp.gap_ils2_vs_BKS_pct < -1e-9]
    if not neg.empty:
        print("FATAL: negative gap vs BKS (definition error).")
        return 1

    comp.to_csv(os.path.join(OUT, "comparison_table.csv"), index=False)

    # ---------------- dataset aggregates ---------------------------------- #
    def agg(g: pd.DataFrame) -> pd.Series:
        return pd.Series({
            "n": len(g),
            "n_cplex_optimal": (g.cplex_status == "OptimalGlobal").sum(),
            "cplex_gap_mean_pct": g.cplex_gap_pct.mean(),
            "gap_ils2_vs_bound_mean_pct": g.gap_ils2_vs_bound_pct.mean(),
            "gap_ils2_vs_bound_median_pct": g.gap_ils2_vs_bound_pct.median(),
            "gap_ils2_vs_primal_mean_pct": g.gap_ils2_vs_cplex_primal_pct.mean(),
            "gap_ils2_vs_primal_median_pct": g.gap_ils2_vs_cplex_primal_pct.median(),
            "ils2_wins": int(g.ils2_wins.sum()),
            "ties": int(g.ties.sum()),
            "cplex_wins": int((~g.ils2_wins & ~g.ties).sum()),
        })

    by_ds = (comp.groupby("dataset").apply(agg, include_groups=False)
                 .reindex(["Real", "2X", "3X", "4X", "5X"]).reset_index())
    by_ds.to_csv(os.path.join(OUT, "comparison_by_dataset.csv"), index=False)

    print("=" * 88)
    print("COMPARISON BY DATASET — ILS v2 (best of 10 x 3600 s) vs CPLEX 22 (3 h)")
    print("=" * 88)
    print(by_ds.round(2).to_string(index=False))
    wins, ties_ = int(comp.ils2_wins.sum()), int(comp.ties.sum())
    print(f"\nOverall: ILS v2 wins {wins}, ties {ties_}, "
          f"loses {len(comp) - wins - ties_} of {len(comp)} instances "
          f"(vs CPLEX primal).")
    print("All consistency checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
