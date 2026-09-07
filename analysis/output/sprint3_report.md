# Sprint 3 Final Analysis Report

## Technical summary

The final production grid is complete: Grade B contributes 180 short-budget runs, Grade A contributes 50 long-budget rf+fo runs on S--5X plus the reconstructed S_1 supplement, and Grade C contributes 24 seed-variability runs. The global BKS scanner now includes CPLEX, ILS, tuning, pilot, short-budget, scale, v2, MIP@10800s scale, reconstructed S_1, and production matheuristic JSONs; legacy GRASP_v1 is retained only in the raw master data because the BKS safeguard detected evaluator inconsistencies.

The IncT8x_4 BKS audit passes the registered check: BKS = 158113.714, source = `MAT_rf_mip_3600s | 3600s | experiments\matheuristics\results_scale_8x10x\IncT8x_4_rf_mip_seed1_b3600.json`.

Using canonical v2 decomposition data for 8X/10X @3600s, the Wilcoxon row `3600s 8X/10X rf+fo vs mip` has median relative delta -4.4997%, p-value 0.1934, and rank-biserial effect -0.4909.

## Registered Sprint 2 hypotheses

| hypothesis | registered_result | evidence |
| --- | --- | --- |
| H1 operational regime | False | 300s: 2/6; 600s: 3/6 |
| H2 scale | True | 10X decomposed wins: 3/5 |
| H3 dominance over ILS v2 | False | at least one short-budget cell failed |
| H4 accounting sanity | True | Z_final <= internal Z_rf for all rf+fo rows |

These are reported as registered historical verdicts. The corrected 8X/10X v2 runs and the production grades are treated as post-hoc evidence below.

## Cell source map

Each frontier/statistical cell is tied to a single declared source. In particular, 8X/10X @3600s uses cold MIP from `results_scale_8x10x/` and matheuristics from `results_scale_8x10x_v2/`, labelled post-hoc. The 8X/10X @10800s cells use cold MIP from `results_scale_8x10x_mip10800/` only; decompositions were not run at 10800s.

| dataset | budget_s | source_cell |
| --- | --- | --- |
| 10X | 600 | production Grade B @600s |
| 10X | 3600 | post-hoc: MIP from results_scale_8x10x; rf+fo/rf+mip from results_scale_8x10x_v2 |
| 10X | 10800 | post-hoc: cold MIP from results_scale_8x10x_mip10800 only; decompositions not run @10800s |
| 2X | 600 | production Grade B @600s |
| 2X | 3600 | registered/production: CPLEX22_1h and Grade A rf+fo |
| 2X | 10800 | registered CPLEX22_3h where available |
| 3X | 600 | production Grade B @600s |
| 3X | 3600 | registered/production: CPLEX22_1h and Grade A rf+fo |
| 3X | 10800 | registered CPLEX22_3h where available |
| 4X | 600 | production Grade B @600s |
| 4X | 3600 | registered/production: CPLEX22_1h and Grade A rf+fo |
| 4X | 10800 | registered CPLEX22_3h where available |
| 5X | 600 | production Grade B @600s |
| 5X | 3600 | registered/production: CPLEX22_1h and Grade A rf+fo |
| 5X | 10800 | registered CPLEX22_3h where available |
| 8X | 600 | production Grade B @600s |
| 8X | 3600 | post-hoc: MIP from results_scale_8x10x; rf+fo/rf+mip from results_scale_8x10x_v2 |
| 8X | 10800 | post-hoc: cold MIP from results_scale_8x10x_mip10800 only; decompositions not run @10800s |
| S | 600 | production Grade B @600s |
| S | 3600 | reconstructed S_1 supplement: mip/rf+fo from results_production/s1; registered/production: CPLEX22_1h and Grade A rf+fo |
| S | 10800 | registered CPLEX22_3h where available |

## Global BKS and comparison table

`comparison_table.csv` now has 61 rows and includes `bks_source`. Dataset coverage is: S=10, 2X=10, 3X=10, 4X=10, 5X=10, 8X=5, 10X=5.

BKS candidates are scanned from registered CPLEX, ILS, and matheuristic sources, but any candidate below an available CPLEX dual bound for the same instance is excluded as a consistency safeguard. Legacy GRASP_v1 remains in `master_runs.csv` only and is intentionally excluded from paper comparison tables because the safeguard exposed evaluator inconsistencies.

## Production frontier

The method frontier is summarized by majority winner per dataset-budget cell. Counts are exact counts of available instances in the cell.

| dataset | budget_s | winner | n | mip | rf+mip | rf+fo | source_cell |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S | 600 | mip | 10 | 10 | 0 | 0 | production Grade B @600s |
| S | 3600 | mip | 10 | 10 | 0 | 0 | reconstructed S_1 supplement: mip/rf+fo from results_production/s1; registered/production: CPLEX22_1h and Grade A rf+fo |
| S | 10800 | mip | 10 | 10 | 0 | 0 | registered CPLEX22_3h where available |
| 2X | 600 | mip | 10 | 8 | 2 | 0 | production Grade B @600s |
| 2X | 3600 | mip | 10 | 10 | 0 | 0 | registered/production: CPLEX22_1h and Grade A rf+fo |
| 2X | 10800 | mip | 10 | 10 | 0 | 0 | registered CPLEX22_3h where available |
| 3X | 600 | mip | 10 | 5 | 4 | 1 | production Grade B @600s |
| 3X | 3600 | mip | 10 | 9 | 0 | 1 | registered/production: CPLEX22_1h and Grade A rf+fo |
| 3X | 10800 | mip | 10 | 10 | 0 | 0 | registered CPLEX22_3h where available |
| 4X | 600 | mip | 10 | 5 | 3 | 2 | production Grade B @600s |
| 4X | 3600 | mip | 10 | 9 | 0 | 1 | registered/production: CPLEX22_1h and Grade A rf+fo |
| 4X | 10800 | mip | 10 | 10 | 0 | 0 | registered CPLEX22_3h where available |
| 5X | 600 | mip | 10 | 6 | 2 | 2 | production Grade B @600s |
| 5X | 3600 | mip | 10 | 6 | 0 | 4 | registered/production: CPLEX22_1h and Grade A rf+fo |
| 5X | 10800 | mip | 10 | 10 | 0 | 0 | registered CPLEX22_3h where available |
| 8X | 600 | rf+mip | 5 | 1 | 3 | 1 | production Grade B @600s |
| 8X | 3600 | rf+mip | 5 | 1 | 3 | 1 | post-hoc: MIP from results_scale_8x10x; rf+fo/rf+mip from results_scale_8x10x_v2 |
| 8X | 10800 | mip | 5 | 5 | 0 | 0 | post-hoc: cold MIP from results_scale_8x10x_mip10800 only; decompositions not run @10800s |
| 10X | 600 | rf+fo | 5 | 1 | 0 | 4 | production Grade B @600s |
| 10X | 3600 | rf+fo | 5 | 1 | 1 | 3 | post-hoc: MIP from results_scale_8x10x; rf+fo/rf+mip from results_scale_8x10x_v2 |
| 10X | 10800 | mip | 5 | 5 | 0 | 0 | post-hoc: cold MIP from results_scale_8x10x_mip10800 only; decompositions not run @10800s |

## Q5 -- cross-budget check

Q5 is adjudicated literally: is cold MIP @10800s strictly better than the best canonical decomposed method @3600s (source `results_scale_8x10x_v2/`) in at least 3 of 5 instances, separately for 8X and 10X?

| dataset | mip10800_wins | n | Q5_true |
| --- | --- | --- | --- |
| 10X | 3 | 5 | true |
| 8X | 4 | 5 | true |

| dataset | instance | mip_10800_Z | best_decomp_3600_Z | best_decomp_3600_method | delta_rel_pct | winner |
| --- | --- | --- | --- | --- | --- | --- |
| 10X | IncT10x_2 | 163595.478 | 142834.183 | rf+fo | 14.535 | decomp@3600 |
| 10X | IncT10x_3 | 80690.614 | 87275.452 | rf+mip | -7.545 | mip@10800 |
| 10X | IncT10x_4 | 168985.520 | 172982.609 | rf+fo | -2.311 | mip@10800 |
| 10X | IncT10x_5 | 66696.973 | 83018.375 | rf+fo | -19.660 | mip@10800 |
| 10X | IncT10x_6 | 111304.255 | 109047.046 | rf+fo | 2.070 | decomp@3600 |
| 8X | IncT8x_2 | 128054.148 | 131246.445 | rf+mip | -2.432 | mip@10800 |
| 8X | IncT8x_3 | 67597.088 | 71896.386 | rf+mip | -5.980 | mip@10800 |
| 8X | IncT8x_4 | 159561.553 | 160602.997 | rf+mip | -0.648 | mip@10800 |
| 8X | IncT8x_5 | 59137.359 | 58152.349 | rf+mip | 1.694 | decomp@3600 |
| 8X | IncT8x_6 | 95679.146 | 97667.582 | rf+fo | -2.036 | mip@10800 |

A negative delta means MIP@10800s is better; a positive delta means the 3600s decomposed run is better despite the shorter budget.

## BKS changes after MIP@10800s

| dataset | instance | BKS_previous | BKS_current | bks_source_previous | bks_source_current |
| --- | --- | --- | --- | --- | --- |
| none | none |  |  | No BKS changes after regeneration. | No BKS changes after regeneration. |

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
| 600s rf+fo vs mip | 60.0000 | 0.2798 | 0.1675 | 0.1177 |
| 600s rf+mip vs mip | 60.0000 | 0.3202 | 0.1761 | 0.0000 |
| 600s rf+fo vs truncated ILS v2 | 6.0000 | 0.0312 | -1.0000 | -20.4246 |
| 3600s 8X/10X rf+fo vs mip | 10.0000 | 0.1934 | -0.4909 | -4.4997 |
| 3600s 8X/10X rf+mip vs mip | 10.0000 | 1.0000 | -0.0182 | -1.7035 |

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

### Seed plumbing audit

The IncT3x_3 FO_random window sequences differ across seeds 2 and 3 (`sequences_differ=true`). Therefore a zero standard deviation for this instance is interpreted as legitimate robustness, not a seed plumbing bug.

| instance | seed | fo_random_windows | first_20_windows | sequences_differ |
| --- | --- | --- | --- | --- |
| IncT3x_3 | 2 | 646 | 1-20; 2-21; 22-41; 42-57; 1-20; 3-22; 23-42; 43-57; 1-20; 3-22; 23-42; 43-57; 1-20; 12-31; 32-51; 52-57; 1-20; 6-25; 26-45; 46-57 | true |
| IncT3x_3 | 3 | 629 | 1-20; 8-27; 28-47; 48-57; 1-20; 19-38; 39-57; 1-20; 18-37; 38-57; 1-20; 5-24; 25-44; 45-57; 1-20; 12-31; 32-51; 52-57; 1-20; 20-39 | true |

## Scope and limitations

The 10800s frontier cells use the available CPLEX 3h baseline where present. For 8X/10X, 10800s cells now contain cold MIP only from `results_scale_8x10x_mip10800/`; decompositions were not executed at 10800s and this asymmetry is disclosed in the frontier figure and Q5 table. Production Grade A supplies rf+fo at 3600s for S--5X, while 8X/10X 3600s decomposition evidence comes only from results_scale_8x10x_v2/ and is explicitly post-hoc.

## Reproducibility outputs

- `analysis/output/comparison_table.csv`
- `analysis/output/sprint3_bks_audit.csv`
- `analysis/output/sprint3_frontier_counts.csv`
- `analysis/output/sprint3_q5_cross_budget.csv`
- `analysis/output/sprint3_q5_verdict.csv`
- `analysis/output/sprint3_mip10800_8x10x.csv`
- `analysis/output/sprint3_bks_changes_after_mip10800.csv`
- `analysis/output/sprint3_cell_sources.csv`
- `analysis/output/sprint3_canonical_3600_cells.csv`
- `analysis/output/sprint3_scale_8x10x_canonical_v2.csv`
- `analysis/output/sprint3_scale_v2_construction.csv`
- `analysis/output/sprint3_seed_window_audit.csv`
- `analysis/output/sprint3_statistical_tests.csv`
- `analysis/output/sprint3_seed_variability.csv`
- `analysis/figures/*.png` and `analysis/figures/*.pdf`
