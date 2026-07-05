# Pilot Matheuristics Report

Seed: `1`
Verdict: **NO-GO**

Decision rule used here: GO requires all 8 RF+FO runs to complete and at least one RF+FO incumbent to improve the CPLEX@3h primal. This is a pilot-screening rule, not a final paper conclusion.

## Results

| Dataset | Instance | RF | RF+FO | CPLEX 1h | CPLEX 3h | ILS v2 best | RF+FO gap vs CPLEX 3h (%) | FO accepts | Warm start | Wall RF+FO (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Real | Ale_1 | 91993.707 | 86850.339 | 86264.683 | 86264.683 | 86324.908 | 0.679 | 5 | True | 3600.020 |
| 2X | IncT2X_1 | 40745.830 | 40661.805 | 40179.544 | 40179.544 | 42278.155 | 1.200 | 5 | True | 3600.023 |
| 3X | IncT3x_3 | 46177.467 | 46175.567 | 46154.492 | 46154.492 | 50505.825 | 0.046 | 1 | True | 3600.035 |
| 3X | IncT3x_7 | 17001.681 | 16759.682 | 16586.707 | 16591.924 | 20633.358 | 1.011 | 7 | True | 3600.024 |
| 4X | IncT4x_3 | 50256.782 | 50144.492 | 49654.614 | 49468.889 | 58956.125 | 1.366 | 6 | True | 3600.029 |
| 4X | IncT4x_7 | 19952.367 | 19873.039 | 19975.839 | 19759.389 | 26566.027 | 0.575 | 4 | True | 3600.030 |
| 5X | IncT5x_3 | 54879.119 | 56880.968 | 54387.750 | 53570.461 | 64510.463 | 6.180 | 10 | True | 3600.025 |
| 5X | IncT5x_10 | 21991.690 | 18115.429 | 17970.346 | 16964.090 | 25271.660 | 6.787 | 44 | True | 3601.223 |

## Warm Start Evidence

Source instance: `Ale_1`

- `>>  mipstart 1`
- `Processing 1 MIP starts.`
- `MIP start 'm1' defined solution with objective 91993.7070.`
- `1 of 1 MIP starts provided solutions.`
- `MIP start 'm1' defined initial solution with objective 91993.7070.`

## Notes

- `RF` and `RF+FO` values are `Z_final` from `experiments/matheuristics/results_pilot`.
- Reference values are read from `analysis/output/comparison_table.csv`.
