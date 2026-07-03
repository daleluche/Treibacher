"""
GRASP + ILS v2.0 — Process Selection Problem (PSP)
====================================================
Enhanced metaheuristic integrating five improvement strategies:

  Strategy 2: Reactive GRASP  — adaptive α weight learning (Prais & Ribeiro 2000)
  Strategy 3: Cross-run PR    — Path Relinking across workers' elite solutions (post-hoc)
  Strategy 4: VND             — Or-opt block-reinsertion neighborhoods (k=1,2,3)
  Strategy 5: Adaptive bridge — triple/quadruple-bridge perturbation for large T
  Strategy 6: Sliding window  — windowed Tabu Search for T > WINDOW_T_THRESH

Standard time limit: 3600 s (60 min), matching GAMSPy/CPLEX22 runs.

Problem (identical to MIP in GAMSPy/CPLEX22):
    Minimise  Z = ∑_{i,t} F[i,t] + 0.001·E[i,t]
    s.t.      ∑_{j,t'≤t} A[i,j]·X[j,t'] + F[i,t] – E[i,t] = ∑_{t'≤t} D[i,t']  ∀i,t
              ∑_j X[j,t] ≤ 1  ∀t;  X ∈ {0,1};  F,E ≥ 0

References:
    Lourenço, Martin & Stützle (2002) — ILS survey
    Feo & Resende (1995) — GRASP original
    Prais & Ribeiro (2000) — Reactive GRASP
    Resende & Ribeiro (2003) — GRASP+PR
    Hansen & Mladenović (2001) — VNS / VND
    Glover (1998) — Tabu Search
"""

from __future__ import annotations

import re
import ast
import time
import random
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

import numpy as np

logger = logging.getLogger(__name__)

ALGO_VERSION = "v2.0"

# ── Core hyper-parameters ─────────────────────────────────────────────────────
PESO_ESTOQUE         = 0.001   # excess-stock penalty weight (matches MIP)
LRC_SIZE             = 7       # fallback candidate-list size for lrc_history-guided TS
TABU_TENURE_LO       = 5       # min tabu tenure (randomised each sweep)
TABU_TENURE_HI       = 12      # max tabu tenure
TABU_SWEEPS          = 150     # max sweeps for full Tabu Search
ELITE_SIZE           = 10      # elite set capacity (intra-run)
MIN_ELITE_DIST       = 2       # min Hamming distance to enter elite set
LOOK_AHEAD_LO        = 3       # construction look-ahead window (min)
LOOK_AHEAD_HI        = 7       # construction look-ahead window (max)
V_MAX                = 5       # distance-decay exponent max (construction)
PR_FREQ              = 4       # intra-run PR every N ILS improvements
ILS_NO_IMPROVE_LIMIT = 20      # GRASP restart after N non-improving ILS iters

# ── Strategy 2: Reactive GRASP ────────────────────────────────────────────────
ALPHA_VALUES   = np.array([0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30])
REACTIVE_DECAY = 0.15          # EMA learning rate for α weight update

# ── Strategy 4: VND — Or-opt block reinsertion ───────────────────────────────
OR_OPT_TRIES    = 80           # random candidate moves per Or-opt call
OR_OPT_K_VALUES = (1, 2, 3)   # block sizes tried in VND

# ── Strategy 5: Adaptive multi-bridge perturbation ───────────────────────────
# (T_upper_bound, n_cuts) — first matching entry is used
BRIDGE_THRESHOLDS = [(40, 3), (70, 4), (float('inf'), 5)]

# ── Strategy 6: Sliding window decomposition ─────────────────────────────────
WINDOW_SIZE     = 22           # periods per window
WINDOW_STEP     = 14           # step between consecutive window starts
WINDOW_T_THRESH = 40           # activate windowed TS when inst.T > this
WINDOW_SWEEPS   = 40           # max TS sweeps per individual window

# ── Cross-run PR budget (Strategy 3) ─────────────────────────────────────────
CROSS_PR_TIME   = 300.0        # max seconds for post-hoc cross-run PR
CROSS_PR_TOP    = 5            # consider top-N runs for cross-run PR pairs


# ══════════════════════════════════════════════════════════════════════════════
# 1. DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Instance:
    """Complete PSP instance."""
    name:          str
    source_file:   str
    dataset:       str
    T:             int
    J:             int          # includes null process at index J-1
    I:             int
    A:             np.ndarray   # (J, I): production of product i by process j
    demand:        np.ndarray   # (I, T): period demand
    product_names: List[str]
    mip_bound:     Optional[float] = None


def _extract_list_literal(text: str, varname: str) -> str:
    """Extract the Python list literal assigned to `varname` from source text."""
    pattern = rf'^{re.escape(varname)}\s*=\s*(\[)'
    m = re.search(pattern, text, re.MULTILINE)
    if not m:
        raise ValueError(f"Variable '{varname}' not found in source")
    start = m.start(1)
    depth = 0
    i = start
    while i < len(text):
        if text[i] == '[':
            depth += 1
        elif text[i] == ']':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    raise ValueError(f"Could not find end of list for '{varname}'")


def load_instance_from_py(py_path: str, name: str, dataset: str,
                          mip_bound: Optional[float] = None) -> Instance:
    """Load PSP instance from a GAMSPy .py file (exact match with MIP data)."""
    with open(py_path, encoding='utf-8') as f:
        content = f.read()

    prods_str = _extract_list_literal(content, 'PRODUCTS')
    products: List[str] = ast.literal_eval(prods_str)
    I = len(products)
    prod_idx = {p: i for i, p in enumerate(products)}

    m = re.search(r'^NUM_PROCESSES\s*=\s*(\d+)', content, re.MULTILINE)
    J = int(m.group(1)) if m else 159
    m = re.search(r'^NUM_PERIODS\s*=\s*(\d+)', content, re.MULTILINE)
    T = int(m.group(1)) if m else 19

    a_str = _extract_list_literal(content, 'A_RECORDS')
    a_records = ast.literal_eval(a_str)
    A = np.zeros((J + 1, I), dtype=np.float64)
    for rec in a_records:
        prod, j_str, val = rec[0], rec[1], float(rec[2])
        j = int(j_str) - 1
        if prod in prod_idx and 0 <= j < J:
            A[j, prod_idx[prod]] = val
    # Row J: null process — A[J,:] = 0 (already zero)

    d_str = _extract_list_literal(content, 'D_RECORDS')
    d_records = ast.literal_eval(d_str)
    demand = np.zeros((I, T), dtype=np.float64)
    for rec in d_records:
        prod, t_str, val = rec[0], rec[1], float(rec[2])
        t = int(t_str) - 1
        if prod in prod_idx and 0 <= t < T:
            demand[prod_idx[prod], t] = val

    return Instance(
        name=name, source_file=str(py_path), dataset=dataset,
        T=T, J=J + 1, I=I,
        A=A, demand=demand,
        product_names=products, mip_bound=mip_bound,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 2. SOLUTION & EVALUATION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(eq=False)
class Solution:
    scheduling: np.ndarray   # (T,) — 0-indexed process per period
    Z:          float
    stock:      np.ndarray   # (I, T+1) cumulative inventory
    time_found: float = 0.0
    iteration:  int   = 0

    def __lt__(self, other: 'Solution') -> bool:
        return self.Z < other.Z

    def copy(self) -> 'Solution':
        return Solution(
            scheduling=self.scheduling.copy(), Z=self.Z,
            stock=self.stock.copy(),
            time_found=self.time_found, iteration=self.iteration,
        )

    def hamming(self, other: 'Solution') -> int:
        return int(np.sum(self.scheduling != other.scheduling))


def evaluate(scheduling: np.ndarray, A: np.ndarray,
             demand: np.ndarray, T: int, I: int) -> Tuple[float, np.ndarray]:
    """
    Compute objective Z and cumulative stock.
    stock[i, t+1] = cumulative (production − demand) through period t.
    F[i,t] = max(0, −stock[i,t+1])  (shortage)
    E[i,t] = max(0,  stock[i,t+1])  (excess)
    Z = ΣΣ F[i,t] + 0.001·E[i,t]  — identical to EQ_OBJ in GAMSPy model.
    """
    stock = np.zeros((I, T + 1), dtype=np.float64)
    for t in range(T):
        j = scheduling[t]
        stock[:, t + 1] = stock[:, t] + A[j, :] - demand[:, t]
    neg = np.minimum(stock[:, 1:], 0.0)
    pos = np.maximum(stock[:, 1:], 0.0)
    Z = float(-neg.sum() + PESO_ESTOQUE * pos.sum())
    return Z, stock


def make_solution(scheduling: np.ndarray, inst: Instance,
                  t_start: float = 0.0, iteration: int = 0) -> Solution:
    Z, stock = evaluate(scheduling, inst.A, inst.demand, inst.T, inst.I)
    return Solution(scheduling=scheduling, Z=Z, stock=stock,
                    time_found=time.perf_counter() - t_start,
                    iteration=iteration)


# ══════════════════════════════════════════════════════════════════════════════
# 3. CONSTRUCTION FITNESS
# ══════════════════════════════════════════════════════════════════════════════

def _greedy_fitness(A: np.ndarray, demand: np.ndarray,
                    t: int, T: int, look_ahead: int, v: int,
                    stock_cur: np.ndarray) -> np.ndarray:
    """Score every process j for assignment to period t (higher = better)."""
    J = A.shape[0]
    production = A.copy()
    fitness = np.zeros(J)
    for tt in range(t, min(t + look_ahead, T)):
        net_demand = demand[:, tt] - (stock_cur if tt == t else 0)
        production -= net_demand[np.newaxis, :]
        w = float((tt - t + 1) ** v) if v > 0 else 1.0
        neg = np.minimum(production, 0.0)
        pos = np.maximum(production, 0.0)
        fitness += neg.sum(axis=1) / w
        fitness -= PESO_ESTOQUE * pos.sum(axis=1)
    return fitness


# ══════════════════════════════════════════════════════════════════════════════
# STRATEGY 2 — Reactive GRASP: adaptive α management
# ══════════════════════════════════════════════════════════════════════════════

class ReactiveGRASP:
    """
    Probability distribution over RCL threshold α values.

    α = 0: pure greedy (only best-fitness process qualifies for RCL).
    α = 1: fully random (all processes qualify).

    Weights are updated via EMA proportional to relative solution quality.
    """
    def __init__(self, rng: np.random.Generator):
        self._rng = rng
        self.weights = np.ones(len(ALPHA_VALUES), dtype=np.float64)
        self._best_z_ref: Optional[float] = None

    def select(self) -> Tuple[float, int]:
        """Return (α_value, α_index) sampled proportional to weights."""
        probs = self.weights / self.weights.sum()
        idx = int(self._rng.choice(len(ALPHA_VALUES), p=probs))
        return float(ALPHA_VALUES[idx]), idx

    def update(self, alpha_idx: int, z_found: float) -> None:
        """Update weight for alpha_idx based on quality of z_found."""
        if self._best_z_ref is None or z_found < self._best_z_ref:
            self._best_z_ref = z_found
        ref = self._best_z_ref
        quality = ref / z_found if z_found > 0 and ref > 0 else 1.0
        self.weights[alpha_idx] = (
            (1.0 - REACTIVE_DECAY) * self.weights[alpha_idx]
            + REACTIVE_DECAY * quality
        )
        self.weights = np.maximum(self.weights, 1e-4)


# ══════════════════════════════════════════════════════════════════════════════
# 4. CONSTRUCTION (greedy-randomised with Reactive GRASP α)
# ══════════════════════════════════════════════════════════════════════════════

def construct(inst: Instance, rng: np.random.Generator,
              look_ahead: int, v: int,
              alpha: float = 0.15,
              t_start: float = 0.0, iteration: int = 0) -> Solution:
    """
    Greedy-randomised construction using RCL threshold (Strategy 2).

    Candidate list for period t: all processes j with
        fitness(j) >= f_max - alpha * (f_max - f_min)
    alpha=0 → pure greedy;  alpha=1 → all processes eligible.
    """
    scheduling = np.zeros(inst.T, dtype=np.int32)
    stock_cur  = np.zeros(inst.I, dtype=np.float64)

    for t in range(inst.T):
        fitness   = _greedy_fitness(inst.A, inst.demand, t, inst.T,
                                    look_ahead, v, stock_cur)
        f_max     = float(fitness.max())
        f_min     = float(fitness.min())
        threshold = f_max - alpha * (f_max - f_min)
        candidates = np.where(fitness >= threshold)[0]
        if len(candidates) == 0:
            candidates = np.array([int(np.argmax(fitness))], dtype=np.intp)
        j = int(rng.choice(candidates))
        scheduling[t] = j
        stock_cur = stock_cur + inst.A[j, :] - inst.demand[:, t]

    return make_solution(scheduling, inst, t_start, iteration)


# ══════════════════════════════════════════════════════════════════════════════
# 5. TABU SEARCH (with optional active_periods for windowed TS — Strategy 6)
# ══════════════════════════════════════════════════════════════════════════════

def tabu_search(sol: Solution, inst: Instance,
                rng: np.random.Generator,
                lrc_history: np.ndarray,
                max_sweeps: int = TABU_SWEEPS,
                t_start: float = 0.0,
                iteration: int = 0,
                time_limit: float = float('inf'),
                active_periods: Optional[np.ndarray] = None) -> Solution:
    """
    Enhanced Tabu Search.

    Neighbourhood:
      • Single-period substitution (restricted to active_periods if provided)
      • 2-opt period-pair swap (every 5th sweep, within active_periods)

    Enhancements:
      • Randomised tabu tenure in [TABU_TENURE_LO, TABU_TENURE_HI]
      • Aspiration: accept tabu move if it improves global best
      • lrc_history-guided candidate set
      • Early termination after 5 non-improving sweeps

    Args:
        active_periods: if provided, only these period indices are explored
                        in the substitution sweep (Strategy 6 — windowed TS).
    """
    best  = sol.copy()
    sched = sol.scheduling.copy()
    tabu  = np.zeros((inst.T, inst.J), dtype=np.int32)
    iter_count = 0
    no_improve = 0

    periods = active_periods if active_periods is not None else np.arange(inst.T)

    while iter_count < max_sweeps:
        if time.perf_counter() - t_start > time_limit:
            break
        iter_count += 1
        improved = False

        # ── Single-substitution sweep (over active periods only) ──────────
        for t in periods:
            tenure  = int(rng.integers(TABU_TENURE_LO, TABU_TENURE_HI + 1))
            j_out   = int(sched[t])
            tabu[t, j_out] = iter_count + tenure

            candidates = np.where(lrc_history[t] > 0)[0]
            if len(candidates) == 0:
                candidates = np.arange(inst.J)

            best_j   = j_out
            best_z_t = float('inf')
            n_try    = min(len(candidates), LRC_SIZE * 3)
            sample   = rng.choice(candidates, size=n_try, replace=False)
            for j_try in sample:
                if j_try == j_out:
                    continue
                is_tabu = (tabu[t, j_try] > 0 and iter_count < tabu[t, j_try])
                sched[t] = j_try
                Z_try, _ = evaluate(sched, inst.A, inst.demand, inst.T, inst.I)
                if not is_tabu or Z_try < best.Z:
                    if Z_try < best_z_t:
                        best_z_t = Z_try
                        best_j   = j_try
                sched[t] = j_out

            sched[t] = best_j
            if best_j != j_out:
                Z_new, st_new = evaluate(sched, inst.A, inst.demand,
                                         inst.T, inst.I)
                if Z_new < best.Z:
                    best = Solution(scheduling=sched.copy(), Z=Z_new,
                                    stock=st_new,
                                    time_found=time.perf_counter() - t_start,
                                    iteration=iteration)
                    improved = True

        # ── 2-opt period-swap sweep (every 5 sweeps, within active periods) ─
        if iter_count % 5 == 0 and len(periods) >= 2:
            n_pairs = min(len(periods) * (len(periods) - 1) // 2, 40)
            for _ in range(n_pairs):
                i1, i2 = rng.integers(0, len(periods), size=2)
                if i1 == i2:
                    continue
                t1, t2 = int(periods[i1]), int(periods[i2])
                j1, j2 = int(sched[t1]), int(sched[t2])
                if j1 == j2:
                    continue
                is_tabu = ((tabu[t1, j2] > 0 and iter_count < tabu[t1, j2]) or
                           (tabu[t2, j1] > 0 and iter_count < tabu[t2, j1]))
                sched[t1], sched[t2] = j2, j1
                Z_swap, st_swap = evaluate(sched, inst.A, inst.demand,
                                           inst.T, inst.I)
                if Z_swap < best.Z and (not is_tabu):
                    best = Solution(scheduling=sched.copy(), Z=Z_swap,
                                    stock=st_swap,
                                    time_found=time.perf_counter() - t_start,
                                    iteration=iteration)
                    improved = True
                else:
                    sched[t1], sched[t2] = j1, j2

        if not improved:
            no_improve += 1
            if no_improve >= 5:
                break
        else:
            no_improve = 0

    return best


# ══════════════════════════════════════════════════════════════════════════════
# STRATEGY 6 — Sliding window Tabu Search
# ══════════════════════════════════════════════════════════════════════════════

def _sliding_window_ts(sol: Solution, inst: Instance,
                       rng: np.random.Generator,
                       lrc_history: np.ndarray,
                       t_start: float,
                       iteration: int,
                       time_limit: float) -> Solution:
    """
    Apply TS over sequential overlapping windows of the schedule.

    For T > WINDOW_T_THRESH each window covers WINDOW_SIZE consecutive periods.
    The tabu table spans the full schedule; only active periods are explored per
    window call. This reduces evaluations per TS sweep from O(T) to O(W) while
    keeping WINDOW_SWEEPS quick passes per region.

    Window layout (W=22, step=14):
      T=38: [0:22], [14:36], [22:38]   → 3 windows
      T=57: [0:22], [14:36], [28:50], [36:57] → 4 windows
      T=76: [0:22], [14:36], [28:50], [42:64], [54:76] → 5 windows
      T=95: [0:22], ..., [70:92], [73:95] → 7 windows
    """
    T    = inst.T
    best = sol.copy()

    w_start = 0
    while w_start < T:
        if time.perf_counter() - t_start >= time_limit:
            break
        w_end   = min(w_start + WINDOW_SIZE, T)
        active  = np.arange(w_start, w_end, dtype=np.int32)
        best    = tabu_search(best, inst, rng, lrc_history,
                              max_sweeps=WINDOW_SWEEPS,
                              t_start=t_start, iteration=iteration,
                              time_limit=time_limit,
                              active_periods=active)
        # Advance window; ensure last window always reaches end
        next_start = w_start + WINDOW_STEP
        if next_start < T and next_start + WINDOW_SIZE > T:
            next_start = max(T - WINDOW_SIZE, w_start + 1)
        w_start = next_start

    return best


# ══════════════════════════════════════════════════════════════════════════════
# STRATEGY 4 — Or-opt block reinsertion (VND neighbourhood)
# ══════════════════════════════════════════════════════════════════════════════

def _or_opt_sweep(sol: Solution, inst: Instance,
                  rng: np.random.Generator,
                  t_start: float, iteration: int, time_limit: float,
                  k_size: int = 1) -> Solution:
    """
    Or-opt: randomly try reinserting a contiguous block of k_size periods
    at a different position in the schedule. Accept first improving move.

    For PSP, reinserting a block changes *when* certain processes run, which
    directly affects the cumulative stock balance across periods.
    """
    T = inst.T
    if T <= k_size + 1:
        return sol

    best  = sol.copy()
    sched = best.scheduling.copy()

    for _ in range(OR_OPT_TRIES):
        if time.perf_counter() - t_start >= time_limit:
            break

        # Random block start; random insertion index in remaining (len = T - k_size)
        t1  = int(rng.integers(0, T - k_size + 1))
        ins = int(rng.integers(0, T - k_size + 1))
        if ins == t1:          # no-op: block returns to same position
            continue

        block     = sched[t1 : t1 + k_size].copy()
        remaining = np.concatenate([sched[:t1], sched[t1 + k_size:]])
        ins       = min(ins, len(remaining))   # guard
        new_sched = np.concatenate(
            [remaining[:ins], block, remaining[ins:]]
        ).astype(np.int32)

        if len(new_sched) != T:
            continue  # safety

        Z_new, st_new = evaluate(new_sched, inst.A, inst.demand, T, inst.I)
        if Z_new < best.Z:
            best = Solution(scheduling=new_sched.copy(), Z=Z_new, stock=st_new,
                            time_found=time.perf_counter() - t_start,
                            iteration=iteration)
            sched = new_sched.copy()

    return best


# ══════════════════════════════════════════════════════════════════════════════
# STRATEGY 4 — VND local search (TS + Or-opt k=1,2,3)
# ══════════════════════════════════════════════════════════════════════════════

def _vnd_local_search(sol: Solution, inst: Instance,
                      rng: np.random.Generator,
                      lrc_history: np.ndarray,
                      t_start: float, iteration: int,
                      time_limit: float) -> Solution:
    """
    Variable Neighborhood Descent as the local search within ILS.

    Neighborhoods:
      N0: Tabu Search (full for T ≤ WINDOW_T_THRESH; sliding-window otherwise)
      N1: Or-opt reinsertion, block size 1
      N2: Or-opt reinsertion, block size 2
      N3: Or-opt reinsertion, block size 3

    Cycling: improvement at Nk → restart at N0; no improvement → advance to N(k+1).
    """
    use_window = inst.T > WINDOW_T_THRESH
    best = sol.copy()
    k    = 0

    while k <= 3 and time.perf_counter() - t_start < time_limit:
        if k == 0:
            candidate = (
                _sliding_window_ts(best, inst, rng, lrc_history,
                                   t_start, iteration, time_limit)
                if use_window else
                tabu_search(best, inst, rng, lrc_history,
                            max_sweeps=TABU_SWEEPS,
                            t_start=t_start, iteration=iteration,
                            time_limit=time_limit)
            )
        else:
            candidate = _or_opt_sweep(best, inst, rng,
                                      t_start, iteration, time_limit,
                                      k_size=k)

        if candidate.Z < best.Z - 1e-9:
            best = candidate
            k    = 0          # restart from N0
        else:
            k   += 1          # try next neighbourhood

    return best


# ══════════════════════════════════════════════════════════════════════════════
# STRATEGY 5 — Adaptive multi-bridge perturbation
# ══════════════════════════════════════════════════════════════════════════════

def adaptive_perturb(sol: Solution, inst: Instance,
                     rng: np.random.Generator,
                     t_start: float = 0.0,
                     iteration: int = 0) -> Solution:
    """
    Multi-bridge perturbation scaled to T (Strategy 5).

    Number of cuts:
      T ≤ 40  → 3 cuts (double-bridge):    A|C|B|D
      T ≤ 70  → 4 cuts (triple-bridge):    A|C|D|B|E
      T > 70  → 5 cuts (quadruple-bridge): A|C|E|B|D|F

    Larger T → more cuts → stronger perturbation, escaping wider local optima.
    """
    T = inst.T
    n_cuts = next(nc for (th, nc) in BRIDGE_THRESHOLDS if T <= th)

    if T < n_cuts + 1:
        # Too short for multi-bridge — random 3-period perturbation
        new_sched = sol.scheduling.copy()
        positions = rng.choice(T, size=min(3, T), replace=False)
        for pos in positions:
            new_sched[pos] = int(rng.integers(0, inst.J))
        return make_solution(new_sched, inst, t_start, iteration)

    cuts = sorted(rng.choice(np.arange(1, T), size=n_cuts, replace=False).tolist())
    s    = sol.scheduling

    if n_cuts == 3:
        c1, c2, c3 = cuts
        # Classic double-bridge: A|C|B|D
        new_sched = np.concatenate([s[0:c1], s[c2:c3], s[c1:c2], s[c3:T]])

    elif n_cuts == 4:
        c1, c2, c3, c4 = cuts
        # Triple-bridge: A|C|D|B|E  (rotate middle 3 segments: B→last, C→first, D→middle)
        new_sched = np.concatenate([s[0:c1], s[c2:c3], s[c3:c4], s[c1:c2], s[c4:T]])

    else:  # n_cuts == 5
        c1, c2, c3, c4, c5 = cuts
        # Quadruple-bridge: A|C|E|B|D|F  (interleave odd and even segments)
        new_sched = np.concatenate([
            s[0:c1], s[c2:c3], s[c4:c5],
            s[c1:c2], s[c3:c4], s[c5:T]
        ])

    return make_solution(new_sched.astype(np.int32), inst, t_start, iteration)


# ══════════════════════════════════════════════════════════════════════════════
# 6. PATH RELINKING
# ══════════════════════════════════════════════════════════════════════════════

def path_relinking(src: Solution, tgt: Solution,
                   inst: Instance,
                   t_start: float = 0.0,
                   iteration: int = 0) -> Solution:
    """Best-admissible forward + backward path relinking."""

    def _one_dir(s: Solution, target: Solution) -> Solution:
        path_best = s.copy()
        sched = s.scheduling.copy()
        remaining = set(np.where(sched != target.scheduling)[0].tolist())
        while remaining:
            best_z = float('inf'); best_t = -1; best_j = -1
            for t in remaining:
                j_tgt = int(target.scheduling[t])
                old_j = int(sched[t])
                sched[t] = j_tgt
                Z_s, _ = evaluate(sched, inst.A, inst.demand, inst.T, inst.I)
                if Z_s < best_z:
                    best_z = Z_s; best_t = t; best_j = j_tgt
                sched[t] = old_j
            sched[best_t] = best_j
            remaining.discard(best_t)
            Z_p, st_p = evaluate(sched, inst.A, inst.demand, inst.T, inst.I)
            if Z_p < path_best.Z:
                path_best = Solution(
                    scheduling=sched.copy(), Z=Z_p, stock=st_p,
                    time_found=time.perf_counter() - t_start,
                    iteration=iteration)
        return path_best

    fwd = _one_dir(src, tgt)
    bwd = _one_dir(tgt, src)
    return fwd if fwd.Z <= bwd.Z else bwd


# ══════════════════════════════════════════════════════════════════════════════
# 7. ELITE SET
# ══════════════════════════════════════════════════════════════════════════════

class EliteSet:
    def __init__(self, max_size: int = ELITE_SIZE,
                 min_dist: int = MIN_ELITE_DIST):
        self.solutions: List[Solution] = []
        self.max_size  = max_size
        self.min_dist  = min_dist

    def __len__(self) -> int:
        return len(self.solutions)

    def try_add(self, sol: Solution) -> bool:
        for idx, e in enumerate(self.solutions):
            if sol.hamming(e) < self.min_dist:
                if sol.Z < e.Z:
                    self.solutions[idx] = sol.copy()
                    return True
                return False
        if len(self.solutions) < self.max_size:
            self.solutions.append(sol.copy())
            return True
        worst = max(range(len(self.solutions)),
                    key=lambda k: self.solutions[k].Z)
        if sol.Z < self.solutions[worst].Z:
            self.solutions[worst] = sol.copy()
            return True
        return False

    def random_partner(self, rng: np.random.Generator,
                       exclude: Solution) -> Optional[Solution]:
        candidates = [e for e in self.solutions
                      if e.hamming(exclude) >= self.min_dist]
        if not candidates:
            candidates = self.solutions
        return rng.choice(candidates) if candidates else None  # type: ignore


# ══════════════════════════════════════════════════════════════════════════════
# 8. MAIN GRASP + ILS RUN (integrates all strategies)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ILSResult:
    instance:      str
    dataset:       str
    run_id:        int
    seed:          int
    algo_version:  str
    objective:     float
    shortage:      float
    excess:        float
    gap_vs_mip:    Optional[float]
    time_to_best:  float
    total_time:    float
    iterations:    int          # total ILS perturbation count
    grasp_iters:   int          # total GRASP constructions
    improvements:  List[Dict]
    scheduling:    List[int]    # 1-indexed; null process reported as 0


def run_grasp_ils(inst: Instance,
                  time_limit_s: float = 3600.0,
                  run_id: int = 1,
                  seed: Optional[int] = None) -> ILSResult:
    """
    GRASP + ILS single run — v2.0 with all five enhancement strategies.

    Phase 1 (20% time): Reactive GRASP warm-up + VND → build elite set + lrc_history
    Phase 2 (80% time): ILS loop
        ├── Adaptive multi-bridge perturbation (Strategy 5)
        ├── VND local search: windowed TS + Or-opt (Strategies 4 & 6)
        ├── Best-accept criterion
        ├── Intra-run path relinking every PR_FREQ improvements
        └── GRASP restart after ILS_NO_IMPROVE_LIMIT non-improving iterations
    """
    if seed is None:
        seed = random.randint(0, 2 ** 31 - 1)
    rng     = np.random.default_rng(seed)
    t_start = time.perf_counter()

    elite        = EliteSet()
    lrc_history  = np.zeros((inst.T, inst.J), dtype=np.int32)
    improvements: List[Dict] = []
    grasp_iters  = 0
    ils_iters    = 0
    pr_counter   = 0
    reactive     = ReactiveGRASP(rng)   # Strategy 2

    def elapsed() -> float:
        return time.perf_counter() - t_start

    def _build_lrc_history(sol: Solution, look_ahead: int, v: int, alpha: float):
        """Track RCL membership for lrc_history-guided TS."""
        stock_cur = np.zeros(inst.I)
        for t in range(inst.T):
            fit_t = _greedy_fitness(inst.A, inst.demand, t, inst.T,
                                    look_ahead, v, stock_cur)
            f_max = float(fit_t.max())
            f_min = float(fit_t.min())
            thresh = f_max - alpha * (f_max - f_min)
            in_lrc = np.where(fit_t >= thresh)[0]
            if len(in_lrc) == 0:
                in_lrc = np.array([int(np.argmax(fit_t))])
            lrc_history[t, in_lrc] += 1
            j = int(sol.scheduling[t])
            stock_cur = stock_cur + inst.A[j, :] - inst.demand[:, t]

    best_overall: Optional[Solution] = None

    def _update_best(sol: Solution, tag: str = '') -> bool:
        nonlocal best_overall
        if best_overall is None or sol.Z < best_overall.Z:
            best_overall = sol.copy()
            entry: Dict = {
                "iteration": ils_iters,
                "grasp_iter": grasp_iters,
                "time_s": round(sol.time_found, 3),
                "Z": round(sol.Z, 6),
            }
            if tag:
                entry["tag"] = tag
            improvements.append(entry)
            logger.debug(
                f"  [{inst.name} run {run_id}] {tag} "
                f"iter={ils_iters} Z={sol.Z:.3f} t={sol.time_found:.1f}s"
            )
            return True
        return False

    # ──────────────────────────────────────────────────────────────────────
    # Phase 1: Reactive GRASP warm-up (first 20% of time, min 5 constructions)
    # ──────────────────────────────────────────────────────────────────────
    warmup_limit  = min(time_limit_s * 0.20, time_limit_s - 60.0)
    warmup_iters  = 0

    while elapsed() < warmup_limit or warmup_iters < 5:
        if elapsed() >= time_limit_s:
            break
        warmup_iters += 1
        grasp_iters  += 1

        look_ahead = int(rng.integers(LOOK_AHEAD_LO, LOOK_AHEAD_HI + 1))
        v          = int(rng.integers(0, V_MAX + 1))
        alpha, a_idx = reactive.select()                      # Strategy 2

        sol = construct(inst, rng, look_ahead, v, alpha, t_start, grasp_iters)
        reactive.update(a_idx, sol.Z)                         # Strategy 2
        _build_lrc_history(sol, look_ahead, v, alpha)

        sol = _vnd_local_search(sol, inst, rng, lrc_history,  # Strategy 4+6
                                t_start, grasp_iters,
                                t_start + time_limit_s)

        _update_best(sol, 'GRASP_warmup')
        elite.try_add(sol)

    # ──────────────────────────────────────────────────────────────────────
    # Phase 2: ILS main loop
    # ──────────────────────────────────────────────────────────────────────
    ils_no_improve = 0

    while elapsed() < time_limit_s:
        ils_iters += 1

        # Strategy 5: adaptive multi-bridge perturbation
        x_perturbed = adaptive_perturb(
            best_overall, inst, rng, t_start, ils_iters)
        # Strategy 4+6: VND local search (windowed TS + Or-opt)
        x_ls = _vnd_local_search(
            x_perturbed, inst, rng, lrc_history,
            t_start, ils_iters,
            t_start + time_limit_s)

        improved = _update_best(x_ls, 'ILS')
        elite.try_add(x_ls)

        if improved:
            ils_no_improve = 0
            pr_counter    += 1
        else:
            ils_no_improve += 1

        # Intra-run path relinking
        if pr_counter >= PR_FREQ and len(elite) >= 2:
            pr_counter = 0
            partner    = elite.random_partner(rng, best_overall)
            if partner is not None and elapsed() < time_limit_s:
                pr_sol = path_relinking(
                    best_overall, partner, inst, t_start, ils_iters)
                elite.try_add(pr_sol)
                _update_best(pr_sol, 'PR')

        # Reactive GRASP restart when stuck
        if ils_no_improve >= ILS_NO_IMPROVE_LIMIT:
            ils_no_improve = 0
            grasp_iters   += 1
            look_ahead = int(rng.integers(LOOK_AHEAD_LO, LOOK_AHEAD_HI + 1))
            v          = int(rng.integers(0, V_MAX + 1))
            alpha, a_idx = reactive.select()
            sol_new = construct(inst, rng, look_ahead, v, alpha, t_start, grasp_iters)
            reactive.update(a_idx, sol_new.Z)
            _build_lrc_history(sol_new, look_ahead, v, alpha)
            sol_new = _vnd_local_search(sol_new, inst, rng, lrc_history,
                                        t_start, grasp_iters,
                                        t_start + time_limit_s)
            _update_best(sol_new, 'GRASP_restart')
            elite.try_add(sol_new)

    total_time = elapsed()

    if best_overall is None:
        look_ahead = int(rng.integers(LOOK_AHEAD_LO, LOOK_AHEAD_HI + 1))
        best_overall = construct(inst, rng, look_ahead, 0, 0.15, t_start, 0)

    st       = best_overall.stock[:, 1:]
    shortage = float(-np.sum(np.minimum(st, 0.0)))
    excess   = float( np.sum(np.maximum(st, 0.0)))

    gap_vs_mip = None
    if inst.mip_bound is not None and inst.mip_bound > 0:
        gap_vs_mip = round(
            (best_overall.Z - inst.mip_bound) / inst.mip_bound * 100, 4)

    return ILSResult(
        instance=inst.name, dataset=inst.dataset,
        run_id=run_id, seed=seed,
        algo_version=ALGO_VERSION,
        objective=round(best_overall.Z, 6),
        shortage=round(shortage, 3),
        excess=round(excess, 3),
        gap_vs_mip=gap_vs_mip,
        time_to_best=round(best_overall.time_found, 3),
        total_time=round(total_time, 3),
        iterations=ils_iters,
        grasp_iters=grasp_iters,
        improvements=improvements,
        scheduling=[0 if int(j) == inst.J - 1 else int(j) + 1
                    for j in best_overall.scheduling],
    )


# ══════════════════════════════════════════════════════════════════════════════
# 9. MULTI-RUN ORCHESTRATION & I/O
# ══════════════════════════════════════════════════════════════════════════════

def _worker_run(args: tuple) -> dict:
    """
    Top-level worker function for multiprocessing.Pool.
    Loads the instance independently in each worker (avoids pickle overhead).
    """
    py_path, name, dataset, mip_bound, time_limit_s, run_id, seed, out_dir = args
    inst   = load_instance_from_py(py_path, name, dataset, mip_bound)
    result = run_grasp_ils(inst, time_limit_s=time_limit_s,
                           run_id=run_id, seed=seed)

    run_file = os.path.join(out_dir, f"{name}_run{run_id:02d}.json")
    with open(run_file, 'w') as f:
        json.dump({
            "instance":      result.instance,
            "dataset":       result.dataset,
            "run_id":        result.run_id,
            "seed":          result.seed,
            "algo_version":  result.algo_version,
            "objective":     result.objective,
            "shortage":      result.shortage,
            "excess":        result.excess,
            "gap_vs_mip":    result.gap_vs_mip,
            "time_to_best":  result.time_to_best,
            "total_time":    result.total_time,
            "iterations":    result.iterations,
            "grasp_iters":   result.grasp_iters,
            "improvements":  result.improvements,
            "scheduling":    result.scheduling,
            "T": inst.T, "J": inst.J, "I": inst.I,
            "mip_bound":     inst.mip_bound,
        }, f, indent=2)

    return {
        "run_id":       result.run_id,
        "objective":    result.objective,
        "gap_vs_mip":   result.gap_vs_mip,
        "time_to_best": result.time_to_best,
        "iterations":   result.iterations,
        "grasp_iters":  result.grasp_iters,
    }


# ══════════════════════════════════════════════════════════════════════════════
# STRATEGY 3 — Cross-run Path Relinking (post-hoc cooperative search)
# ══════════════════════════════════════════════════════════════════════════════

def _cross_run_pr(run_dicts: List[dict], inst: Instance,
                  out_dir: str, name: str) -> Optional[float]:
    """
    Load best solutions from all completed runs and perform path relinking
    between top-N pairs from different workers.

    Returns the best Z found by cross-run PR (or None if no improvement).
    This implements a lightweight cooperative population search without
    requiring real-time inter-process communication.
    """
    solutions: List[Solution] = []

    for rd in run_dicts:
        run_file = os.path.join(out_dir, f"{name}_run{rd['run_id']:02d}.json")
        try:
            with open(run_file) as f:
                data = json.load(f)
            sched_1idx = np.array(data['scheduling'], dtype=np.int32)
            # Convert 1-indexed (0 = null) back to 0-indexed (null = J-1)
            sched_0idx = np.where(
                sched_1idx == 0, inst.J - 1, sched_1idx - 1
            ).astype(np.int32)
            Z, stock = evaluate(sched_0idx, inst.A, inst.demand, inst.T, inst.I)
            solutions.append(Solution(scheduling=sched_0idx, Z=Z, stock=stock))
        except Exception as e:
            logger.warning(f"  cross-run PR: skipped {run_file}: {e}")

    if len(solutions) < 2:
        return None

    solutions.sort(key=lambda s: s.Z)
    best_z_before = solutions[0].Z
    best_z_pr     = best_z_before
    t_pr_start    = time.perf_counter()
    n_top         = min(CROSS_PR_TOP, len(solutions))

    logger.info(f"  cross-run PR: {len(solutions)} solutions, "
                f"best={best_z_before:.3f}, trying {n_top*(n_top-1)//2} pairs …")

    for i in range(n_top):
        for j in range(i + 1, n_top):
            if time.perf_counter() - t_pr_start > CROSS_PR_TIME:
                logger.info("  cross-run PR: time budget exhausted")
                break
            try:
                pr_sol = path_relinking(solutions[i], solutions[j], inst,
                                        t_start=time.perf_counter(), iteration=0)
                if pr_sol.Z < best_z_pr:
                    best_z_pr = pr_sol.Z
                    logger.info(f"  cross-run PR improvement: {pr_sol.Z:.3f}")
            except Exception as e:
                logger.debug(f"  cross-run PR pair ({i},{j}) error: {e}")

    return best_z_pr if best_z_pr < best_z_before - 1e-9 else None


def run_instance(py_path: str, name: str, dataset: str,
                 out_dir: str,
                 mip_bound: Optional[float] = None,
                 n_runs: int = 10,
                 time_limit_s: float = 3600.0,
                 base_seed: Optional[int] = None,
                 n_workers: int = 0) -> Dict:
    """
    Run GRASP+ILS v2.0 n_runs times on one instance and save results.

    After all parallel runs complete, performs cross-run path relinking
    (Strategy 3) between the top CROSS_PR_TOP solutions.
    """
    import multiprocessing as mp
    os.makedirs(out_dir, exist_ok=True)

    inst_info = load_instance_from_py(py_path, name, dataset, mip_bound)
    logger.info(f"Loaded {name} ({dataset}): T={inst_info.T}, J={inst_info.J}, "
                f"I={inst_info.I}  [algo {ALGO_VERSION}]")

    run_args = [
        (py_path, name, dataset, mip_bound, time_limit_s,
         k, (base_seed + k) if base_seed is not None else None, out_dir)
        for k in range(1, n_runs + 1)
    ]

    workers = n_workers if n_workers > 0 else min(n_runs, mp.cpu_count())
    logger.info(f"  Launching {n_runs} runs on {workers} worker(s) …")

    if workers == 1:
        run_dicts = [_worker_run(a) for a in run_args]
    else:
        with mp.Pool(processes=workers) as pool:
            run_dicts = pool.map(_worker_run, run_args)

    for rd in sorted(run_dicts, key=lambda x: x["run_id"]):
        logger.info(
            f"    run{rd['run_id']:02d}: Z={rd['objective']:.3f}  "
            f"t2best={rd['time_to_best']:.1f}s  "
            f"ILS_iters={rd['iterations']}  gap={rd['gap_vs_mip']}%"
        )

    # ── Summary statistics ────────────────────────────────────────────────
    objs      = [rd["objective"]    for rd in run_dicts]
    t2bests   = [rd["time_to_best"] for rd in run_dicts]
    ils_iters = [rd["iterations"]   for rd in run_dicts]
    gaps      = [rd["gap_vs_mip"]   for rd in run_dicts
                 if rd["gap_vs_mip"] is not None]

    summary: Dict = {
        "instance":       name,
        "dataset":        dataset,
        "algo_version":   ALGO_VERSION,
        "T": inst_info.T, "J": inst_info.J, "I": inst_info.I,
        "n_runs":         n_runs,
        "n_workers":      workers,
        "time_limit_s":   time_limit_s,
        "Z_best":         round(min(objs), 6),
        "Z_mean":         round(float(np.mean(objs)), 6),
        "Z_std":          round(float(np.std(objs)), 6),
        "Z_worst":        round(max(objs), 6),
        "t2best_best":    round(min(t2bests), 3),
        "t2best_mean":    round(float(np.mean(t2bests)), 3),
        "ils_iters_mean": round(float(np.mean(ils_iters)), 1),
        "mip_bound":      inst_info.mip_bound,
        "gap_best_vs_mip": round(min(gaps), 4) if gaps else None,
        "gap_mean_vs_mip": round(float(np.mean(gaps)), 4) if gaps else None,
        "cross_run_pr_z":  None,
    }

    # ── Strategy 3: cross-run path relinking ─────────────────────────────
    if len(run_dicts) >= 2:
        pr_best = _cross_run_pr(run_dicts, inst_info, out_dir, name)
        if pr_best is not None and pr_best < summary["Z_best"]:
            logger.info(
                f"  cross-run PR improved Z_best: {pr_best:.3f} < {summary['Z_best']:.3f}"
            )
            summary["Z_best"]         = round(pr_best, 6)
            summary["cross_run_pr_z"] = round(pr_best, 6)
            if inst_info.mip_bound and inst_info.mip_bound > 0:
                summary["gap_best_vs_mip"] = round(
                    (pr_best - inst_info.mip_bound) / inst_info.mip_bound * 100, 4)

    summary_file = os.path.join(out_dir, f"{name}_summary.json")
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    logger.info(f"  Summary -> {summary_file}")
    logger.info(f"  Z_best={summary['Z_best']:.3f}  Z_mean={summary['Z_mean']:.3f}  "
                f"gap_best={summary['gap_best_vs_mip']}%")
    return summary


# ══════════════════════════════════════════════════════════════════════════════
# 10. CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description=f"GRASP+ILS {ALGO_VERSION} for the PSP"
    )
    parser.add_argument("py_file",      help="GAMSPy .py instance file path")
    parser.add_argument("--name",       default=None,
                        help="Instance name (default: stem of py_file)")
    parser.add_argument("--dataset",    default="Unknown",
                        help="Dataset label (2X/3X/4X/5X/Real)")
    parser.add_argument("--out_dir",    default="results_ils_v2",
                        help="Output directory (default: results_ils_v2)")
    parser.add_argument("--n_runs",     type=int,   default=10,
                        help="Number of independent runs (default: 10)")
    parser.add_argument("--time",       type=float, default=3600.0,
                        help="Time limit per run in seconds (default: 3600)")
    parser.add_argument("--mip_bound",  type=float, default=None,
                        help="CPLEX22 best_bound for gap reporting")
    parser.add_argument("--seed",       type=int,   default=None,
                        help="Base random seed")
    parser.add_argument("--workers",    type=int,   default=0,
                        help="Parallel workers (0 = all CPU cores, 1 = sequential)")
    args = parser.parse_args()

    name = args.name or Path(args.py_file).stem

    summary = run_instance(
        py_path=args.py_file,
        name=name,
        dataset=args.dataset,
        out_dir=args.out_dir,
        mip_bound=args.mip_bound,
        n_runs=args.n_runs,
        time_limit_s=args.time,
        base_seed=args.seed,
        n_workers=args.workers,
    )

    print(f"\n{'='*58}")
    print(f"  GRASP+ILS {ALGO_VERSION} — {summary['instance']} ({summary['dataset']})")
    print(f"  Z_best    : {summary['Z_best']:.3f}")
    print(f"  Z_mean    : {summary['Z_mean']:.3f}  ±{summary['Z_std']:.3f}")
    print(f"  gap_best  : {summary['gap_best_vs_mip']}%")
    if summary.get('cross_run_pr_z'):
        print(f"  cross-PR  : {summary['cross_run_pr_z']:.3f}  (post-hoc improvement)")
    print(f"{'='*58}")
