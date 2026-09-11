# ILS v2 strict equal-budget audit

The comparison value is reconstructed from each run trajectory using only improvements with `time_s <= 3600.0`. Within-run path relinking before the cutoff remains eligible; cross-run path relinking from summary files is reported as `ILS_v2_pr` and excluded from equal-budget comparisons.

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
| mean | 0.085211 | 1.013249 | 1.097379 |
| median | 0.000000 | 0.415218 | 0.463210 |
| max | 1.441019 | 7.118505 | 7.118505 |

## Mean total non-compliant gain by large family

| dataset | mean_total_noncompliant_gain_pct |
|---|---|
| 2X | 0.284080 |
| 3X | 1.531604 |
| 4X | 1.205740 |
| 5X | 1.886004 |

## Instances without a reproducible strict-budget schedule

| dataset | instance | Z_at_cutoff | selected_source_path | selected_time_s |
|---|---|---|---|---|
| 4X | IncT4x_7 | 26629.952000 | experiments\GRASP\results_ils_v2\IncT4x_7_run08.json | 2471.327000 |
| 5X | IncT5x_2 | 128756.484000 | experiments\GRASP\results_ils_v2\IncT5x_2_run10.json | 3512.629000 |

