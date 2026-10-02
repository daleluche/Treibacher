"""Solve PSP instances under the gamma=0 excess-penalty variant.

The variant keeps the process-selection structure of the original MIP but
removes the excess variable from the objective and replaces cumulative demand
balance equalities by lower-bound inequalities:

    cumulative production + shortage >= cumulative demand.

This isolates the effect of the small excess penalty used in the paper model.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
from gamspy import Alias, Container, Equation, Model, Options, Ord, Parameter, Set, Sum, Variable

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.matheuristics.psp_instance import load_instance

RESLIM = 10800
ITERLIM = 10000000
OPTCR = 0.0


def hardware_provenance() -> dict:
    """Collect hardware provenance for reproducible solver outputs."""
    physical = None
    ram_bytes = None
    try:
        import psutil

        physical = psutil.cpu_count(logical=False)
        ram_bytes = int(psutil.virtual_memory().total)
    except Exception:
        pass

    processor_model = None
    if platform.system().lower() == "windows":
        try:
            processor_model = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except Exception:
            processor_model = None

    return {
        "processor": platform.processor(),
        "processor_model": processor_model or platform.processor(),
        "cpu_count_logical": os.cpu_count(),
        "cpu_count_physical": physical,
        "ram_bytes": ram_bytes,
        "platform": platform.platform(),
    }


def parse_solver_version(log_text: str) -> str | None:
    """Extract a compact CPLEX version line from solver output when present."""
    for line in log_text.splitlines():
        if "IBM ILOG CPLEX" in line or line.strip().startswith("Version identifier:"):
            return line.strip()
    return None


def solve_instance(
    instance_path: str | Path,
    output_dir: str | Path | None = None,
    reslim: int = RESLIM,
    threads: int = 0,
    force: bool = False,
) -> Path:
    """Solve one gamma=0 variant and write a JSON result file."""
    instance_path = Path(instance_path).resolve()
    inst = load_instance(instance_path)
    out_dir = Path(output_dir) if output_dir is not None else Path(__file__).resolve().parent / "results_gamma0"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{inst.name}.json"
    if json_path.exists() and not force:
        print(f"[skip] {inst.dataset}/{inst.name}: {json_path} already exists")
        return json_path

    container = Container()
    i_set = Set(container, "I", records=inst.products, description="products")
    j_records = [str(j) for j in range(1, inst.J + 1)]
    t_records = [str(t) for t in range(1, inst.T + 1)]
    j_set = Set(container, "J", records=j_records, description="processes")
    t_set = Set(container, "T", records=t_records, description="periods")
    tl_set = Alias(container, "TL", alias_with=t_set)

    a_records = [
        [inst.products[i], j_records[j], float(inst.A[i, j])]
        for i in range(inst.I)
        for j in range(inst.J)
        if abs(float(inst.A[i, j])) > 0.0
    ]
    d_records = [
        [inst.products[i], t_records[t], float(inst.D[i, t])]
        for i in range(inst.I)
        for t in range(inst.T)
        if abs(float(inst.D[i, t])) > 0.0
    ]
    a_param = Parameter(
        container,
        "A",
        domain=[i_set, j_set],
        records=pd.DataFrame(a_records, columns=["i", "j", "value"]),
        description="production rate",
    )
    d_param = Parameter(
        container,
        "D",
        domain=[i_set, t_set],
        records=pd.DataFrame(d_records, columns=["i", "t", "value"]),
        description="period demand",
    )

    x_var = Variable(container, "X", type="binary", domain=[j_set, t_set], description="selected process")
    f_var = Variable(container, "F", type="positive", domain=[i_set, t_set], description="shortage")
    z_var = Variable(container, "Z", description="objective")

    eq_obj = Equation(container, "EQ_OBJ", description="shortage-only objective")
    eq_dem = Equation(container, "EQ_DEM", domain=[i_set, t_set], description="cumulative demand lower bound")
    eq_prop = Equation(container, "EQ_PROP", domain=[t_set], description="at most one process per period")

    i, j, t, tl = i_set, j_set, t_set, tl_set
    eq_obj[...] = z_var == Sum([i, t], f_var[i, t])
    eq_dem[i, t] = (
        Sum([j, tl], (a_param[i, j] * x_var[j, tl]).where[Ord(tl) <= Ord(t)])
        + f_var[i, t]
        >= Sum(tl, d_param[i, tl].where[Ord(tl) <= Ord(t)])
    )
    eq_prop[t] = Sum(j, x_var[j, t]) <= 1

    model = Model(
        container,
        "PSP_GAMMA0",
        equations=container.getEquations(),
        problem="MIP",
        sense="MIN",
        objective=z_var,
    )

    output = io.StringIO()
    t0 = time.time()
    model.solve(
        solver="CPLEX",
        options=Options(
            relative_optimality_gap=OPTCR,
            iteration_limit=ITERLIM,
            time_limit=float(reslim),
        ),
        solver_options={"tilim": float(reslim), "epgap": OPTCR, "threads": int(threads)},
        output=output,
    )
    wall = time.time() - t0
    log_text = output.getvalue()

    obj = model.objective_value
    bound = model.objective_estimation
    if obj and obj != 0 and bound is not None:
        gap = abs(float(obj) - float(bound)) / abs(float(obj)) * 100.0
    elif obj == 0:
        gap = 0.0
    else:
        gap = None

    x_df = x_var.records
    if x_df is not None:
        x_df = x_df.rename(columns=str.lower)
    sched = []
    if x_df is not None:
        selected = x_df[x_df["level"] >= 0.5][["j", "t"]].copy()
        selected["period_int"] = selected["t"].astype(int)
        sched = [
            {"period": int(row["t"]), "process": int(row["j"])}
            for _, row in selected.sort_values("period_int").iterrows()
        ]

    f_df = f_var.records
    if f_df is not None:
        f_df = f_df.rename(columns=str.lower)
    details = []
    if f_df is not None:
        for _, row in f_df[f_df["level"] > 1e-6].iterrows():
            details.append(
                {
                    "product": row["i"],
                    "period": int(row["t"]),
                    "shortage": round(float(row["level"]), 4),
                    "excess": 0.0,
                }
            )

    result = {
        "instance": inst.name,
        "dataset": inst.dataset,
        "source_instance_py": str(instance_path.relative_to(ROOT)),
        "variant": "gamma0",
        "gamma": 0.0,
        "run_timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "num_periods": inst.T,
        "num_processes": inst.J,
        "num_products": inst.I,
        "num_variables": model.num_variables,
        "num_equations": model.num_equations,
        "num_nonzeros": model.num_nonzeros,
        "num_discrete": model.num_discrete_variables,
        "solver": "CPLEX",
        "optcr": OPTCR,
        "iterlim": ITERLIM,
        "reslim_s": int(reslim),
        "threads": int(threads),
        "optfile_used": False,
        "model_status": str(model.status),
        "solve_status": str(model.solve_status),
        "objective_value": round(float(obj), 6) if obj is not None else None,
        "best_bound": round(float(bound), 6) if bound is not None else None,
        "gap_pct": round(float(gap), 6) if gap is not None else None,
        "wall_time_s": round(wall, 4),
        "algorithm_time_s": round(model.algorithm_time, 4) if model.algorithm_time is not None else None,
        "total_solve_time_s": round(model.total_solve_time, 4) if model.total_solve_time is not None else None,
        "total_solver_time_s": round(model.total_solver_time, 4) if model.total_solver_time is not None else None,
        "model_gen_time_s": round(model.model_generation_time, 4) if model.model_generation_time is not None else None,
        "solve_model_time_s": round(model.solve_model_time, 4) if model.solve_model_time is not None else None,
        "num_nodes_used": model.num_nodes_used,
        "num_iterations": model.num_iterations,
        "num_infeasibilities": model.num_infeasibilities,
        "max_infeasibility": model.max_infeasibility,
        "solver_version": str(model.solver_version) if model.solver_version is not None else parse_solver_version(log_text),
        "hardware": hardware_provenance(),
        "num_periods_scheduled": len(sched),
        "scheduling": sched,
        "product_details": details,
    }
    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)

    log_path = json_path.with_suffix(".log")
    log_path.write_text(log_text, encoding="utf-8")
    print(
        f"[done] {inst.dataset}/{inst.name}: Z={result['objective_value']} "
        f"bound={result['best_bound']} gap={result['gap_pct']}% wall={wall:.1f}s"
    )
    return json_path


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point for one gamma=0 solve."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", required=True, help="Path to the original GAMSPy instance .py file.")
    parser.add_argument("--output-dir", default=None, help="Directory for gamma=0 JSON outputs.")
    parser.add_argument("--reslim", type=int, default=RESLIM, help="CPLEX wall-clock limit in seconds.")
    parser.add_argument("--threads", type=int, default=0, help="CPLEX threads option; 0 lets CPLEX use all.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing result JSON.")
    args = parser.parse_args(argv)
    solve_instance(args.instance, args.output_dir, args.reslim, args.threads, args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
