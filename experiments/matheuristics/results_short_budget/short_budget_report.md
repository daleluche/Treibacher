# Short-budget operational regime experiment

Instances: IncT3x_3, IncT3x_7, IncT4x_3, IncT4x_7, IncT5x_3, IncT5x_10.
Budgets: 300s and 600s. Seed: 1.

RF+FO uses the Tarefa 2.2 recommendation: omega=20, step_fo=10, tl_window_fo=30s.
RF+MIP runs RF and then solves the full monolithic MIP with the RF incumbent as a MIP start.
MIP is the cold monolithic CPLEX baseline with the same wall-clock budget and no RF.

ILS v2 references were not rerun. For each instance and budget, the script scans the ten existing
experiments/GRASP/results_ils_v2/<instance>_run*.json files and selects the minimum Z among
improvements entries with time_s <= budget.

## Consolidated Table

| instance | budget_s | rf+fo | rf+mip | mip | ils_v2_until_budget | best_method | best_Z |
|---|---:|---:|---:|---:|---:|---|---:|
| IncT3x_3 | 300 | 47769.556000 | 46239.367000 | 48147.231000 | 53728.903000 | rf+mip | 46239.367000 |
| IncT3x_3 | 600 | 48237.316000 | 46190.017000 | 46210.117000 | 53728.903000 | rf+mip | 46190.017000 |
| IncT3x_7 | 300 | 16702.607000 | 16603.182000 | 16664.600000 | 23026.037000 | rf+mip | 16603.182000 |
| IncT3x_7 | 600 | 16532.257000 | 16441.491000 | 16651.675000 | 23026.037000 | rf+mip | 16441.491000 |
| IncT4x_3 | 300 | 51437.320000 | 53449.044000 | 50288.764000 | 63255.293000 | mip | 50288.764000 |
| IncT4x_3 | 600 | 51777.217000 | 49578.045000 | 49521.664000 | 62926.853000 | mip | 49521.664000 |
| IncT4x_7 | 300 | 23259.550000 | 23534.720000 | 22685.483000 | 38851.599000 | mip | 22685.483000 |
| IncT4x_7 | 600 | 20675.807000 | 21389.233000 | 21657.453000 | 26897.394000 | rf+fo | 20675.807000 |
| IncT5x_3 | 300 | 93627.594000 | 380937.341000 | 56023.127000 | 69520.774000 | mip | 56023.127000 |
| IncT5x_3 | 600 | 64791.163000 | 56597.058000 | 55824.522000 | 68096.090000 | mip | 55824.522000 |
| IncT5x_10 | 300 | 999420.861000 | 283461.421000 | 18657.518000 | 26440.814000 | mip | 18657.518000 |
| IncT5x_10 | 600 | 18776.770000 | 18536.715000 | 17880.240000 | 26440.814000 | mip | 17880.240000 |
