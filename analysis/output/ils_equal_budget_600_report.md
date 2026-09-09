# ILS v2 strict equal-budget audit

The comparison value is reconstructed from each run trajectory using only improvements with `time_s <= 600.0`. Within-run path relinking before the cutoff remains eligible; cross-run path relinking from summary files is reported as `ILS_v2_pr` and excluded from equal-budget comparisons.

## Execution universes

| universe | count |
|---|---:|
| raw_ils_execution_records | 520 |
| derived_instances_for_comparisons | 50 |
| real_order_book_instances | 1 |
| legacy_ale1_instances | 1 |

## Non-compliant gain metrics

| metric | postbudget_gain_pct | cross_pr_gain_pct | total_noncompliant_gain_pct |
|---|---|---|---|
| mean | 6.434399 | 1.013249 | 7.369762 |
| median | 5.196099 | 0.415218 | 5.878577 |
| max | 23.390294 | 7.118505 | 23.959636 |

## Mean total non-compliant gain by large family

| dataset | mean_total_noncompliant_gain_pct |
|---|---|
| 2X | 6.609765 |
| 3X | 10.234947 |
| 4X | 9.797562 |
| 5X | 8.510580 |

## Instances without a reproducible strict-budget schedule

| dataset | instance | Z_best_truncated | selected_source_path | selected_time_s |
|---|---|---|---|---|
| 2X | IncT2X_1 | 43176.912000 | experiments\GRASP\results_ils_v2\IncT2X_1_run02.json | 225.195000 |
| 2X | IncT2X_10 | 11568.743000 | experiments\GRASP\results_ils_v2\IncT2X_10_run10.json | 497.035000 |
| 2X | IncT2X_2 | 110717.709000 | experiments\GRASP\results_ils_v2\IncT2X_2_run04.json | 151.780000 |
| 2X | IncT2X_3 | 47893.987000 | experiments\GRASP\results_ils_v2\IncT2X_3_run09.json | 8.135000 |
| 2X | IncT2X_4 | 137355.840000 | experiments\GRASP\results_ils_v2\IncT2X_4_run04.json | 196.010000 |
| 2X | IncT2X_5 | 40466.208000 | experiments\GRASP\results_ils_v2\IncT2X_5_run09.json | 118.294000 |
| 2X | IncT2X_6 | 75739.559000 | experiments\GRASP\results_ils_v2\IncT2X_6_run09.json | 523.809000 |
| 2X | IncT2X_7 | 14223.675000 | experiments\GRASP\results_ils_v2\IncT2X_7_run04.json | 73.457000 |
| 2X | IncT2X_8 | 173189.523000 | experiments\GRASP\results_ils_v2\IncT2X_8_run07.json | 73.690000 |
| 2X | IncT2X_9 | 21615.691000 | experiments\GRASP\results_ils_v2\IncT2X_9_run10.json | 291.445000 |
| 3X | IncT3x_1 | 50322.222000 | experiments\GRASP\results_ils_v2\IncT3x_1_run04.json | 470.030000 |
| 3X | IncT3x_10 | 16971.589000 | experiments\GRASP\results_ils_v2\IncT3x_10_run06.json | 441.523000 |
| 3X | IncT3x_2 | 122785.592000 | experiments\GRASP\results_ils_v2\IncT3x_2_run02.json | 111.053000 |
| 3X | IncT3x_3 | 53728.903000 | experiments\GRASP\results_ils_v2\IncT3x_3_run06.json | 119.210000 |
| 3X | IncT3x_4 | 143696.622000 | experiments\GRASP\results_ils_v2\IncT3x_4_run05.json | 522.189000 |
| 3X | IncT3x_5 | 56909.256000 | experiments\GRASP\results_ils_v2\IncT3x_5_run06.json | 123.306000 |
| 3X | IncT3x_6 | 83039.315000 | experiments\GRASP\results_ils_v2\IncT3x_6_run03.json | 420.097000 |
| 3X | IncT3x_7 | 23026.037000 | experiments\GRASP\results_ils_v2\IncT3x_7_run04.json | 276.037000 |
| 3X | IncT3x_8 | 187687.958000 | experiments\GRASP\results_ils_v2\IncT3x_8_run09.json | 438.673000 |
| 3X | IncT3x_9 | 28565.637000 | experiments\GRASP\results_ils_v2\IncT3x_9_run07.json | 551.633000 |
| 4X | IncT4x_1 | 60960.053000 | experiments\GRASP\results_ils_v2\IncT4x_1_run07.json | 248.136000 |
| 4X | IncT4x_2 | 133705.017000 | experiments\GRASP\results_ils_v2\IncT4x_2_run03.json | 492.218000 |
| 4X | IncT4x_3 | 62926.853000 | experiments\GRASP\results_ils_v2\IncT4x_3_run03.json | 578.983000 |
| 4X | IncT4x_4 | 163195.834000 | experiments\GRASP\results_ils_v2\IncT4x_4_run05.json | 286.818000 |
| 4X | IncT4x_6 | 91992.448000 | experiments\GRASP\results_ils_v2\IncT4x_6_run02.json | 392.650000 |
| 4X | IncT4x_8 | 198997.489000 | experiments\GRASP\results_ils_v2\IncT4x_8_run09.json | 233.632000 |
| 4X | IncT4x_9 | 37691.430000 | experiments\GRASP\results_ils_v2\IncT4x_9_run09.json | 269.518000 |
| 5X | IncT5x_1 | 70735.232000 | experiments\GRASP\results_ils_v2\IncT5x_1_run02.json | 26.005000 |
| 5X | IncT5x_10 | 26440.814000 | experiments\GRASP\results_ils_v2\IncT5x_10_run10.json | 144.068000 |
| 5X | IncT5x_2 | 141113.347000 | experiments\GRASP\results_ils_v2\IncT5x_2_run04.json | 388.714000 |
| 5X | IncT5x_4 | 178798.190000 | experiments\GRASP\results_ils_v2\IncT5x_4_run03.json | 306.774000 |
| 5X | IncT5x_6 | 102621.717000 | experiments\GRASP\results_ils_v2\IncT5x_6_run09.json | 424.777000 |
| 5X | IncT5x_8 | 202244.369000 | experiments\GRASP\results_ils_v2\IncT5x_8_run03.json | 30.991000 |
| Real | Ale_1 | 89327.058000 | experiments\GRASP\results_ils_v2\Ale_1_run04.json | 366.691000 |
| Real order book | REAL_1 | 11478.225000 | experiments\matheuristics\results_production\real\REAL_1_run03.json | 555.216000 |
| S | S_1 | 37575.875000 | experiments\matheuristics\results_production\s1\S_1_run07.json | 475.719000 |
| S | S_10 | 6666.268000 | experiments\GRASP\results_ils_v2\Ale_10_run06.json | 488.416000 |
| S | S_3 | 42718.013000 | experiments\GRASP\results_ils_v2\Ale_3_run07.json | 44.642000 |
| S | S_4 | 128299.397000 | experiments\GRASP\results_ils_v2\Ale_4_run05.json | 19.207000 |
| S | S_5 | 36374.363000 | experiments\GRASP\results_ils_v2\Ale_5_run05.json | 64.442000 |
| S | S_6 | 68207.592000 | experiments\GRASP\results_ils_v2\Ale_6_run10.json | 278.773000 |
| S | S_7 | 10596.618000 | experiments\GRASP\results_ils_v2\Ale_7_run03.json | 202.255000 |
| S | S_8 | 162758.314000 | experiments\GRASP\results_ils_v2\Ale_8_run08.json | 255.217000 |
| S | S_9 | 15980.098000 | experiments\GRASP\results_ils_v2\Ale_9_run08.json | 76.654000 |

