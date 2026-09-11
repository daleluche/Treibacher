# Technical Fidelity Review Notes

Scope: Sprint 4.5 review of Sections 4 and 5 against `experiments/matheuristics/rf_fo_psp.py`,
`experiments/GRASP/grasp_ils_psp.py`, and `docs/metaheuristicas.docx`. These notes intentionally do
not edit the manuscript prose.

## Section 4: Matheuristics

Overall status: mostly faithful to the current implementation.

Confirmed matches:

- The single restricted GAMSPy model uses binary `X[j,t]` and positive `XR[j,t]`, and every assignment
  occurrence in the demand and per-period constraints is modeled as `X + XR`.
- Period regimes are controlled by bounds and batch record updates rather than rebuilding the container.
- RF windows are anchored at the end through `make_windows`, and the function asserts full horizon
  coverage.
- RF uses `optcr=0.001`; FO uses `optcr=0.01`; RF+MIP and cold MIP use `optcr=0.0`.
- RF construction budget is `min(0.25 * B, n_windows * tl_rf)`.
- RF has a wall-clock construction guard, a global-budget guard, and a greedy tail fallback.
- Every run computes a greedy construction and starts improvement from the better of RF and greedy
  (`construction_used` may be `rf`, `greedy`, or `greedy_floor`).
- FO frees the active window, fixes all other periods, sets a MIP start, accepts only strict global
  objective improvements, and records the best solution found in any phase.
- When `omega >= T`, FO performs one full-horizon solve with the remaining budget and records
  `early_stop_reason = "fo_window_covers_horizon"`.
- Window logs include identity columns, solve timing, incumbent profiles, shortage/excess profiles,
  full-horizon marginal arrays for `EQ_DEM` and `EQ_PROP`, and `xr_frac_nonzero`.

Potential manuscript divergences:

- Section 4 says that if an RF window yields no integer incumbent, "its limit is doubled once." The
  current code no longer doubles the limit beyond the current dynamic allowance; the retry time is
  bounded by `min(tl, remaining RF budget, remaining global budget)`. The prose should be softened to
  "retried within the remaining RF/global budget" or similar.
- Section 4 says accepted FO MIP starts were verified in the solver log. The code checks and records
  MIP-start evidence lines, but the Boolean `warm_start_log_has_mipstart` is based on whether MIP-start
  text appears in the log, not necessarily on a strong "accepted initial solution" line for every run.
  This is adequate as instrumentation but the prose should avoid overclaiming universal acceptance.
- Section 4's RF+MIP subsection says RF produces a solution "on the order of seconds to two minutes."
  This is true for small and medium instances but not for the corrected 8X/10X runs, where RF wall time
  can be roughly 14--16 minutes under the wall-clock guard. Consider qualifying this by scale.
- The FO early-stop behavior when `omega >= T` is implemented but not described in Section 4 prose or
  Algorithm 1. It is operationally important for `T <= omega` instances.

## Section 5: Hybrid Metaheuristic Baseline

Overall status: mostly faithful, with one wording issue about cross-run information sharing.

Confirmed implementation values:

- `PESO_ESTOQUE = 0.001`, matching the MIP excess penalty.
- Reactive GRASP uses `ALPHA_VALUES = {0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30}` and exponential
  moving-average updates with `REACTIVE_DECAY = 0.15`.
- Construction uses look-ahead in `[3, 7]` and distance exponent `v` in `[0, 5]`.
- Tabu tenure is randomized in `[5, 12]`, with aspiration if the tabu move improves the best solution.
- Full tabu search uses `TABU_SWEEPS = 150`; for long horizons, windowed tabu search activates at
  `T > 40` with `WINDOW_SIZE = 22`, `WINDOW_STEP = 14`, and `WINDOW_SWEEPS = 40`.
- The local search is VND-like: tabu search followed by Or-opt block reinsertion neighborhoods with
  block sizes `1, 2, 3` and `OR_OPT_TRIES = 80`.
- Perturbation is adaptive multi-bridge: 3 cuts for `T <= 40`, 4 cuts for `T <= 70`, and 5 cuts for
  larger horizons.
- Intra-run elite pool capacity is `ELITE_SIZE = 10`, with `MIN_ELITE_DIST = 2`.
- Intra-run path relinking is attempted every `PR_FREQ = 4` improvements when the elite pool has at
  least two members.
- The driver defaults to `n_runs = 10` and uses up to `min(n_runs, cpu_count)` workers when `--workers`
  is left at zero.
- After all worker runs finish, a post-hoc cross-run path relinking step considers the top
  `CROSS_PR_TOP = 5` solutions and has a `CROSS_PR_TIME = 300` second cap.

Potential manuscript divergence:

- Section 5 says the ten workers "share an elite pool through cross-run path relinking." In the code,
  each worker has its own intra-run elite pool; cross-run path relinking happens after all runs complete
  using saved top solutions. The manuscript should say "post-hoc cross-run path relinking among the best
  worker outputs" rather than implying live shared-memory elite-pool exchange.

Notes on `docs/metaheuristicas.docx`:

- The document matches the key constants above for `TABU_TENURE = [5,12]`, `ELITE_SIZE = 10`,
  `MIN_DIST = 2`, and `PR_FREQ = 4`.
- Some pseudocode in the DOCX describes a fixed top-`LRC_SIZE = 7` candidate list during construction,
  whereas the current `grasp_ils_psp.py` construction uses reactive alpha-threshold RCL selection.
  The manuscript follows the code on this point.
