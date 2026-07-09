"""Relax-and-fix and fix-and-optimize matheuristics for the PSP MFP model."""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import math
import os
import platform
import random
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from gamspy import Alias, Container, Equation, Model, Options, Ord, Parameter, Set, Sum, Variable

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from experiments.matheuristics.psp_instance import PSPInstance, evaluate, load_instance

RESULTS_DIR = Path(__file__).resolve().parent / "results_pilot"
EPS = 1e-6
MIN_RF_WINDOW_TL = 5.0


@dataclass(frozen=True)
class RunParams:
    """Configuration for one RF/FO run."""

    budget: float
    sigma: int
    step: int
    omega: int
    step_fo: int
    tl_rf: float
    tl_fo: float
    method: str
    start_from: str | None
    threads: int
    output_suffix: str | None
    log_windows: bool = False


@dataclass
class MatheuristicResult:
    """Summary of one RF/FO run."""

    schedule: list[int]
    construction: str
    z_greedy: float | None
    greedy_wall_time: float
    z_final: float
    z_best_overall: float
    shortage: float
    excess: float
    z_rf: float
    improvements: list[dict]
    rf_windows: int
    rf_wall_time: float
    rf_validation_checks: list[dict]
    fo_accepts: int
    fo_sweeps_completed: int
    warm_start_checked: bool
    warm_start_log_has_mipstart: bool
    warm_start_log_excerpt: str | None
    warm_start_log_evidence_lines: list[str]
    rf_window_diag: list[dict]
    window_log_rows: list[dict]
    instrumentation_wall_time: float
    solver_version: str | None
    hardware: dict


class PSPGamspyModel:
    """Single GAMSPy model with X and XR controlled by bounds."""

    def __init__(self, inst: PSPInstance, threads: int = 0) -> None:
        self.inst = inst
        self.threads = threads
        self.solver_version: str | None = None
        self.container = Container()
        self.i_records = inst.products
        self.j_records = [str(j) for j in range(1, inst.J + 1)]
        self.t_records = [str(t) for t in range(1, inst.T + 1)]

        self.I = Set(self.container, "I", records=self.i_records, description="products")
        self.J = Set(self.container, "J", records=self.j_records, description="processes")
        self.T = Set(self.container, "T", records=self.t_records, description="periods")
        self.TL = Alias(self.container, "TL", alias_with=self.T)

        a_records = [
            [self.i_records[i], self.j_records[j], float(inst.A[i, j])]
            for i in range(inst.I)
            for j in range(inst.J)
            if abs(inst.A[i, j]) > 0.0
        ]
        d_records = [
            [self.i_records[i], self.t_records[t], float(inst.D[i, t])]
            for i in range(inst.I)
            for t in range(inst.T)
            if abs(inst.D[i, t]) > 0.0
        ]
        self.A = Parameter(
            self.container,
            "A",
            domain=[self.I, self.J],
            records=pd.DataFrame(a_records, columns=["i", "j", "value"]),
            description="production rate",
        )
        self.D = Parameter(
            self.container,
            "D",
            domain=[self.I, self.T],
            records=pd.DataFrame(d_records, columns=["i", "t", "value"]),
            description="period demand",
        )

        self.X = Variable(self.container, "X", type="binary", domain=[self.J, self.T])
        self.XR = Variable(self.container, "XR", type="positive", domain=[self.J, self.T])
        self.E = Variable(self.container, "E", type="positive", domain=[self.I, self.T])
        self.F = Variable(self.container, "F", type="positive", domain=[self.I, self.T])
        self.Z = Variable(self.container, "Z")

        self.EQ_OBJ = Equation(self.container, "EQ_OBJ")
        self.EQ_DEM = Equation(self.container, "EQ_DEM", domain=[self.I, self.T])
        self.EQ_PROP = Equation(self.container, "EQ_PROP", domain=[self.T])

        i, j, t, tl = self.I, self.J, self.T, self.TL
        self.EQ_OBJ[...] = self.Z == Sum([i, t], self.F[i, t] + 0.001 * self.E[i, t])
        self.EQ_DEM[i, t] = (
            Sum([j, tl], (self.A[i, j] * (self.X[j, tl] + self.XR[j, tl])).where[Ord(tl) <= Ord(t)])
            + self.F[i, t]
            - self.E[i, t]
            == Sum(tl, self.D[i, tl].where[Ord(tl) <= Ord(t)])
        )
        self.EQ_PROP[t] = Sum(j, self.X[j, t] + self.XR[j, t]) <= 1
        self.model = Model(
            self.container,
            "RF_FO_PSP",
            equations=self.container.getEquations(),
            problem="MIP",
            sense="MIN",
            objective=self.Z,
        )
        self._initialize_bounds()

    def _initialize_bounds(self) -> None:
        """Set initial variable bounds before the first solve."""
        zero = np.zeros((self.inst.J, self.inst.T), dtype=np.float64)
        one = np.ones((self.inst.J, self.inst.T), dtype=np.float64)
        self._set_variable_records(self.X, zero, zero, one)
        self._set_variable_records(self.XR, zero, zero, one)

    def _set_variable_records(
        self,
        variable: Variable,
        level: np.ndarray,
        lower: np.ndarray,
        upper: np.ndarray,
    ) -> None:
        """Bulk-update variable records for fast bound changes."""
        records = []
        for period in range(self.inst.T):
            for process in range(self.inst.J):
                records.append(
                    [
                        self.j_records[process],
                        self.t_records[period],
                        float(level[process, period]),
                        0.0,
                        float(lower[process, period]),
                        float(upper[process, period]),
                        1.0,
                    ]
                )
        variable.setRecords(
            pd.DataFrame(
                records,
                columns=["j", "t", "level", "marginal", "lower", "upper", "scale"],
            )
        )

    def _incumbent_matrix(self, incumbent: np.ndarray) -> np.ndarray:
        """Return a J x T binary matrix for a 1-indexed incumbent schedule."""
        matrix = np.zeros((self.inst.J, self.inst.T), dtype=np.float64)
        for period, process in enumerate(incumbent):
            if int(process) > 0:
                matrix[int(process) - 1, period] = 1.0
        return matrix

    def set_rf_regimes(self, fixed_until: int, window: set[int], incumbent: np.ndarray) -> None:
        """Apply RF relaxed, binary, and fixed period regimes by bounds."""
        x_level = self._incumbent_matrix(incumbent)
        x_lower = np.zeros((self.inst.J, self.inst.T), dtype=np.float64)
        x_upper = np.zeros((self.inst.J, self.inst.T), dtype=np.float64)
        xr_level = np.zeros((self.inst.J, self.inst.T), dtype=np.float64)
        xr_lower = np.zeros((self.inst.J, self.inst.T), dtype=np.float64)
        xr_upper = np.zeros((self.inst.J, self.inst.T), dtype=np.float64)

        for period in range(self.inst.T):
            if period < fixed_until:
                x_lower[:, period] = x_level[:, period]
                x_upper[:, period] = x_level[:, period]
            elif period in window:
                x_upper[:, period] = 1.0
            else:
                xr_upper[:, period] = 1.0
        self._set_variable_records(self.X, x_level, x_lower, x_upper)
        self._set_variable_records(self.XR, xr_level, xr_lower, xr_upper)

    def set_fo_regimes(self, window: set[int], incumbent: np.ndarray) -> None:
        """Apply FO fixed-outside and binary-inside regimes by bounds."""
        x_level = self._incumbent_matrix(incumbent)
        x_lower = np.zeros((self.inst.J, self.inst.T), dtype=np.float64)
        x_upper = np.zeros((self.inst.J, self.inst.T), dtype=np.float64)
        xr_level = np.zeros((self.inst.J, self.inst.T), dtype=np.float64)
        xr_lower = np.zeros((self.inst.J, self.inst.T), dtype=np.float64)
        xr_upper = np.zeros((self.inst.J, self.inst.T), dtype=np.float64)

        for period in range(self.inst.T):
            if period in window:
                x_upper[:, period] = 1.0
            else:
                x_lower[:, period] = x_level[:, period]
                x_upper[:, period] = x_level[:, period]
        self._set_variable_records(self.X, x_level, x_lower, x_upper)
        self._set_variable_records(self.XR, xr_level, xr_lower, xr_upper)

    def set_monolithic_mip_regime(self, incumbent: np.ndarray) -> None:
        """Apply the full MIP regime with all X binary and all XR fixed to zero."""
        x_level = self._incumbent_matrix(incumbent)
        x_lower = np.zeros((self.inst.J, self.inst.T), dtype=np.float64)
        x_upper = np.ones((self.inst.J, self.inst.T), dtype=np.float64)
        xr_level = np.zeros((self.inst.J, self.inst.T), dtype=np.float64)
        xr_lower = np.zeros((self.inst.J, self.inst.T), dtype=np.float64)
        xr_upper = np.zeros((self.inst.J, self.inst.T), dtype=np.float64)
        self._set_variable_records(self.X, x_level, x_lower, x_upper)
        self._set_variable_records(self.XR, xr_level, xr_lower, xr_upper)

    def set_mip_start(self, incumbent: np.ndarray) -> None:
        """Set X.l from the incumbent schedule before an FO solve."""
        records = self.X.records.copy()
        records = records.rename(columns=str.lower)
        levels = {
            (self.j_records[process], self.t_records[period]): (
                1.0 if int(incumbent[period]) == process + 1 else 0.0
            )
            for period in range(self.inst.T)
            for process in range(self.inst.J)
        }
        records["level"] = [levels[(str(row["j"]), str(row["t"]))] for _, row in records.iterrows()]
        self.X.setRecords(records)

    def solve(self, time_limit: float, mipstart: bool = False, optcr: float = 0.001) -> tuple[bool, str, str]:
        """Solve the current model and return whether a solution was loaded."""
        if time_limit <= 0:
            return False, "", "NoTime"
        output = io.StringIO()
        solver_options = {"tilim": float(time_limit), "epgap": float(optcr), "threads": int(self.threads)}
        if mipstart:
            solver_options["mipstart"] = 1
        self.model.solve(
            solver="CPLEX",
            options=Options(relative_optimality_gap=float(optcr), time_limit=float(time_limit)),
            solver_options=solver_options,
            output=output,
        )
        log_text = output.getvalue()
        parsed_version = parse_solver_version(log_text)
        if parsed_version:
            self.solver_version = parsed_version
        return self.X.records is not None, log_text, str(self.model.solve_status)

    def extract_schedule(self, base_schedule: np.ndarray | None = None, periods: set[int] | None = None) -> np.ndarray:
        """Extract a 1-indexed schedule from X levels with tolerance."""
        records = self.X.records
        if records is None:
            raise RuntimeError("No X records are available after solve.")
        records = records.rename(columns=str.lower)
        schedule = np.zeros(self.inst.T, dtype=np.int64) if base_schedule is None else base_schedule.copy()
        target_periods = range(self.inst.T) if periods is None else sorted(periods)
        for period in target_periods:
            t = self.t_records[period]
            active = records[(records["t"] == t) & (records["level"] > 0.5)]
            if len(active) > 1:
                raise RuntimeError(f"More than one process is active in period {period + 1}.")
            schedule[period] = 0
            if len(active) == 1:
                schedule[period] = int(active.iloc[0]["j"])
        return schedule


def make_windows(length: int, width: int, step: int) -> list[tuple[int, int]]:
    """Create zero-based RF windows with the last window anchored at the end."""
    if length <= 0 or width <= 0 or step <= 0:
        raise ValueError("length, width, and step must be positive.")
    width = min(width, length)
    starts = list(range(0, length, step))
    final_start = max(0, length - width)
    starts.append(final_start)
    windows = []
    seen = set()
    for start in sorted(starts):
        if start > final_start:
            continue
        end = min(length, start + width)
        window = (start, end)
        if window not in seen:
            windows.append(window)
            seen.add(window)
    covered = set().union(*(set(range(start, end)) for start, end in windows))
    if covered != set(range(length)):
        raise AssertionError("RF windows do not cover the full horizon.")
    return windows


def evaluate_prefix(schedule: np.ndarray, inst: PSPInstance, last_period: int) -> float:
    """Evaluate the PSP objective accumulated through a prefix of periods."""
    production = np.zeros(inst.I, dtype=float)
    objective = 0.0
    for period in range(last_period + 1):
        process = int(schedule[period])
        if process > 0:
            production += inst.A[:, process - 1]
        demand = inst.D[:, : period + 1].sum(axis=1)
        balance = production - demand
        shortage = np.maximum(-balance, 0.0)
        excess = np.maximum(balance, 0.0)
        objective += float(shortage.sum() + 0.001 * excess.sum())
    return objective


def greedy_fill_window(inst: PSPInstance, schedule: np.ndarray, start: int, end: int) -> np.ndarray:
    """Fill a window by greedily minimizing the prefix objective period by period."""
    candidate = schedule.copy()
    for period in range(start, end):
        best_process = 0
        best_z = math.inf
        for process in range(0, inst.J + 1):
            trial = candidate.copy()
            trial[period] = process
            z_value = evaluate_prefix(trial, inst, period)
            if z_value < best_z:
                best_z = z_value
                best_process = process
        candidate[period] = best_process
    return candidate


def incumbent_from_json(path: Path, inst: PSPInstance) -> np.ndarray:
    """Load a schedule from a JSON result using either list or dict format."""
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("schedule", data.get("scheduling"))
    if raw is None:
        raise ValueError(f"No schedule found in {path}.")
    schedule = np.zeros(inst.T, dtype=np.int64)
    if raw and isinstance(raw[0], dict):
        for item in raw:
            schedule[int(item["period"]) - 1] = int(item["process"])
    else:
        values = [int(value) for value in raw]
        if len(values) != inst.T:
            raise ValueError(f"Schedule in {path} has length {len(values)}, expected {inst.T}.")
        schedule[:] = values
    return schedule


def time_left(start_time: float, budget: float) -> float:
    """Return remaining wall-clock budget."""
    return max(0.0, budget - (time.perf_counter() - start_time))


def classify_window_status(has_solution: bool, solve_status: str, log_text: str) -> str:
    """Classify a window solve status for downstream window-log datasets."""
    evidence = f"{solve_status}\n{log_text}".lower()
    if not has_solution:
        return "no_solution"
    if "resourceinterrupt" in evidence or "resource interrupt" in evidence:
        return "interrupted"
    return "solved"


def schedule_period_profile(schedule: np.ndarray, inst: PSPInstance) -> dict:
    """Return accumulated shortage/excess profiles by period for a schedule."""
    production = np.zeros(inst.I, dtype=float)
    shortage_by_period: list[float] = []
    excess_by_period: list[float] = []
    for period in range(inst.T):
        process = int(schedule[period])
        if process > 0:
            production += inst.A[:, process - 1]
        demand = inst.D[:, : period + 1].sum(axis=1)
        balance = production - demand
        shortage = float(np.maximum(-balance, 0.0).sum())
        excess = float(np.maximum(balance, 0.0).sum())
        shortage_by_period.append(shortage)
        excess_by_period.append(excess)
    max_shortage = max(shortage_by_period) if shortage_by_period else 0.0
    max_period = shortage_by_period.index(max_shortage) + 1 if shortage_by_period else None
    return {
        "shortage_total": float(sum(shortage_by_period)),
        "excess_total": float(sum(excess_by_period)),
        "max_shortage_period": max_period,
        "max_shortage_value": float(max_shortage),
        "shortage_by_period": shortage_by_period,
        "excess_by_period": excess_by_period,
    }


def parse_cplex_progress(log_text: str) -> dict:
    """Extract coarse node and gap information from a CPLEX log when available."""
    node_matches = re.findall(r"^\s*(\d+)\s+\d+\s+", log_text, flags=re.MULTILINE)
    gap_matches = re.findall(r"(\d+(?:\.\d+)?)%", log_text)
    return {
        "cplex_nodes": int(node_matches[-1]) if node_matches else None,
        "cplex_gap_percent": float(gap_matches[-1]) if gap_matches else None,
    }


def aggregate_equation_marginals(equation: Equation, period_column: str = "t") -> pd.DataFrame:
    """Aggregate equation marginal records by period."""
    records = equation.records
    if records is None or records.empty:
        return pd.DataFrame(columns=[period_column, "sum_marginal", "max_abs_marginal"])
    records = records.rename(columns=str.lower)
    if period_column not in records.columns or "marginal" not in records.columns:
        return pd.DataFrame(columns=[period_column, "sum_marginal", "max_abs_marginal"])
    grouped = records.groupby(period_column, observed=False)["marginal"].agg(
        sum_marginal="sum",
        max_abs_marginal=lambda values: float(np.abs(values).max()) if len(values) else 0.0,
    )
    return grouped.reset_index()


def marginal_signal_summary(model: PSPGamspyModel, start: int, end: int, horizon: int) -> dict:
    """Summarize LP marginal signals for a window and the full horizon."""
    target = {str(period) for period in range(start + 1, end + 1)}
    dem = aggregate_equation_marginals(model.EQ_DEM)
    prop = aggregate_equation_marginals(model.EQ_PROP)

    def subset(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame
        return frame[frame["t"].astype(str).isin(target)]

    dem_window = subset(dem)
    prop_window = subset(prop)

    dem_abs_by_period = [0.0] * horizon
    if model.EQ_DEM.records is not None and not model.EQ_DEM.records.empty:
        dem_records = model.EQ_DEM.records.rename(columns=str.lower)
        if "t" in dem_records.columns and "marginal" in dem_records.columns:
            grouped_abs = dem_records.groupby("t", observed=False)["marginal"].apply(
                lambda values: float(np.abs(values).sum())
            )
            for period_key, value in grouped_abs.items():
                period = int(period_key) - 1
                if 0 <= period < horizon:
                    dem_abs_by_period[period] = float(value)

    prop_by_period = [0.0] * horizon
    if model.EQ_PROP.records is not None and not model.EQ_PROP.records.empty:
        prop_records = model.EQ_PROP.records.rename(columns=str.lower)
        if "t" in prop_records.columns and "marginal" in prop_records.columns:
            for _, row in prop_records.iterrows():
                period = int(row["t"]) - 1
                if 0 <= period < horizon:
                    prop_by_period[period] = float(row["marginal"])

    return {
        "eq_dem_marginal_sum_window": float(dem_window["sum_marginal"].sum()) if not dem_window.empty else None,
        "eq_dem_marginal_max_abs_window": float(dem_window["max_abs_marginal"].max()) if not dem_window.empty else None,
        "eq_prop_marginal_sum_window": float(prop_window["sum_marginal"].sum()) if not prop_window.empty else None,
        "eq_prop_marginal_max_abs_window": float(prop_window["max_abs_marginal"].max()) if not prop_window.empty else None,
        "eqdem_marginal_abs_sum_by_period_json": json.dumps(dem_abs_by_period),
        "eqprop_marginal_by_period_json": json.dumps(prop_by_period),
    }


def xr_tail_fraction_nonzero(model: PSPGamspyModel, end: int) -> float:
    """Return the fraction of relaxed-tail XR levels greater than tolerance."""
    records = model.XR.records
    if records is None or records.empty or end >= model.inst.T:
        return 0.0
    records = records.rename(columns=str.lower)
    tail_periods = {str(period) for period in range(end + 1, model.inst.T + 1)}
    tail = records[records["t"].astype(str).isin(tail_periods)]
    if tail.empty:
        return 0.0
    return float((tail["level"].astype(float).abs() > 1e-6).mean())


def append_window_log(
    rows: list[dict],
    *,
    inst: PSPInstance,
    model: PSPGamspyModel,
    phase: str,
    method: str,
    seed: int,
    budget_s: float,
    run_id: str,
    start: int,
    end: int,
    schedule_before: np.ndarray,
    z_before: float,
    z_after: float,
    accepted: bool,
    solve_wall: float,
    status: str,
    reslim_used: float,
    log_text: str,
    solve_status: str,
    time_s: float,
) -> float:
    """Append one window-log row and return instrumentation overhead seconds."""
    log_start = time.perf_counter()
    profile = schedule_period_profile(schedule_before, inst)
    progress = parse_cplex_progress(log_text)
    marginals = marginal_signal_summary(model, start, end, inst.T)
    rows.append(
        {
            "instance": inst.name,
            "dataset": inst.dataset,
            "method": method,
            "seed": int(seed),
            "budget_s": float(budget_s),
            "run_id": run_id,
            "phase": phase,
            "window_start": start + 1,
            "window_end": end,
            "window_size": end - start,
            "time_s": round(time_s, 6),
            "solve_wall_time_s": round(solve_wall, 6),
            "reslim_used_s": round(reslim_used, 6),
            "status": status,
            "solve_status": solve_status,
            "Z_before": round(z_before, 6),
            "Z_after": round(z_after, 6),
            "accepted": bool(accepted),
            "cplex_nodes": progress["cplex_nodes"],
            "cplex_gap_percent": progress["cplex_gap_percent"],
            "xr_frac_nonzero": xr_tail_fraction_nonzero(model, end),
            "shortage_total_before": round(profile["shortage_total"], 6),
            "excess_total_before": round(profile["excess_total"], 6),
            "max_shortage_period_before": profile["max_shortage_period"],
            "max_shortage_value_before": round(profile["max_shortage_value"], 6),
            "shortage_by_period_before_json": json.dumps(profile["shortage_by_period"]),
            "excess_by_period_before_json": json.dumps(profile["excess_by_period"]),
            "eq_dem_marginal_semantics": "LP relaxation with integer variables fixed/reported by GAMS after the solve",
            **marginals,
        }
    )
    return time.perf_counter() - log_start


def solve_relax_and_fix(
    model: PSPGamspyModel,
    inst: PSPInstance,
    params: RunParams,
    start_time: float,
    improvements: list[dict],
    window_log_rows: list[dict],
    seed: int,
    run_id: str,
) -> tuple[np.ndarray, float, int, float, list[dict], list[dict], float]:
    """Construct an incumbent with relax-and-fix."""
    rf_start = time.perf_counter()
    windows = make_windows(inst.T, params.sigma, params.step)
    rf_budget = min(0.25 * params.budget, len(windows) * params.tl_rf)
    incumbent = np.zeros(inst.T, dtype=np.int64)
    best_z = math.inf
    validation_checks: list[dict] = []
    window_diag: list[dict] = []
    executed_windows = 0
    completed_with_solver = False
    instrumentation_wall_time = 0.0

    for idx, (start, end) in enumerate(windows):
        rf_elapsed = time.perf_counter() - rf_start
        if rf_elapsed >= rf_budget or time_left(start_time, params.budget) < 10.0:
            incumbent = greedy_fill_window(inst, incumbent, start, inst.T)
            window_diag.append(
                {
                    "window_start": start + 1,
                    "window_end": end,
                    "status": "budget_guard_greedy_tail",
                    "reslim_used": 0.0,
                    "wall_time_s": 0.0,
                }
            )
            break
        fixed_until = start
        window = set(range(start, end))
        remaining_rf = max(0.0, rf_budget - rf_elapsed)
        remaining_total = time_left(start_time, params.budget)
        remaining_windows = max(1, len(windows) - idx)
        tl = min(params.tl_rf, remaining_rf / remaining_windows, remaining_total)
        if tl < MIN_RF_WINDOW_TL:
            incumbent = greedy_fill_window(inst, incumbent, start, inst.T)
            window_diag.append(
                {
                    "window_start": start + 1,
                    "window_end": end,
                    "status": "budget_guard_greedy_tail",
                    "reslim_used": 0.0,
                    "wall_time_s": 0.0,
                }
            )
            break

        model.set_rf_regimes(fixed_until=fixed_until, window=window, incumbent=incumbent)
        schedule_before = incumbent.copy()
        z_before, _, _ = evaluate(schedule_before, inst)
        solve_start = time.perf_counter()
        solved, log_text, solve_status = model.solve(tl, optcr=0.001)
        solve_wall = time.perf_counter() - solve_start
        if not solved:
            retry_tl = min(tl, max(0.0, rf_budget - (time.perf_counter() - rf_start)), time_left(start_time, params.budget))
            if retry_tl > 0.0:
                retry_start = time.perf_counter()
                solved, log_text, solve_status = model.solve(retry_tl, optcr=0.001)
                solve_wall += time.perf_counter() - retry_start
                tl += retry_tl

        if solved:
            incumbent = model.extract_schedule(base_schedule=incumbent, periods=window)
            status = classify_window_status(solved, solve_status, log_text)
            completed_with_solver = end == inst.T
        else:
            incumbent = greedy_fill_window(inst, incumbent, start, end)
            status = "greedy_window"
        executed_windows += 1

        z_eval, _, _ = evaluate(incumbent, inst)
        if params.log_windows:
            instrumentation_wall_time += append_window_log(
                window_log_rows,
                inst=inst,
                model=model,
                phase="RF",
                method=params.method,
                seed=seed,
                budget_s=params.budget,
                run_id=run_id,
                start=start,
                end=end,
                schedule_before=schedule_before,
                z_before=z_before,
                z_after=z_eval,
                accepted=bool(z_eval < z_before - EPS),
                solve_wall=solve_wall,
                status=status,
                reslim_used=tl,
                log_text=log_text,
                solve_status=solve_status,
                time_s=time.perf_counter() - start_time,
            )
        z_model = float(model.model.objective_value) if model.model.objective_value is not None else math.nan
        has_relaxed_tail = end < inst.T
        validation_checks.append(
            {
                "window_start": start + 1,
                "window_end": end,
                "has_relaxed_tail": has_relaxed_tail,
                "Z_model": round(z_model, 6) if not math.isnan(z_model) else None,
                "Z_evaluate": round(z_eval, 6),
                "abs_diff": None if has_relaxed_tail or math.isnan(z_model) else round(abs(z_model - z_eval), 6),
                "passed": bool(has_relaxed_tail or (not math.isnan(z_model) and abs(z_model - z_eval) < 0.01)),
            }
        )
        window_diag.append(
            {
                "window_start": start + 1,
                "window_end": end,
                "status": status,
                "reslim_used": round(tl, 3),
                "wall_time_s": round(solve_wall, 3),
                "fixed_until": fixed_until,
                "relaxed_tail": end < inst.T,
            }
        )
        if z_eval < best_z - EPS:
            best_z = z_eval
            improvements.append(
                {
                    "time_s": round(time.perf_counter() - start_time, 3),
                    "Z": round(best_z, 6),
                    "phase": "RF",
                    "window_start": start + 1,
                }
            )
        if time_left(start_time, params.budget) <= 0:
            break

    if windows[-1][1] != inst.T:
        raise AssertionError("The final RF window does not reach the end of the horizon.")
    if not np.all(incumbent >= 0):
        raise AssertionError("RF returned an invalid schedule.")

    z_model = float(model.model.objective_value) if model.model.objective_value is not None else best_z
    z_eval, _, _ = evaluate(incumbent, inst)
    if completed_with_solver and abs(z_model - z_eval) >= 0.01:
        raise RuntimeError(f"RF validation failed: model Z={z_model}, evaluator Z={z_eval}.")
    if validation_checks:
        validation_checks[-1]["abs_diff"] = round(abs(z_model - z_eval), 6) if completed_with_solver else None
        validation_checks[-1]["passed"] = bool(completed_with_solver and abs(z_model - z_eval) < 0.01)
        validation_checks[-1]["completed_with_solver"] = completed_with_solver
    return (
        incumbent,
        z_eval,
        executed_windows,
        time.perf_counter() - rf_start,
        validation_checks,
        window_diag,
        instrumentation_wall_time,
    )


def solve_greedy_construction(
    inst: PSPInstance,
    start_time: float,
    improvements: list[dict],
) -> tuple[np.ndarray, float, float, list[dict]]:
    """Construct a complete incumbent with the deterministic greedy heuristic."""
    construction_start = time.perf_counter()
    incumbent = greedy_fill_window(inst, np.zeros(inst.T, dtype=np.int64), 0, inst.T)
    z_eval, _, _ = evaluate(incumbent, inst)
    wall_time = time.perf_counter() - construction_start
    improvements.append(
        {
            "time_s": round(time.perf_counter() - start_time, 3),
            "Z": round(z_eval, 6),
            "phase": "greedy_construction",
            "window_start": 1,
        }
    )
    diag = [
        {
            "window_start": 1,
            "window_end": inst.T,
            "status": "greedy_construction",
            "reslim_used": 0.0,
            "wall_time_s": round(wall_time, 3),
            "fixed_until": 0,
            "relaxed_tail": False,
        }
    ]
    return incumbent, z_eval, wall_time, diag


def solve_fix_and_optimize(
    model: PSPGamspyModel,
    inst: PSPInstance,
    params: RunParams,
    start_time: float,
    incumbent: np.ndarray,
    improvements: list[dict],
    seed: int,
    window_log_rows: list[dict],
    run_id: str,
) -> tuple[np.ndarray, float, int, int, bool, bool, str | None, list[str], float]:
    """Improve an incumbent with fix-and-optimize windows."""
    rng = random.Random(seed)
    z_inc, _, _ = evaluate(incumbent, inst)
    accepts = 0
    sweeps_completed = 0
    warm_checked = False
    warm_has_mipstart = False
    warm_log_excerpt: str | None = None
    warm_evidence_lines: list[str] = []
    instrumentation_wall_time = 0.0

    def try_window(start: int, end: int, phase: str) -> bool:
        nonlocal incumbent, z_inc, accepts, warm_checked, warm_has_mipstart, warm_log_excerpt
        nonlocal warm_evidence_lines, instrumentation_wall_time
        if time_left(start_time, params.budget) < 10.0:
            return False
        window = set(range(start, end))
        schedule_before = incumbent.copy()
        z_before = z_inc
        model.set_fo_regimes(window=window, incumbent=incumbent)
        model.set_mip_start(incumbent)
        reslim_used = max(5.0, min(params.tl_fo, time_left(start_time, params.budget)))
        solve_start = time.perf_counter()
        solved, log_text, solve_status = model.solve(reslim_used, mipstart=True, optcr=0.01)
        solve_wall = time.perf_counter() - solve_start
        status = classify_window_status(solved, solve_status, log_text)
        if not warm_checked:
            warm_checked = True
            normalized_log = log_text.lower()
            warm_has_mipstart = "mip start" in normalized_log or "mipstart" in normalized_log
            warm_log_excerpt = extract_mipstart_excerpt(log_text)
            warm_evidence_lines = extract_mipstart_evidence(log_text)
        if not solved:
            if params.log_windows:
                instrumentation_wall_time += append_window_log(
                    window_log_rows,
                    inst=inst,
                    model=model,
                    phase=phase,
                    method=params.method,
                    seed=seed,
                    budget_s=params.budget,
                    run_id=run_id,
                    start=start,
                    end=end,
                    schedule_before=schedule_before,
                    z_before=z_before,
                    z_after=z_before,
                    accepted=False,
                    solve_wall=solve_wall,
                    status=status,
                    reslim_used=reslim_used,
                    log_text=log_text,
                    solve_status=solve_status,
                    time_s=time.perf_counter() - start_time,
                )
            return False
        candidate = model.extract_schedule(base_schedule=incumbent, periods=window)
        z_new, _, _ = evaluate(candidate, inst)
        accepted = z_new < z_inc - EPS
        if params.log_windows:
            instrumentation_wall_time += append_window_log(
                window_log_rows,
                inst=inst,
                model=model,
                phase=phase,
                method=params.method,
                seed=seed,
                budget_s=params.budget,
                run_id=run_id,
                start=start,
                end=end,
                schedule_before=schedule_before,
                z_before=z_before,
                z_after=z_new,
                accepted=accepted,
                solve_wall=solve_wall,
                status=status,
                reslim_used=reslim_used,
                log_text=log_text,
                solve_status=solve_status,
                time_s=time.perf_counter() - start_time,
            )
        if accepted:
            incumbent = candidate
            z_inc = z_new
            accepts += 1
            improvements.append(
                {
                    "time_s": round(time.perf_counter() - start_time, 3),
                    "Z": round(z_inc, 6),
                    "phase": phase,
                    "window_start": start + 1,
                }
            )
            return True
        return False

    improved_in_sweep = True
    while time_left(start_time, params.budget) >= 10.0 and improved_in_sweep:
        improved_in_sweep = False
        completed = True
        for start, end in make_windows(inst.T, params.omega, params.step_fo):
            if time_left(start_time, params.budget) < 10.0:
                completed = False
                break
            improved_in_sweep |= try_window(start, end, "FO_sweep")
            if time_left(start_time, params.budget) < 10.0:
                completed = False
                break
        if completed:
            sweeps_completed += 1

    while time_left(start_time, params.budget) >= 10.0:
        offset = rng.randrange(max(1, min(params.omega, inst.T)))
        starts = list(range(offset, inst.T, params.omega))
        if offset > 0:
            starts.insert(0, 0)
        completed = True
        for start in starts:
            if time_left(start_time, params.budget) < 10.0:
                completed = False
                break
            end = min(inst.T, start + params.omega)
            try_window(start, end, "FO_random")
            if time_left(start_time, params.budget) < 10.0:
                completed = False
                break
        if completed:
            sweeps_completed += 1

    return (
        incumbent,
        z_inc,
        accepts,
        sweeps_completed,
        warm_checked,
        warm_has_mipstart,
        warm_log_excerpt,
        warm_evidence_lines,
        instrumentation_wall_time,
    )


def solve_monolithic_mip(
    model: PSPGamspyModel,
    inst: PSPInstance,
    params: RunParams,
    start_time: float,
    incumbent: np.ndarray,
    improvements: list[dict],
) -> tuple[np.ndarray, float, bool, bool, str | None, list[str]]:
    """Solve the full MIP using the RF incumbent as a MIP start."""
    z_inc, _, _ = evaluate(incumbent, inst)
    if time_left(start_time, params.budget) <= 0:
        return incumbent, z_inc, False, False, None, []

    model.set_monolithic_mip_regime(incumbent)
    model.set_mip_start(incumbent)
    solved, log_text, _ = model.solve(time_left(start_time, params.budget), mipstart=True, optcr=0.0)
    normalized_log = log_text.lower()
    warm_has_mipstart = "mip start" in normalized_log or "mipstart" in normalized_log
    warm_log_excerpt = extract_mipstart_excerpt(log_text)
    warm_evidence_lines = extract_mipstart_evidence(log_text)

    if not solved:
        return incumbent, z_inc, True, warm_has_mipstart, warm_log_excerpt, warm_evidence_lines

    candidate = model.extract_schedule()
    z_new, _, _ = evaluate(candidate, inst)
    improvements.append(
        {
            "time_s": round(time.perf_counter() - start_time, 3),
            "Z": round(z_new, 6),
            "phase": "MIP",
            "window_start": None,
        }
    )
    if z_new < z_inc - EPS:
        return candidate, z_new, True, warm_has_mipstart, warm_log_excerpt, warm_evidence_lines
    return incumbent, z_inc, True, warm_has_mipstart, warm_log_excerpt, warm_evidence_lines


def solve_cold_monolithic_mip(
    model: PSPGamspyModel,
    inst: PSPInstance,
    params: RunParams,
    start_time: float,
    improvements: list[dict],
) -> tuple[np.ndarray, float]:
    """Solve the full MIP without a warm start."""
    incumbent = np.zeros(inst.T, dtype=np.int64)
    z_inc, _, _ = evaluate(incumbent, inst)
    if time_left(start_time, params.budget) <= 0:
        return incumbent, z_inc

    model.set_monolithic_mip_regime(incumbent)
    solved, _, _ = model.solve(time_left(start_time, params.budget), mipstart=False, optcr=0.0)
    if not solved:
        return incumbent, z_inc

    candidate = model.extract_schedule()
    z_new, _, _ = evaluate(candidate, inst)
    improvements.append(
        {
            "time_s": round(time.perf_counter() - start_time, 3),
            "Z": round(z_new, 6),
            "phase": "MIP",
            "window_start": None,
        }
    )
    return candidate, z_new


def extract_mipstart_excerpt(log_text: str) -> str | None:
    """Return the first CPLEX log line mentioning a MIP start."""
    for line in log_text.splitlines():
        normalized = line.lower()
        if "mip start" in normalized or "mipstart" in normalized:
            return line.strip()
    return None


def extract_mipstart_evidence(log_text: str) -> list[str]:
    """Return CPLEX log lines that can evidence MIP start handling."""
    keywords = ("mip start", "mipstart", "defined initial solution", "initial solution")
    lines = []
    for line in log_text.splitlines():
        normalized = line.lower()
        if any(keyword in normalized for keyword in keywords):
            stripped = line.strip()
            if stripped and stripped not in lines:
                lines.append(stripped)
    return lines[:10]


def parse_solver_version(log_text: str) -> str | None:
    """Parse the CPLEX version identifier from solver output."""
    match = re.search(r"Version identifier:\s*([^|\r\n]+)", log_text)
    if match:
        return match.group(1).strip()
    match = re.search(r"Cplex\s+([0-9]+(?:\.[0-9]+)+)", log_text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def hardware_provenance() -> dict:
    """Collect hardware provenance for experimental JSON outputs."""
    physical = None
    ram_bytes = None
    processor_model = None
    try:
        import psutil

        physical = psutil.cpu_count(logical=False)
        ram_bytes = int(psutil.virtual_memory().total)
    except Exception:
        physical = None
        ram_bytes = None
    if platform.system().lower() == "windows":
        try:
            processor_model = subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)",
                ],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5,
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


def run_matheuristic(instance_path: Path, params: RunParams, seed: int) -> MatheuristicResult:
    """Run RF, RF+FO, RF+MIP, or cold MIP on one instance."""
    start_time = time.perf_counter()
    inst = load_instance(instance_path)
    suffix = params.output_suffix or ""
    run_id = f"{inst.name}_{params.method.replace('+', '_')}_seed{seed}{suffix}"
    model = PSPGamspyModel(inst, threads=params.threads)
    improvements: list[dict] = []
    rf_wall_time = 0.0
    rf_validation_checks: list[dict] = []
    rf_window_diag: list[dict] = []
    window_log_rows: list[dict] = []
    instrumentation_wall_time = 0.0
    construction = "rf"
    z_greedy: float | None = None
    greedy_wall_time = 0.0

    if params.method == "mip":
        incumbent, z_rf = solve_cold_monolithic_mip(model, inst, params, start_time, improvements)
        rf_windows = 0
        construction = "mip"
    elif params.start_from:
        incumbent = incumbent_from_json(Path(params.start_from), inst)
        z_rf, _, _ = evaluate(incumbent, inst)
        rf_windows = 0
        construction = "external"
    else:
        greedy_incumbent, z_greedy, greedy_wall_time, greedy_diag = solve_greedy_construction(
            inst, start_time, improvements
        )
        rf_windows_plan = make_windows(inst.T, params.sigma, params.step)
        rf_budget = min(0.25 * params.budget, len(rf_windows_plan) * params.tl_rf)
        if rf_budget / len(rf_windows_plan) < 10.0:
            construction = "greedy"
            incumbent = greedy_incumbent
            z_rf = z_greedy
            rf_windows = 0
            rf_window_diag = greedy_diag
        else:
            (
                rf_incumbent,
                z_rf,
                rf_windows,
                rf_wall_time,
                rf_validation_checks,
                rf_window_diag,
                rf_instrumentation_wall_time,
            ) = solve_relax_and_fix(model, inst, params, start_time, improvements, window_log_rows, seed, run_id)
            instrumentation_wall_time += rf_instrumentation_wall_time
            if z_greedy <= z_rf + EPS:
                incumbent = greedy_incumbent
                construction = "greedy_floor"
            else:
                incumbent = rf_incumbent
                construction = "rf"
    best_schedule = incumbent.copy()
    z_best_overall, _, _ = evaluate(incumbent, inst)
    z_initial = z_best_overall

    fo_accepts = 0
    fo_sweeps_completed = 0
    warm_checked = False
    warm_has_mipstart = False
    warm_log_excerpt = None
    warm_evidence_lines: list[str] = []
    z_final = z_best_overall
    if params.method == "rf+fo" and time_left(start_time, params.budget) > 0:
        (
            incumbent,
            z_final,
            fo_accepts,
            fo_sweeps_completed,
            warm_checked,
            warm_has_mipstart,
            warm_log_excerpt,
            warm_evidence_lines,
            fo_instrumentation_wall_time,
        ) = solve_fix_and_optimize(
            model, inst, params, start_time, incumbent, improvements, seed, window_log_rows, run_id
        )
        instrumentation_wall_time += fo_instrumentation_wall_time
        if z_final < z_best_overall - EPS:
            best_schedule = incumbent.copy()
            z_best_overall = z_final
    elif params.method == "rf+mip" and time_left(start_time, params.budget) > 0:
        (
            incumbent,
            z_final,
            warm_checked,
            warm_has_mipstart,
            warm_log_excerpt,
            warm_evidence_lines,
        ) = solve_monolithic_mip(model, inst, params, start_time, incumbent, improvements)
        if z_final < z_best_overall - EPS:
            best_schedule = incumbent.copy()
            z_best_overall = z_final

    z_final, shortage, excess = evaluate(best_schedule, inst)
    z_best_overall = z_final
    if z_final > z_initial + EPS and params.method in {"rf+fo", "rf+mip"}:
        raise RuntimeError(f"Improvement phase worsened incumbent: Z_final={z_final}, Z_start={z_initial}.")

    return MatheuristicResult(
        schedule=[int(value) for value in best_schedule],
        construction=construction,
        z_greedy=z_greedy,
        greedy_wall_time=greedy_wall_time,
        z_final=z_final,
        z_best_overall=z_best_overall,
        shortage=shortage,
        excess=excess,
        z_rf=z_rf,
        improvements=improvements,
        rf_windows=rf_windows,
        rf_wall_time=rf_wall_time,
        rf_validation_checks=rf_validation_checks,
        fo_accepts=fo_accepts,
        fo_sweeps_completed=fo_sweeps_completed,
        warm_start_checked=warm_checked,
        warm_start_log_has_mipstart=warm_has_mipstart,
        warm_start_log_excerpt=warm_log_excerpt,
        warm_start_log_evidence_lines=warm_evidence_lines,
        rf_window_diag=rf_window_diag,
        window_log_rows=window_log_rows,
        instrumentation_wall_time=instrumentation_wall_time,
        solver_version=model.solver_version,
        hardware=hardware_provenance(),
    )


def write_result(
    instance_path: Path,
    params: RunParams,
    seed: int,
    result: MatheuristicResult,
    output_dir: Path = RESULTS_DIR,
) -> Path:
    """Write the result JSON expected by the pilot workflow."""
    inst = load_instance(instance_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = params.output_suffix or ""
    output_path = output_dir / f"{inst.name}_{params.method.replace('+', '_')}_seed{seed}{suffix}.json"
    payload = {
        "instance": inst.name,
        "dataset": inst.dataset,
        "method": params.method,
        "construction": result.construction,
        "construction_used": result.construction,
        "params": asdict(params),
        "seed": seed,
        "Z_final": round(result.z_final, 6),
        "Z_best_overall": round(result.z_best_overall, 6),
        "Z_greedy": None if result.z_greedy is None else round(result.z_greedy, 6),
        "shortage": round(result.shortage, 6),
        "excess": round(result.excess, 6),
        "schedule": result.schedule,
        "improvements": result.improvements,
        "Z_rf": round(result.z_rf, 6),
        "wall_time_total": None,
        "versions": {
            "gamspy": getattr(__import__("gamspy"), "__version__", None),
            "solver": "CPLEX",
            "solver_version": result.solver_version,
        },
        "hardware": result.hardware,
        "rf_windows": result.rf_windows,
        "rf_wall_time": round(result.rf_wall_time, 3),
        "rf_wall_time_s": round(result.rf_wall_time, 3),
        "greedy_wall_time_s": round(result.greedy_wall_time, 3),
        "instrumentation_wall_time_s": round(result.instrumentation_wall_time, 6),
        "rf_validation_checks": result.rf_validation_checks,
        "rf_window_diag": result.rf_window_diag,
        "window_log_rows": len(result.window_log_rows),
        "fo_accepts": result.fo_accepts,
        "fo_sweeps_completed": result.fo_sweeps_completed,
        "warm_start_checked": result.warm_start_checked,
        "warm_start_log_has_mipstart": result.warm_start_log_has_mipstart,
        "warm_start_log_excerpt": result.warm_start_log_excerpt,
        "warm_start_log_evidence_lines": result.warm_start_log_evidence_lines,
        "run_timestamp": dt.datetime.now().isoformat(timespec="seconds"),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def write_window_log(result_path: Path, rows: list[dict]) -> Path | None:
    """Write per-window instrumentation next to a result JSON."""
    if not rows:
        return None
    log_dir = result_path.parent / "window_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    parquet_path = log_dir / f"{result_path.stem}_windows.parquet"
    try:
        frame.to_parquet(parquet_path, index=False)
        return parquet_path
    except Exception:
        csv_path = log_dir / f"{result_path.stem}_windows.csv"
        frame.to_csv(csv_path, index=False)
        return csv_path


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse CLI options."""
    parser = argparse.ArgumentParser(description="RF/FO matheuristic for PSP GAMSPy instances.")
    parser.add_argument("--instance", required=True, type=Path)
    parser.add_argument("--budget", required=True, type=float)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--sigma", type=int, default=10)
    parser.add_argument("--step", type=int, default=5)
    parser.add_argument("--omega", type=int, default=12)
    parser.add_argument("--step-fo", type=int, default=6)
    parser.add_argument("--tl-rf", type=float, default=120.0)
    parser.add_argument("--tl-fo", type=float, default=60.0)
    parser.add_argument("--start-from", default=None)
    parser.add_argument("--method", choices=["rf", "rf+fo", "rf+mip", "mip"], default="rf+fo")
    parser.add_argument("--threads", type=int, default=0, help="CPLEX threads option; 0 lets CPLEX use all.")
    parser.add_argument("--output-suffix", default=None, help="Optional suffix before .json, e.g. _v2.")
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR, help="Directory for the result JSON.")
    parser.add_argument("--log-windows", action="store_true", help="Write per-window instrumentation.")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    """Run the command-line interface."""
    args = parse_args(argv)
    params = RunParams(
        budget=args.budget,
        sigma=args.sigma,
        step=args.step,
        omega=args.omega,
        step_fo=args.step_fo,
        tl_rf=args.tl_rf,
        tl_fo=args.tl_fo,
        method=args.method,
        start_from=args.start_from,
        threads=args.threads,
        output_suffix=args.output_suffix,
        log_windows=args.log_windows,
    )
    wall_start = time.perf_counter()
    result = run_matheuristic(args.instance, params, args.seed)
    output_path = write_result(args.instance, params, args.seed, result, output_dir=args.output_dir)
    data = json.loads(output_path.read_text(encoding="utf-8"))
    data["wall_time_total"] = round(time.perf_counter() - wall_start, 3)
    data["window_log_path"] = None
    if args.log_windows:
        log_path = write_window_log(output_path, result.window_log_rows)
        data["window_log_path"] = None if log_path is None else str(log_path)
        data["instrumentation_overhead_percent"] = (
            round(100.0 * result.instrumentation_wall_time / data["wall_time_total"], 6)
            if data["wall_time_total"]
            else 0.0
        )
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Result JSON: {output_path}")
    print(
        f"Z_rf={result.z_rf:.6f} Z_final={result.z_final:.6f} "
        f"Z_best_overall={result.z_best_overall:.6f} "
        f"Z_greedy={result.z_greedy if result.z_greedy is not None else 'NA'} "
        f"construction={result.construction} "
        f"rf_windows={result.rf_windows} fo_accepts={result.fo_accepts} "
        f"fo_sweeps_completed={result.fo_sweeps_completed} "
        f"rf_wall_time={result.rf_wall_time:.3f}s "
        f"greedy_wall_time={result.greedy_wall_time:.3f}s "
        f"instrumentation_wall_time={result.instrumentation_wall_time:.6f}s "
        f"wall_time_total={data['wall_time_total']:.3f}s"
    )
    if args.log_windows:
        print(f"Window log: {data['window_log_path']}")
        print(f"Instrumentation overhead: {data['instrumentation_overhead_percent']:.6f}%")
    if result.warm_start_checked and not result.warm_start_log_has_mipstart:
        print("WARNING: CPLEX log did not contain a visible 'MIP start' message.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
