# Window-Log Schema Corrections Sample

This folder contains a schema-correction audit sample. It is not part of the production result tables.

## Run

Command:

```powershell
python experiments\matheuristics\rf_fo_psp.py --instance experiments\GAMSPy\Real\Ale_2.py --method rf+fo --budget 1800 --seed 99 --log-windows --output-dir experiments\matheuristics\results_logsample_v2 --output-suffix _rf_logsample
```

Outputs:

- JSON: `Ale_2_rf_fo_seed99_rf_logsample.json`
- Window log: `window_logs/Ale_2_rf_fo_seed99_rf_logsample_windows.parquet`

## Audit Checks

| check | result |
| --- | --- |
| Rows | 2181 |
| Columns | 34 |
| Identity columns present | `instance`, `dataset`, `method`, `seed`, `budget_s`, `run_id` |
| Full-horizon dual arrays present | `eqdem_marginal_abs_sum_by_period_json`, `eqprop_marginal_by_period_json` |
| Full-horizon array length | 19 values per row |
| RF rows present | 3 |
| F&O rows present | 2178 |
| RF/F&O schemas identical | true |
| Status values observed | `solved` |
| Status field supports interrupted solves | yes, via ResourceInterrupt classification in `rf_fo_psp.py` |
| Tail relaxed fraction column | `xr_frac_nonzero` |
| Instrumentation wall time | 17.636667 s |
| Total wall time | 1791.637 s |
| Instrumentation overhead | 0.984388% |

## RF Rows

| phase | window_start | window_end | status | Z_before | Z_after | accepted | xr_frac_nonzero |
| --- | ---: | ---: | --- | ---: | ---: | --- | ---: |
| RF | 1 | 10 | solved | 2517294.000 | 396126.490 | true | 0.020964 |
| RF | 6 | 15 | solved | 396126.490 | 122075.683 | true | 0.015723 |
| RF | 10 | 19 | solved | 122075.683 | 99950.709 | true | 0.000000 |

## Notes

- `xr_frac_nonzero` is the fraction of relaxed-tail `XR` levels with absolute value greater than `1e-6`.
- `eqdem_marginal_abs_sum_by_period_json` stores one value per period: the sum over products of absolute `EQ_DEM[i,t]` marginal values.
- `eqprop_marginal_by_period_json` stores one `EQ_PROP[t]` marginal value per period.
- For MIP solves, GAMS reports marginal values with the integer solution context available after the solve; treat these as diagnostic LP-style signals, not MIP dual certificates.
