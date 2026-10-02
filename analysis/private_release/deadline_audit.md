# Deadline Audit

R3 base SHA: ce7fa16875fb76659ff6edce60b79a5740ded156

## GRASP/ILS

`experiments/GRASP/grasp_ils_psp.py` was updated prospectively to keep
cross-run path relinking outside the equal-budget objective fields and to
record deadline overrun metadata. The historical JSON outputs were not
modified.

Unit tests enforce:

- `total_time <= budget + 0.5 s` on a short synthetic run.
- no improvement record has `time_s > budget`.
- post-hoc cross-run path relinking does not overwrite `Z_best` or
  `Z_best_equal_budget`.

## RF/FO

`experiments/matheuristics/rf_fo_psp.py` already uses `time.perf_counter()`
and `time_left(start_time, params.budget)` throughout the construction,
fix-and-optimize, RF+MIP, and cold-MIP flows. The RF loop also guards the
construction budget before each window solve and falls back to greedy
completion when the total remaining budget drops below 10 seconds. No R4 code
change was required for this module.
