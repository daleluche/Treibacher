# F&O tuning summary

Grid: omega in {12, 20, 28}, tl_window_fo in {30, 60}, step_fo = omega / 2.
Relative gaps use the BKS column from analysis/output/comparison_table.csv.

## Winner by instance

| instance | config | Z_final | fo_accepts | complete_sweeps | gap_to_BKS_pct |
|---|---:|---:|---:|---:|---:|
| IncT5x_10 | omega20_tlfo30 | 16188.998000 | 43 | 37 | -4.5690 |
| IncT5x_3 | omega28_tlfo30 | 54859.144000 | 1 | 45 | 2.4056 |

## Mean relative gap by config

| config | mean_gap_to_BKS_pct |
|---|---:|
| omega20_tlfo30 | -1.0631 |
| omega20_tlfo60 | -0.0325 |
| omega28_tlfo60 | 0.8429 |
| omega28_tlfo30 | 0.8953 |
| omega12_tlfo30 | 7.1540 |
| omega12_tlfo60 | 7.1540 |

## Recommendation

Recommended configuration: omega20_tlfo30 (mean gap to BKS = -1.0631%).
