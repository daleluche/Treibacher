# Sprint 3 Final Analysis Report

## Technical summary

The final production grid is complete: Grade B contributes 180 short-budget runs, Grade A contributes 50 long-budget rf+fo runs on Real--5X, and Grade C contributes 24 seed-variability runs. The global BKS scanner now includes all CPLEX, GRASP, ILS, tuning, pilot, short-budget, scale, v2, and production matheuristic JSONs.

The IncT8x_4 BKS audit passes the registered check: BKS = 158113.714, source = `MAT_rf_mip_3600s | 3600s | experiments\matheuristics\results_scale_8x10x\IncT8x_4_rf_mip_seed1_b3600.json`.

## Registered Sprint 2 hypotheses

| hypothesis | registered_result | evidence |
| --- | --- | --- |
| H1 operational regime | False | 300s: 2/6; 600s: 3/6 |
| H2 scale | True | 10X decomposed wins: 3/5 |
| H3 dominance over ILS v2 | False | at least one short-budget cell failed |
| H4 accounting sanity | True | Z_final <= internal Z_rf for all rf+fo rows |

These are reported as registered historical verdicts. The corrected 8X/10X v2 runs and the production grades are treated as post-hoc evidence below.

## Global BKS and comparison table

`comparison_table.csv` now has 60 rows and includes `bks_source`. Dataset coverage is: Real=10, 2X=10, 3X=10, 4X=10, 5X=10, 8X=5, 10X=5.

BKS candidates are scanned from all registered sources, but any candidate below an available CPLEX dual bound for the same instance is excluded as a consistency safeguard. This affects legacy GRASP_v1 rows on a few Real instances and prevents infeasible/incomparable legacy objectives from overriding proven optima.

## Production frontier

The method frontier is summarized by majority winner per dataset-budget cell. Counts are exact counts of available instances in the cell.

| dataset | budget_s | winner | n | mip | rf+mip | rf+fo |
| --- | --- | --- | --- | --- | --- | --- |
| Real | 600 | mip | 10 | 10 | 0 | 0 |
| Real | 3600 | mip | 10 | 10 | 0 | 0 |
| Real | 10800 | mip | 10 | 10 | 0 | 0 |
| 2X | 600 | mip | 10 | 8 | 2 | 0 |
| 2X | 3600 | mip | 10 | 10 | 0 | 0 |
| 2X | 10800 | mip | 10 | 10 | 0 | 0 |
| 3X | 600 | mip | 10 | 5 | 4 | 1 |
| 3X | 3600 | mip | 10 | 9 | 0 | 1 |
| 3X | 10800 | mip | 10 | 10 | 0 | 0 |
| 4X | 600 | mip | 10 | 5 | 3 | 2 |
| 4X | 3600 | mip | 10 | 9 | 0 | 1 |
| 4X | 10800 | mip | 10 | 10 | 0 | 0 |
| 5X | 600 | mip | 10 | 6 | 2 | 2 |
| 5X | 3600 | mip | 10 | 6 | 0 | 4 |
| 5X | 10800 | mip | 10 | 10 | 0 | 0 |
| 8X | 600 | rf+mip | 5 | 1 | 3 | 1 |
| 8X | 3600 | rf+mip | 5 | 0 | 4 | 1 |
| 8X | 10800 | no data | 0 | 0 | 0 | 0 |
| 10X | 600 | rf+fo | 5 | 1 | 0 | 4 |
| 10X | 3600 | rf+fo | 5 | 1 | 1 | 3 |
| 10X | 10800 | no data | 0 | 0 | 0 | 0 |

Figures: `analysis/figures/performance_profile_600s.*`, `performance_profile_3600s.*`, `frontier_heatmap.*`, and convergence curves for IncT3x_7, IncT5x_10, and IncT10x_2.

## 8X/10X v2 construction diagnostics

The v2 diagnostics separate the construction handoff from the improvement phase. `improvement_time_left_s` is the nominal remaining budget after RF construction wall time.

| dataset | instance | method | construction_used | construction_Z | rf_wall_time_s | improvement_time_left_s | Z_final |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10X | IncT10x_2 | rf+fo | greedy_floor | 64949157.152 | 843.387 | 2756.613 | 142834.183 |
| 10X | IncT10x_2 | rf+mip | greedy_floor | 64949157.152 | 843.396 | 2756.604 | 154797.480 |
| 10X | IncT10x_3 | rf+fo | greedy_floor | 50914291.231 | 797.530 | 2802.470 | 88476.214 |
| 10X | IncT10x_3 | rf+mip | greedy_floor | 50914291.231 | 803.583 | 2796.417 | 87275.452 |
| 10X | IncT10x_4 | rf+fo | greedy_floor | 53481810.021 | 796.912 | 2803.088 | 172982.609 |
| 10X | IncT10x_4 | rf+mip | greedy_floor | 62714040.950 | 843.858 | 2756.142 | 376198.080 |
| 10X | IncT10x_5 | rf+fo | greedy_floor | 52350388.486 | 798.174 | 2801.826 | 83018.375 |
| 10X | IncT10x_5 | rf+mip | greedy_floor | 43510609.027 | 799.246 | 2800.754 | 87036.326 |
| 10X | IncT10x_6 | rf+fo | greedy_floor | 53309346.263 | 797.983 | 2802.017 | 109047.046 |
| 10X | IncT10x_6 | rf+mip | greedy_floor | 63132592.910 | 844.547 | 2755.453 | 187103.043 |
| 8X | IncT8x_2 | rf+fo | greedy_floor | 59130387.070 | 841.411 | 2758.589 | 135291.725 |
| 8X | IncT8x_2 | rf+mip | greedy_floor | 58659668.175 | 855.586 | 2744.414 | 131246.445 |
| 8X | IncT8x_3 | rf+fo | greedy_floor | 63327814.323 | 839.401 | 2760.599 | 77987.822 |
| 8X | IncT8x_3 | rf+mip | greedy_floor | 63327814.323 | 839.753 | 2760.247 | 71896.386 |
| 8X | IncT8x_4 | rf+fo | greedy_floor | 60599633.954 | 840.140 | 2759.860 | 160989.844 |
| 8X | IncT8x_4 | rf+mip | greedy_floor | 60599633.954 | 836.748 | 2763.252 | 160602.997 |
| 8X | IncT8x_5 | rf+fo | greedy_floor | 59149435.356 | 836.317 | 2763.683 | 60653.804 |
| 8X | IncT8x_5 | rf+mip | greedy_floor | 59725672.856 | 840.251 | 2759.749 | 58152.349 |
| 8X | IncT8x_6 | rf+fo | greedy_floor | 53156195.929 | 861.063 | 2738.937 | 97667.582 |
| 8X | IncT8x_6 | rf+mip | greedy_floor | 57467501.049 | 862.821 | 2737.179 | 99419.134 |

## Statistical tests

Wilcoxon tests are paired by instance. Rank-biserial effect size is computed on paired objective differences (left minus right); negative values favor the first method because lower objective is better.

| comparison | n | p_value | rank_biserial | median_rel_delta_pct |
| --- | --- | --- | --- | --- |
| 600s rf+fo vs mip | 60.0000 | 0.2724 | 0.1701 | 0.1177 |
| 600s rf+mip vs mip | 60.0000 | 0.3202 | 0.1761 | 0.0000 |
| 600s rf+fo vs truncated ILS v2 | 6.0000 | 0.0312 | -1.0000 | -20.4246 |
| 3600s 8X/10X rf+fo vs mip | 10.0000 | 0.0098 | 0.8909 | 14.7536 |
| 3600s 8X/10X rf+mip vs mip | 10.0000 | 0.5566 | -0.2364 | -1.2827 |

## Seed variability

| dataset | instance | Z_mean | Z_std | Z_min | Z_max | Z_range |
| --- | --- | --- | --- | --- | --- | --- |
| 10X | IncT10x_5 | 80393.433 | 3035.847 | 78246.765 | 82540.101 | 4293.336 |
| 3X | IncT3x_3 | 46177.467 | 0.000 | 46177.467 | 46177.467 | 0.000 |
| 3X | IncT3x_7 | 16517.632 | 0.000 | 16517.632 | 16517.632 | 0.000 |
| 4X | IncT4x_3 | 50216.932 | 0.000 | 50216.932 | 50216.932 | 0.000 |
| 4X | IncT4x_7 | 19519.564 | 0.000 | 19519.564 | 19519.564 | 0.000 |
| 5X | IncT5x_10 | 16432.742 | 448.208 | 16115.811 | 16749.673 | 633.862 |
| 5X | IncT5x_3 | 56950.294 | 0.000 | 56950.294 | 56950.294 | 0.000 |
| 8X | IncT8x_2 | 135505.430 | 330.827 | 135271.500 | 135739.360 | 467.860 |
| 8X | IncT8x_3 | 77834.849 | 106.352 | 77759.647 | 77910.051 | 150.404 |
| 8X | IncT8x_4 | 160989.319 | 731.926 | 160471.770 | 161506.869 | 1035.099 |
| 8X | IncT8x_5 | 60119.988 | 195.138 | 59982.004 | 60257.971 | 275.967 |
| 8X | IncT8x_6 | 96744.939 | 237.906 | 96576.714 | 96913.164 | 336.450 |

## Scope and limitations

The 10800s frontier cells use the available CPLEX 3h baseline where present; 8X/10X have no 10800s cold MIP runs in this sprint and are marked as no data in that budget column. Production Grade A supplies rf+fo at 3600s for Real--5X, while 8X/10X 3600s evidence comes from the scale and v2 folders rather than Grade A.

## Reproducibility outputs

- `analysis/output/comparison_table.csv`
- `analysis/output/sprint3_bks_audit.csv`
- `analysis/output/sprint3_frontier_counts.csv`
- `analysis/output/sprint3_scale_v2_construction.csv`
- `analysis/output/sprint3_statistical_tests.csv`
- `analysis/output/sprint3_seed_variability.csv`
- `analysis/figures/*.png` and `analysis/figures/*.pdf`
