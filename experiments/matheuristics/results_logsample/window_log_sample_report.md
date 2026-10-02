# Window-Log Schema Audit Sample

These runs are audit samples only and are not part of the production result tables.

## Runs

| instance | method | budget_s | seed | construction_used | window_log_rows | window_log_file | instrumentation_wall_time_s | wall_time_total_s | overhead_percent |
| --- | --- | ---: | ---: | --- | ---: | --- | ---: | ---: | ---: |
| IncT10x_2 | rf+fo | 900 | 99 | greedy | 15 | `window_logs/IncT10x_2_rf_fo_seed99_logsample_windows.parquet` | 0.433177 | 903.621 | 0.047938 |
| Ale_1 | rf+fo | 120 | 99 | greedy | 12 | `window_logs/Ale_1_rf_fo_seed99_logsample_windows.parquet` | 0.078767 | 112.160 | 0.070227 |

## Schema Notes

- Each row is one solved window.
- The sample runs used the adaptive greedy construction because the short-budget guard made windowed RF ineligible.
- Therefore, the sample window logs contain F&O rows (`FO_sweep` and/or `FO_random`) and no RF-window rows.
- Marginal columns summarize `EQ_DEM` and `EQ_PROP` records by the active window after each solve.
- For MIP solves, GAMS reports marginal values with the integer solution context available after the solve; downstream analysis should treat them as diagnostic LP-style signals, not as MIP dual certificates.
- Per-period incumbent profiles before each solve are stored as JSON arrays in `shortage_by_period_before_json` and `excess_by_period_before_json`.
