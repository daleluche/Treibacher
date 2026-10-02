# Sprint 3 Task 3.1 Post-Mortem

This note documents the two required pre-fix autopsies. No corrective changes are applied here.

## IncT5x_10 short-budget rf+fo collapse

Command reproduced:

```powershell
python experiments\matheuristics\rf_fo_psp.py --instance experiments\GAMSPy\5X\IncT5x_10.py --budget 300 --seed 1 --method rf+fo --omega 20 --step-fo 10 --tl-fo 30 --output-suffix _autopsy_b300
```

New evidence file:

- `experiments/matheuristics/results_pilot/IncT5x_10_rf_fo_seed1_autopsy_b300.json`

Observed metrics:

| source | Z_rf | Z_final | rf_windows | rf_wall_time_s | wall_time_s | fo_accepts | idle_periods |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Sprint 2 short-budget JSON | 15353974.912 | 999420.861 | 18 | 260.852 | 303.082 | 1 | 10 |
| Sprint 3 autopsy rerun | 15374552.554 | 1064433.166 | 18 | 269.461 | 302.255 | 1 | 10 |

Diagnosis:

- The greedy fallback was not triggered. All 18 RF windows have `status = "solved"` in both the Sprint 2 JSON and the autopsy rerun.
- The RF covered the full 95-period horizon. The last RF validation check passed with `Z_model = Z_evaluate = 15374552.554` in the autopsy rerun.
- The final schedule is structurally complete: schedule length is 95 and the vector representation permits at most one process per period. It contains 10 idle periods, which are allowed by the model and are not missing periods.
- The large final value is therefore not caused by a greedy fallback bug, an incomplete horizon, or an evaluator mismatch.
- The root cause is budget starvation of the improvement phase after a poor RF construction. RF consumed about 269 seconds of a 300-second run; only one F&O window was accepted near the end, improving the RF incumbent from about 15.37 million to about 1.06 million, still far above the ILS v2 300s reference.
- The GAMSPy stdout showed repeated `ResourceInterrupt` warnings. In this run they correspond to time-limited window solves that still produced incumbent records; they did not trigger the fallback path.
- The first F&O solve used and accepted the RF MIP start. Evidence from the JSON log lines:
  - `Processing 1 MIP starts.`
  - `MIP start 'm1' defined solution with objective 1.5375e+07.`
  - `MIP start 'm1' defined initial solution with objective 1.5375e+07.`

Conclusion: the short-budget collapse is a policy failure, not a fallback implementation failure. With 18 RF windows, the 300s budget leaves too little time for F&O. This supports the Sprint 3.2 adaptive construction rule that bypasses windowed RF when `budget_rf / n_windows < 10s`.

## IncT10x_5 rf+mip anomaly

Compared files:

- Cold MIP: `experiments/matheuristics/results_scale_8x10x/IncT10x_5_mip_seed1_b3600.json`
- RF+MIP: `experiments/matheuristics/results_scale_8x10x/IncT10x_5_rf_mip_seed1_b3600.json`
- RF+FO reference: `experiments/matheuristics/results_scale_8x10x/IncT10x_5_rf_fo_seed1_b3600.json`

Observed metrics:

| method | Z_rf | Z_final | rf_windows | rf_wall_time_s | wall_time_s | solver_time_after_rf_s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| mip | 68914.120 | 68914.120 | 0 | 0.000 | 3633.881 | 3633.881 |
| rf+mip | 155724693.239 | 165170.737 | 37 | 2056.657 | 3644.624 | 1587.967 |
| rf+fo | 155724693.239 | 154102.825 | 37 | 1983.732 | 3617.750 | 1634.018 |

Hypotheses checked:

1. RF bad incumbent anchored the search.
   - Supported as a quality diagnosis, but not as a hard correctness issue. RF delivered `Z_rf = 155724693.239`, which is over three orders of magnitude worse than the cold MIP incumbent. The subsequent monolithic MIP improved that start to `165170.737`, so the solver was not stuck at the RF value, but the start was not helpful.

2. Warm MIP received less time than cold MIP.
   - Supported. RF consumed `2056.657s`, leaving about `1588s` for the monolithic solve. The cold MIP received the full `3634s`. This is the most direct accounting explanation for `rf+mip` losing to cold MIP on this instance.

3. Tree variability.
   - Plausible but not isolated by the available single-seed production run. The data show a materially different solve setup: cold start with full time versus accepted warm start after a very poor RF and about 44% of the wall-clock time. A controlled rerun with equal monolithic time would be needed to isolate tree effects.

Warm-start evidence:

- `Processing 1 MIP starts.`
- `MIP start 'm1' defined solution with objective 1.5572e+08.`
- `MIP start 'm1' defined initial solution with objective 1.5572e+08.`

Conclusion: the anomaly is primarily explained by an extremely poor RF incumbent plus RF consuming more than half of the budget. The MIP start was accepted, and the monolithic phase improved the incumbent substantially, but it did not have enough remaining time to match the cold MIP run.
