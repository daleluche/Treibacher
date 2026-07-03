"""
GRASP with Tabu Search and Path Relinking
for the Process Selection Problem (PSP) in the electrofused grain industry.

Problem:
    Minimise  Z = ∑_{i,t} F[i,t] + 0.001·E[i,t]
    s.t.      ∑_{j, t'≤t} A[i,j]·X[j,t'] + F[i,t] – E[i,t] = ∑_{t'≤t} D[i,t']  ∀i,t
              ∑_j X[j,t] ≤ 1  ∀t;  X ∈ {0,1};  F,E ≥ 0

Algorithm:
    GRASP construction (greedy-randomised, look-ahead evaluation)
    + Tabu Search local search (forward sweep with backward refinement)
    + Path Relinking post-processing with elite set

References:
    Feo & Resende (1995), Glover (1998), Resende & Ribeiro (2003)
"""

from __future__ import annotations

import re
import time
import random
import json
import copy
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

import numpy as np

logger = logging.getLogger(__name__)

# ── Algorithm hyper-parameters (tunable) ─────────────────────────────────────
PESO_ESTOQUE  = 0.001   # weight of excess stock in objective (matches MIP)
LRC_SIZE      = 7       # Restricted Candidate List size
TABU_TENURE   = 3       # number of iterations a process stays on tabu list
ELITE_SIZE    = 10      # max number of elite solutions for Path Relinking
MIN_ELITE_DIST= 2       # minimum Hamming distance to enter elite set
MAX_TROLL_LO  = 3       # look-ahead window lower bound (randomised each construction)
MAX_TROLL_HI  = 7       # look-ahead window upper bound
V_MAX         = 5       # max exponent for exponential distance decay (randomised)
TABU_ITERS    = 50      # number of Tabu Search sweeps per solution
PR_FREQ       = 5       # trigger Path Relinking every PR_FREQ improvements


# ══════════════════════════════════════════════════════════════════════════════
# 1. INSTANCE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Instance:
    """Complete PSP instance loaded from a .gms file."""
    name:          str
    source_gms:    str
    dataset:       str
    T:             int              # periods
    J:             int              # processes
    I:             int              # products
    A:             np.ndarray       # shape (J, I): A[j,i] = production of product i by process j
    demand:        np.ndarray       # shape (I, T): demand[i,t] period demand (0-indexed t)
    product_names: List[str]


def _parse_table(lines: List[str], start: int) -> Tuple[Dict, int]:
    """Parse a GAMS TABLE block (handles multi-block '+' continuation).
    Returns {(row_label, col_label): value} and the line index after the ';'."""
    result: Dict[Tuple[str,str], float] = {}
    col_headers: List[str] = []
    row_idx = start + 1          # skip 'TABLE ...' declaration line

    while row_idx < len(lines):
        line = lines[row_idx].strip()
        row_idx += 1
        if line == ';':
            break
        if not line or line.startswith('$') or line.startswith('*'):
            continue
        # Column-header row: starts with whitespace (only numbers/names, no label in col-0)
        tokens = line.split()
        if not tokens:
            continue
        # Check if this is a new column-header row
        # It's a header row if it starts with a '+' continuation marker or all tokens are
        # plausible column labels (no ':=' or value assignment)
        if tokens[0] == '+':
            col_headers = tokens[1:]          # new set of column headers (continuation)
            continue
        # Detect header rows: heuristic – if first token looks like a pure integer
        # (the column indices), treat as column header
        try:
            int(tokens[0])
            col_headers = tokens             # numeric column headers
            continue
        except ValueError:
            pass
        # Data row: first token is the row label
        row_label = tokens[0].rstrip(',').strip()
        for k, val_str in enumerate(tokens[1:]):
            if k < len(col_headers):
                try:
                    val = float(val_str)
                    if val != 0.0:
                        result[(row_label, col_headers[k])] = val
                except ValueError:
                    pass

    return result, row_idx


def load_instance(gms_path: str, name: str, dataset: str) -> Instance:
    """Parse a GAMS .gms file and return an Instance object."""
    with open(gms_path, encoding='utf-8', errors='replace') as f:
        content = f.read()
    lines = content.splitlines()

    # ── Number of periods ──────────────────────────────────────────────────
    m = re.search(r'/\s*1\s*\*\s*(\d+)\s*/', content)
    T = int(m.group(1)) if m else 19

    # ── Product list ───────────────────────────────────────────────────────
    products: List[str] = []
    in_prod = False
    for line in lines:
        s = line.strip()
        if re.search(r'\bI\b.*produtos', s, re.IGNORECASE) or \
           (re.search(r'\bI\b', s) and '/' in s and not re.search(r'TABLE|ALIAS', s)):
            in_prod = True
        if in_prod:
            # Extract names on this line (strip leading '/')
            part = re.sub(r'^.*/', '', s) if '/' in s else s
            for tok in re.split(r'[\s,/]+', part):
                tok = tok.strip().rstrip(',').strip()
                if tok and not tok.startswith('*') and tok != '/':
                    products.append(tok)
            if s.endswith('/') or s.endswith('/;'):
                in_prod = False
                break
    # Deduplicate while preserving order
    seen = set()
    unique_products = []
    for p in products:
        if p and p not in seen:
            seen.add(p)
            unique_products.append(p)
    products = unique_products

    # ── Parse TABLE A(I,J) ─────────────────────────────────────────────────
    a_data: Dict[Tuple[str,str], float] = {}
    for i_line, line in enumerate(lines):
        if re.match(r'\s*TABLE\s+A\(', line, re.IGNORECASE):
            a_data, _ = _parse_table(lines, i_line)
            break

    # ── Parse TABLE D(I,T) or TABLE DOG(I,T) ────────────────────────────────
    # Real instances use TABLE D(I,T); 2X/3X/4X/5X use TABLE DOG(I,T) + a
    # GAMS parameter assignment that repeats the 19-period base demand.
    d_data: Dict[Tuple[str,str], float] = {}
    for i_line, line in enumerate(lines):
        if re.match(r'\s*TABLE\s+D(?:OG)?\(', line, re.IGNORECASE):
            d_data, _ = _parse_table(lines, i_line)
            break

    # ── Build numpy arrays (0-indexed) ────────────────────────────────────
    # Determine J from the A table column headers (process indices)
    if a_data:
        J = max(int(c) for _, c in a_data.keys())
    else:
        J = 0

    I = len(products)
    prod_idx = {p: i for i, p in enumerate(products)}

    A = np.zeros((J, I), dtype=np.float64)
    for (prod, proc_str), val in a_data.items():
        if prod in prod_idx:
            j = int(proc_str) - 1   # 0-indexed
            i = prod_idx[prod]
            if 0 <= j < J:
                A[j, i] = val

    # DOG demand: if T > 19, repeat base-19 demand
    BASE_T = 19
    demand = np.zeros((I, T), dtype=np.float64)
    for (prod, t_str), val in d_data.items():
        if prod in prod_idx:
            t_orig = int(t_str) - 1   # 0-indexed
            i = prod_idx[prod]
            if T > BASE_T:
                # propagate to all repetitions
                while t_orig < T:
                    if t_orig < T:
                        demand[i, t_orig] = val
                    t_orig += BASE_T
            else:
                if t_orig < T:
                    demand[i, t_orig] = val

    return Instance(
        name=name, source_gms=str(gms_path), dataset=dataset,
        T=T, J=J, I=I, A=A, demand=demand, product_names=products
    )


# ══════════════════════════════════════════════════════════════════════════════
# 2. SOLUTION EVALUATION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(eq=False)
class Solution:
    """A complete PSP solution."""
    scheduling: np.ndarray   # shape (T,): scheduling[t] = process j (0-indexed)
    Z:          float        # objective value (minimise)
    stock:      np.ndarray   # shape (I, T+1): cumulative stock balance
    time_found: float = 0.0  # wall-clock time when found (seconds from start)
    iteration:  int   = 0    # iteration at which found

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Solution): return NotImplemented
        return bool(self.Z == other.Z and np.array_equal(self.scheduling, other.scheduling))

    def __lt__(self, other: Solution) -> bool:
        return self.Z < other.Z

    def copy(self) -> Solution:
        return Solution(
            scheduling=self.scheduling.copy(),
            Z=self.Z,
            stock=self.stock.copy(),
            time_found=self.time_found,
            iteration=self.iteration,
        )

    def hamming(self, other: Solution) -> int:
        """Hamming distance (number of periods with different process)."""
        return int(np.sum(self.scheduling != other.scheduling))


def evaluate(scheduling: np.ndarray, A: np.ndarray, demand: np.ndarray,
             T: int, I: int) -> Tuple[float, np.ndarray]:
    """Compute exact objective Z and cumulative stock array.

    Z = ∑_{i,t} max(0, –stock[i,t]) + PESO_ESTOQUE · max(0, stock[i,t])
    """
    stock = np.zeros((I, T + 1), dtype=np.float64)
    for t in range(T):
        j = scheduling[t]
        stock[:, t + 1] = stock[:, t] + A[j, :] - demand[:, t]
    neg = np.minimum(stock[:, 1:], 0.0)
    pos = np.maximum(stock[:, 1:], 0.0)
    Z = -neg.sum() + PESO_ESTOQUE * pos.sum()
    return float(Z), stock


# ══════════════════════════════════════════════════════════════════════════════
# 3. GREEDY EVALUATION (vectorised over all J processes)
# ══════════════════════════════════════════════════════════════════════════════

def _greedy_fitness(A: np.ndarray, demand: np.ndarray,
                    t: int, T: int, max_troll: int, v: int,
                    current_stock: np.ndarray) -> np.ndarray:
    """Return fitness score for every process j when assigned to period t.

    Simulates process j's output being consumed by net demands over the next
    max_troll periods; uses exponential distance decay with exponent v.

    Args:
        A:             (J, I) production rates
        demand:        (I, T) period demands (0-indexed)
        t:             current period index (0-indexed)
        T:             total number of periods
        max_troll:     look-ahead window
        v:             exponential decay exponent (0 = uniform, higher = near-sighted)
        current_stock: (I,) cumulative stock at start of period t (= end of t-1)

    Returns:
        fitness: (J,) scores — higher (closer to 0) is better
    """
    J = A.shape[0]
    production = A.copy()           # (J, I): cumulative production balance in look-ahead
    fitness = np.zeros(J, dtype=np.float64)

    for tt in range(t, min(t + max_troll, T)):
        if tt == t:
            net_demand = demand[:, tt] - current_stock   # (I,)
        else:
            net_demand = demand[:, tt]                   # future: no stock offset
        production -= net_demand[np.newaxis, :]          # (J, I) broadcast

        w = (tt - t + 1) ** v if v > 0 else 1.0
        neg = np.minimum(production, 0.0)
        pos = np.maximum(production, 0.0)
        fitness += neg.sum(axis=1) / w
        fitness -= PESO_ESTOQUE * pos.sum(axis=1)

    return fitness                  # maximise (less negative = better)


# ══════════════════════════════════════════════════════════════════════════════
# 4. CONSTRUCTION PHASE
# ══════════════════════════════════════════════════════════════════════════════

def construct(inst: Instance, rng: np.random.Generator,
              max_troll: int, v: int,
              t_start: float = 0.0, iteration: int = 0) -> Solution:
    """Greedy-randomised construction of one PSP solution.

    For each period t (in order):
      1. Evaluate all J processes using the look-ahead function.
      2. Build an LRC of the best LRC_SIZE processes.
      3. Randomly select one process from the LRC.
      4. Update the cumulative stock.

    Returns a fully evaluated Solution object.
    """
    scheduling = np.zeros(inst.T, dtype=np.int32)
    stock_cur = np.zeros(inst.I, dtype=np.float64)  # stock at end of prev period

    for t in range(inst.T):
        fitness = _greedy_fitness(inst.A, inst.demand, t, inst.T,
                                  max_troll, v, stock_cur)
        lrc_idx = np.argpartition(-fitness, min(LRC_SIZE, inst.J) - 1)[:LRC_SIZE]
        j = int(rng.choice(lrc_idx))
        scheduling[t] = j
        stock_cur = stock_cur + inst.A[j, :] - inst.demand[:, t]

    Z, stock = evaluate(scheduling, inst.A, inst.demand, inst.T, inst.I)
    return Solution(scheduling=scheduling, Z=Z, stock=stock,
                    time_found=time.perf_counter() - t_start,
                    iteration=iteration)


# ══════════════════════════════════════════════════════════════════════════════
# 5. TABU SEARCH LOCAL SEARCH
# ══════════════════════════════════════════════════════════════════════════════

def tabu_search(sol: Solution, inst: Instance,
                lrc_history: np.ndarray,
                rng: np.random.Generator,
                max_iter: int,
                t_start: float = 0.0,
                iteration: int = 0,
                time_limit: float = float('inf')) -> Solution:
    """Tabu Search local search starting from a given solution.

    Strategy (faithful to the Delphi implementation):
      - Outer loop: 'max_iter' sweeps over all periods.
      - For each period t:
          * Remove current process (add to tabu list with current tenure).
          * Sample a candidate from LRC (80%) or random (20%).
          * Accept if not tabu (or tabu-expired).
          * Keep the best process found for this period.
          * Backward refinement: try LRC-history processes on recent prior periods.

    Args:
        sol:          starting solution
        inst:         problem instance
        lrc_history:  (T, J) count of how often each process was in the LRC at each t
        rng:          random number generator
        max_iter:     number of full sweeps
        t_start:      reference wall-clock time (for time_found bookkeeping)
        iteration:    current outer GRASP iteration
        time_limit:   stop early if wall time exceeds this
    """
    best = sol.copy()
    sched = sol.scheduling.copy()
    tabu = np.zeros((inst.T, inst.J), dtype=np.int32)  # tabu[t,j] = iteration when added

    current_iter = 0
    while current_iter < max_iter:
        if time.perf_counter() - t_start > time_limit:
            break
        current_iter += 1
        improved = False

        for t in range(inst.T):
            j_out = int(sched[t])
            tabu[t, j_out] = current_iter   # mark as tabu

            # ── Candidate selection ───────────────────────────────────────
            lrc_candidates = np.where(lrc_history[t] > 0)[0]
            if len(lrc_candidates) == 0:
                lrc_candidates = np.arange(inst.J)

            if rng.random() < 0.80 and len(lrc_candidates) > 0:
                j_try = int(rng.choice(lrc_candidates))
            else:
                j_try = int(rng.integers(0, inst.J))

            # Skip if tabu and not aspiration (aspiration: improves best)
            attempts = 0
            while (tabu[t, j_try] > 0 and
                   current_iter - tabu[t, j_try] <= TABU_TENURE and
                   attempts < 10):
                j_try = int(rng.choice(lrc_candidates) if rng.random() < 0.8
                            else rng.integers(0, inst.J))
                attempts += 1

            # ── Try move ─────────────────────────────────────────────────
            sched[t] = j_try
            Z_new, stock_new = evaluate(sched, inst.A, inst.demand, inst.T, inst.I)

            if Z_new < best.Z:
                best = Solution(scheduling=sched.copy(), Z=Z_new, stock=stock_new,
                                time_found=time.perf_counter() - t_start,
                                iteration=iteration)
                improved = True
            elif Z_new >= best.Z:
                # Keep the process that gives the best result for period t
                # (best-improving among tried candidates)
                pass   # accept for diversification

            # ── Backward refinement on last few periods ───────────────────
            t_min = max(0, t - 3)
            for tb in range(t - 1, t_min - 1, -1):
                j_back_out = int(sched[tb])
                best_z_back = Z_new
                best_j_back = j_back_out
                back_candidates = np.where(lrc_history[tb] > 0)[0]
                for j_back in back_candidates:
                    if (tabu[tb, j_back] > 0 and
                            current_iter - tabu[tb, j_back] <= TABU_TENURE):
                        continue
                    sched[tb] = j_back
                    Z_back, st_back = evaluate(sched, inst.A, inst.demand,
                                               inst.T, inst.I)
                    if Z_back < best_z_back:
                        best_z_back = Z_back
                        best_j_back = j_back
                    sched[tb] = j_back_out   # revert

                if best_j_back != j_back_out:
                    sched[tb] = best_j_back
                    Z_new, stock_new = evaluate(sched, inst.A, inst.demand,
                                                inst.T, inst.I)
                    if Z_new < best.Z:
                        best = Solution(scheduling=sched.copy(), Z=Z_new,
                                        stock=stock_new,
                                        time_found=time.perf_counter() - t_start,
                                        iteration=iteration)
                        improved = True
                else:
                    break   # no improvement found backward, stop

        if not improved:
            break  # converged

    return best


# ══════════════════════════════════════════════════════════════════════════════
# 6. PATH RELINKING
# ══════════════════════════════════════════════════════════════════════════════

def path_relinking(src: Solution, tgt: Solution,
                   inst: Instance,
                   t_start: float = 0.0,
                   iteration: int = 0) -> Solution:
    """Explore the path from src towards tgt, return the best solution found.

    At each step, the period whose change produces the greatest improvement
    (or smallest deterioration) is selected (best-admissible strategy).
    Both forward (src→tgt) and backward (tgt→src) paths are explored.
    """
    def _one_direction(s: Solution, target: Solution) -> Solution:
        """Walk from s toward target, return best solution on path."""
        path_best = s.copy()
        sched = s.scheduling.copy()
        diff_periods = np.where(sched != target.scheduling)[0]
        remaining = set(diff_periods.tolist())

        while remaining:
            best_step_Z = float('inf')
            best_step_t = -1
            best_step_j = -1

            for t in remaining:
                j_target = int(target.scheduling[t])
                old_j = int(sched[t])
                sched[t] = j_target
                Z_step, _ = evaluate(sched, inst.A, inst.demand, inst.T, inst.I)
                if Z_step < best_step_Z:
                    best_step_Z = Z_step
                    best_step_t = t
                    best_step_j = j_target
                sched[t] = old_j  # revert

            # Accept best step
            sched[best_step_t] = best_step_j
            remaining.discard(best_step_t)
            Z_path, st_path = evaluate(sched, inst.A, inst.demand, inst.T, inst.I)
            if Z_path < path_best.Z:
                path_best = Solution(scheduling=sched.copy(), Z=Z_path,
                                     stock=st_path,
                                     time_found=time.perf_counter() - t_start,
                                     iteration=iteration)

        return path_best

    fwd = _one_direction(src, tgt)
    bwd = _one_direction(tgt, src)
    return fwd if fwd.Z <= bwd.Z else bwd


# ══════════════════════════════════════════════════════════════════════════════
# 7. ELITE SET
# ══════════════════════════════════════════════════════════════════════════════

class EliteSet:
    """Maintains a pool of high-quality diverse solutions for Path Relinking."""

    def __init__(self, max_size: int = ELITE_SIZE,
                 min_distance: int = MIN_ELITE_DIST):
        self.solutions: List[Solution] = []
        self.max_size   = max_size
        self.min_distance = min_distance

    def __len__(self) -> int:
        return len(self.solutions)

    def try_add(self, sol: Solution) -> bool:
        """Try to add sol to the elite set. Returns True if accepted."""
        # Check diversity: must differ from all current members by min_distance
        for idx, e in enumerate(self.solutions):
            if sol.hamming(e) < self.min_distance:
                # If the new solution is better than the similar one, replace it
                if sol.Z < e.Z:
                    self.solutions[idx] = sol.copy()
                    return True
                return False

        if len(self.solutions) < self.max_size:
            self.solutions.append(sol.copy())
            return True

        # Replace worst if new solution is better
        worst_idx = max(range(len(self.solutions)),
                        key=lambda k: self.solutions[k].Z)
        if sol.Z < self.solutions[worst_idx].Z:
            self.solutions[worst_idx] = sol.copy()
            return True
        return False

    def random_partner(self, rng: np.random.Generator,
                       exclude: Solution) -> Optional[Solution]:
        """Return a random elite solution different from 'exclude'."""
        candidates = [e for e in self.solutions
                      if e.hamming(exclude) >= self.min_distance]
        if not candidates:
            candidates = self.solutions
        if not candidates:
            return None
        return rng.choice(candidates)  # type: ignore


# ══════════════════════════════════════════════════════════════════════════════
# 8. MAIN GRASP LOOP (single run)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class GRASPResult:
    """Complete result of one GRASP run."""
    instance:      str
    dataset:       str
    run_id:        int
    seed:          int
    # Best solution metrics
    objective:     float
    shortage:      float
    excess:        float
    # Optimality gap vs MIP lower bound (filled in by caller if available)
    gap_vs_mip:    Optional[float]
    # Timing
    time_to_best:  float    # seconds
    total_time:    float    # seconds
    iterations:    int      # total constructions
    # Trajectory of improvements
    improvements:  List[Dict]   # [{iter, time, Z}]
    # Final scheduling
    scheduling:    List[int]    # scheduling[t] = process index (1-indexed for readability)


def run_grasp(inst: Instance,
              time_limit_s: float = 1800.0,
              run_id: int = 1,
              seed: Optional[int] = None,
              mip_bound: Optional[float] = None) -> GRASPResult:
    """Execute one full GRASP+TS+PR run on 'inst'.

    Args:
        inst:          loaded PSP instance
        time_limit_s:  wall-clock time limit in seconds (default 30 min)
        run_id:        identifier for this run (for logging/results)
        seed:          random seed for reproducibility
        mip_bound:     MIP lower bound (best_bound from CPLEX 22) for gap computation

    Returns:
        GRASPResult with full statistics.
    """
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    rng = np.random.default_rng(seed)

    t_start = time.perf_counter()

    # ── Initialise ────────────────────────────────────────────────────────
    elite = EliteSet(max_size=ELITE_SIZE, min_distance=MIN_ELITE_DIST)
    lrc_history = np.zeros((inst.T, inst.J), dtype=np.int32)  # LRC participation count

    best_overall: Optional[Solution] = None
    improvements: List[Dict] = []
    iteration = 0
    pr_counter = 0

    # ── Main loop ─────────────────────────────────────────────────────────
    while True:
        elapsed = time.perf_counter() - t_start
        if elapsed >= time_limit_s:
            break
        iteration += 1

        # Randomise look-ahead parameters each iteration (reactive randomisation)
        max_troll = int(rng.integers(MAX_TROLL_LO, MAX_TROLL_HI + 1))
        v         = int(rng.integers(0, V_MAX + 1))

        # ── Construction ─────────────────────────────────────────────────
        sol = construct(inst, rng, max_troll, v, t_start=t_start, iteration=iteration)

        # Update LRC history (track which processes were in the LRC)
        # Rebuild LRC history from this construction (approximate: top-LRC_SIZE per period)
        stock_cur = np.zeros(inst.I)
        for t in range(inst.T):
            fitness_t = _greedy_fitness(inst.A, inst.demand, t, inst.T,
                                        max_troll, v, stock_cur)
            lrc_t = np.argpartition(-fitness_t, min(LRC_SIZE, inst.J) - 1)[:LRC_SIZE]
            lrc_history[t, lrc_t] += 1
            stock_cur = stock_cur + inst.A[sol.scheduling[t], :] - inst.demand[:, t]

        # ── Tabu Search ───────────────────────────────────────────────────
        remaining_time = time_limit_s - (time.perf_counter() - t_start)
        sol = tabu_search(sol, inst, lrc_history, rng,
                          max_iter=TABU_ITERS,
                          t_start=t_start,
                          iteration=iteration,
                          time_limit=t_start + time_limit_s)

        # ── Update best ───────────────────────────────────────────────────
        if best_overall is None or sol.Z < best_overall.Z:
            best_overall = sol.copy()
            improvements.append({
                "iteration": iteration,
                "time_s":    round(sol.time_found, 3),
                "Z":         round(sol.Z, 6),
            })
            pr_counter += 1
            logger.debug(f"  [{inst.name} run {run_id}] iter {iteration:4d} "
                         f"Z={sol.Z:.3f}  t={sol.time_found:.1f}s")

        # ── Update elite set ──────────────────────────────────────────────
        elite.try_add(sol)

        # ── Path Relinking ────────────────────────────────────────────────
        if pr_counter >= PR_FREQ and len(elite) >= 2:
            pr_counter = 0
            partner = elite.random_partner(rng, sol)
            if partner is not None:
                if time.perf_counter() - t_start < time_limit_s:
                    pr_sol = path_relinking(sol, partner, inst,
                                            t_start=t_start,
                                            iteration=iteration)
                    elite.try_add(pr_sol)
                    if pr_sol.Z < best_overall.Z:
                        best_overall = pr_sol.copy()
                        improvements.append({
                            "iteration": iteration,
                            "time_s":    round(pr_sol.time_found, 3),
                            "Z":         round(pr_sol.Z, 6),
                            "from_pr":   True,
                        })
                        logger.debug(f"  [{inst.name} run {run_id}] PR iter {iteration:4d} "
                                     f"Z={pr_sol.Z:.3f}  t={pr_sol.time_found:.1f}s")

    total_time = time.perf_counter() - t_start

    if best_overall is None:
        # Should not happen, but guard
        best_overall = construct(inst, rng, MAX_TROLL_LO, 0, t_start=0.0)

    # ── Compute shortage / excess decomposition ───────────────────────────
    st = best_overall.stock[:, 1:]      # (I, T)
    shortage = float(-np.sum(np.minimum(st, 0.0)))
    excess   = float( np.sum(np.maximum(st, 0.0)))

    # ── GAP vs MIP bound  (standard OR formula: (Z_h - Z_MIP) / Z_MIP × 100) ─
    gap_vs_mip = None
    if mip_bound is not None:
        if mip_bound > 0:
            gap_vs_mip = round((best_overall.Z - mip_bound) / mip_bound * 100, 4)
        elif best_overall.Z == 0:
            gap_vs_mip = 0.0   # both heuristic and MIP are 0 → perfect
        else:
            gap_vs_mip = None  # MIP bound = 0 but heuristic > 0 (shouldn't happen)

    return GRASPResult(
        instance=inst.name,
        dataset=inst.dataset,
        run_id=run_id,
        seed=seed,
        objective=round(best_overall.Z, 6),
        shortage=round(shortage, 3),
        excess=round(excess, 3),
        gap_vs_mip=gap_vs_mip,
        time_to_best=round(best_overall.time_found, 3),
        total_time=round(total_time, 3),
        iterations=iteration,
        improvements=improvements,
          scheduling=[int(j) + 1 for j in best_overall.scheduling],  # 1-indexed
    )
