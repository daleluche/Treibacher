"""Relax-and-fix and fix-and-optimize matheuristics for the PSP MFP model."""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import math
import random
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


@dataclass
class MatheuristicResult:
    """Summary of one RF/FO run."""

    schedule: list[int]
    z_final: float
    shortage: float
    excess: float
    z_rf: float
    improvements: list[dict]
    rf_windows: int
    fo_accepts: int
    warm_start_checked: bool
    warm_start_log_has_mipstart: bool


class PSPGamspyModel:
    """Single GAMSPy model with X and XR controlled by bounds."""

    def __init__(self, inst: PSPInstance) -> None:
        self.inst = inst
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
        for period in range(self.inst.T):
            for process in range(self.inst.J):
                j = self.j_records[process]
                t = self.t_records[period]
                self.X.lo[j, t] = 0
                self.X.up[j, t] = 1
                self.XR.lo[j, t] = 0
                self.XR.up[j, t] = 1

    def set_rf_regimes(self, fixed_until: int, window: set[int], incumbent: np.ndarray) -> None:
        """Apply RF relaxed, binary, and fixed period regimes by bounds."""
        for period in range(self.inst.T):
            for process in range(self.inst.J):
                j = self.j_records[process]
                t = self.t_records[period]
                if period < fixed_until:
                    value = 1 if int(incumbent[period]) == process + 1 else 0
                    self.X.fx[j, t] = value
                    self.XR.fx[j, t] = 0
                elif period in window:
                    self.X.lo[j, t] = 0
                    self.X.up[j, t] = 1
                    self.XR.fx[j, t] = 0
                else:
                    self.X.fx[j, t] = 0
                    self.XR.lo[j, t] = 0
                    self.XR.up[j, t] = 1

    def set_fo_regimes(self, window: set[int], incumbent: np.ndarray) -> None:
        """Apply FO fixed-outside and binary-inside regimes by bounds."""
        for period in range(self.inst.T):
            for process in range(self.inst.J):
                j = self.j_records[process]
                t = self.t_records[period]
                self.XR.fx[j, t] = 0
                if period in window:
                    self.X.lo[j, t] = 0
                    self.X.up[j, t] = 1
                else:
                    value = 1 if int(incumbent[period]) == process + 1 else 0
                    self.X.fx[j, t] = value

    def set_mip_start(self, incumbent: np.ndarray) -> None:
        """Set X.l from the incumbent schedule before an FO solve."""
        for period in range(self.inst.T):
            for process in range(self.inst.J):
                self.X.l[self.j_records[process], self.t_records[period]] = (
                    1 if int(incumbent[period]) == process + 1 else 0
                )

    def solve(self, time_limit: float, mipstart: bool = False) -> tuple[bool, str]:
        """Solve the current model and return whether a solution was loaded."""
        if time_limit <= 0:
            return False, ""
        output = io.StringIO()
        solver_options = {"mipstart": 1} if mipstart else None
        self.model.solve(
            solver="CPLEX",
            options=Options(relative_optimality_gap=0.0, time_limit=float(time_limit)),
            solver_options=solver_options,
            output=output,
        )
        return self.X.records is not None, output.getvalue()

    def extract_schedule(self) -> np.ndarray:
        """Extract a 1-indexed schedule from X levels with tolerance."""
        records = self.X.records
        if records is None:
            raise RuntimeError("No X records are available after solve.")
        records = records.rename(columns=str.lower)
        schedule = np.zeros(self.inst.T, dtype=np.int64)
        for period in range(self.inst.T):
            t = self.t_records[period]
            active = records[(records["t"] == t) & (records["level"] > 0.5)]
            if len(active) > 1:
                raise RuntimeError(f"More than one process is active in period {period + 1}.")
            if len(active) == 1:
                schedule[period] = int(active.iloc[0]["j"])
        return schedule


def make_windows(length: int, width: int, step: int) -> list[tuple[int, int]]:
    """Create overlapping zero-based windows covering all periods."""
    windows = []
    start = 0
    while start < length:
        end = min(length, start + width)
        windows.append((start, end))
        if end == length:
            break
        start += step
    return windows


def greedy_fill_window(inst: PSPInstance, schedule: np.ndarray, start: int, end: int) -> np.ndarray:
    """Fill a window with the process that minimizes the current full objective."""
    candidate = schedule.copy()
    for period in range(start, end):
        best_process = 0
        best_z = math.inf
        for process in range(0, inst.J + 1):
            trial = candidate.copy()
            trial[period] = process
            z_value, _, _ = evaluate(trial, inst)
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


def solve_relax_and_fix(
    model: PSPGamspyModel,
    inst: PSPInstance,
    params: RunParams,
    start_time: float,
    improvements: list[dict],
) -> tuple[np.ndarray, float, int]:
    """Construct an incumbent with relax-and-fix."""
    windows = make_windows(inst.T, params.sigma, params.step)
    rf_budget = 0.25 * params.budget
    incumbent = np.zeros(inst.T, dtype=np.int64)
    best_z = math.inf

    for idx, (start, end) in enumerate(windows):
        fixed_until = start
        window = set(range(start, end))
        remaining_rf = max(0.0, rf_budget - (time.perf_counter() - start_time))
        remaining_total = time_left(start_time, params.budget)
        remaining_windows = max(1, len(windows) - idx)
        tl = min(params.tl_rf, remaining_rf / remaining_windows, remaining_total)

        model.set_rf_regimes(fixed_until=fixed_until, window=window, incumbent=incumbent)
        solved, _ = model.solve(tl)
        if not solved:
            solved, _ = model.solve(min(2.0 * tl, time_left(start_time, params.budget)))

        if solved:
            incumbent = model.extract_schedule()
        else:
            incumbent = greedy_fill_window(inst, incumbent, start, end)

        z_eval, _, _ = evaluate(incumbent, inst)
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

    z_model = float(model.model.objective_value) if model.model.objective_value is not None else best_z
    z_eval, _, _ = evaluate(incumbent, inst)
    if abs(z_model - z_eval) >= 0.01:
        raise RuntimeError(f"RF validation failed: model Z={z_model}, evaluator Z={z_eval}.")
    return incumbent, z_eval, len(windows)


def solve_fix_and_optimize(
    model: PSPGamspyModel,
    inst: PSPInstance,
    params: RunParams,
    start_time: float,
    incumbent: np.ndarray,
    improvements: list[dict],
    seed: int,
) -> tuple[np.ndarray, float, int, bool, bool]:
    """Improve an incumbent with fix-and-optimize windows."""
    rng = random.Random(seed)
    z_inc, _, _ = evaluate(incumbent, inst)
    accepts = 0
    warm_checked = False
    warm_has_mipstart = False

    def try_window(start: int, end: int, phase: str) -> bool:
        nonlocal incumbent, z_inc, accepts, warm_checked, warm_has_mipstart
        if time_left(start_time, params.budget) <= 0:
            return False
        window = set(range(start, end))
        model.set_fo_regimes(window=window, incumbent=incumbent)
        model.set_mip_start(incumbent)
        solved, log_text = model.solve(min(params.tl_fo, time_left(start_time, params.budget)), mipstart=True)
        if not warm_checked:
            warm_checked = True
            warm_has_mipstart = "mip start" in log_text.lower()
        if not solved:
            return False
        candidate = model.extract_schedule()
        z_new, _, _ = evaluate(candidate, inst)
        if z_new < z_inc - EPS:
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
    while time_left(start_time, params.budget) > 0 and improved_in_sweep:
        improved_in_sweep = False
        for start, end in make_windows(inst.T, params.omega, params.step_fo):
            improved_in_sweep |= try_window(start, end, "FO_sweep")
            if time_left(start_time, params.budget) <= 0:
                break

    while time_left(start_time, params.budget) > 0:
        offset = rng.randrange(max(1, min(params.omega, inst.T)))
        starts = list(range(offset, inst.T, params.omega))
        if offset > 0:
            starts.insert(0, 0)
        for start in starts:
            end = min(inst.T, start + params.omega)
            try_window(start, end, "FO_random")
            if time_left(start_time, params.budget) <= 0:
                break

    return incumbent, z_inc, accepts, warm_checked, warm_has_mipstart


def run_matheuristic(instance_path: Path, params: RunParams, seed: int) -> MatheuristicResult:
    """Run RF or RF+FO on one instance."""
    start_time = time.perf_counter()
    inst = load_instance(instance_path)
    model = PSPGamspyModel(inst)
    improvements: list[dict] = []

    if params.start_from:
        incumbent = incumbent_from_json(Path(params.start_from), inst)
        z_rf, _, _ = evaluate(incumbent, inst)
        rf_windows = 0
    else:
        incumbent, z_rf, rf_windows = solve_relax_and_fix(model, inst, params, start_time, improvements)

    fo_accepts = 0
    warm_checked = False
    warm_has_mipstart = False
    z_final = z_rf
    if params.method == "rf+fo" and time_left(start_time, params.budget) > 0:
        incumbent, z_final, fo_accepts, warm_checked, warm_has_mipstart = solve_fix_and_optimize(
            model, inst, params, start_time, incumbent, improvements, seed
        )

    z_final, shortage, excess = evaluate(incumbent, inst)
    if z_final > z_rf + EPS and params.method == "rf+fo":
        raise RuntimeError(f"FO worsened incumbent: Z_final={z_final}, Z_rf={z_rf}.")

    return MatheuristicResult(
        schedule=[int(value) for value in incumbent],
        z_final=z_final,
        shortage=shortage,
        excess=excess,
        z_rf=z_rf,
        improvements=improvements,
        rf_windows=rf_windows,
        fo_accepts=fo_accepts,
        warm_start_checked=warm_checked,
        warm_start_log_has_mipstart=warm_has_mipstart,
    )


def write_result(instance_path: Path, params: RunParams, seed: int, result: MatheuristicResult) -> Path:
    """Write the result JSON expected by the pilot workflow."""
    inst = load_instance(instance_path)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / f"{inst.name}_{params.method.replace('+', '_')}_seed{seed}.json"
    payload = {
        "instance": inst.name,
        "dataset": inst.dataset,
        "method": params.method,
        "params": asdict(params),
        "seed": seed,
        "Z_final": round(result.z_final, 6),
        "shortage": round(result.shortage, 6),
        "excess": round(result.excess, 6),
        "schedule": result.schedule,
        "improvements": result.improvements,
        "Z_rf": round(result.z_rf, 6),
        "wall_time_total": None,
        "versions": {"gamspy": getattr(__import__("gamspy"), "__version__", None), "solver": "CPLEX"},
        "rf_windows": result.rf_windows,
        "fo_accepts": result.fo_accepts,
        "warm_start_checked": result.warm_start_checked,
        "warm_start_log_has_mipstart": result.warm_start_log_has_mipstart,
        "run_timestamp": dt.datetime.now().isoformat(timespec="seconds"),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


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
    parser.add_argument("--method", choices=["rf", "rf+fo"], default="rf+fo")
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
    )
    wall_start = time.perf_counter()
    result = run_matheuristic(args.instance, params, args.seed)
    output_path = write_result(args.instance, params, args.seed, result)
    data = json.loads(output_path.read_text(encoding="utf-8"))
    data["wall_time_total"] = round(time.perf_counter() - wall_start, 3)
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Result JSON: {output_path}")
    print(
        f"Z_rf={result.z_rf:.6f} Z_final={result.z_final:.6f} "
        f"rf_windows={result.rf_windows} fo_accepts={result.fo_accepts} "
        f"wall_time_total={data['wall_time_total']:.3f}s"
    )
    if result.warm_start_checked and not result.warm_start_log_has_mipstart:
        print("WARNING: CPLEX log did not contain a visible 'MIP start' message.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
