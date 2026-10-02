# F&O Full-Horizon Early-Stop Sample

This sample verifies the early-stop rule for F&O when `omega >= T`.
It is not part of the production result tables.

Command:

```powershell
python experiments\matheuristics\rf_fo_psp.py --instance experiments\GAMSPy\Real\Ale_2.py --method rf+fo --budget 1800 --seed 99 --omega 20 --step-fo 10 --tl-fo 30 --log-windows --output-dir experiments\matheuristics\results_logsample_earlystop --output-suffix _earlystop_logsample_w20
```

Outputs:

- JSON: `Ale_2_rf_fo_seed99_earlystop_logsample_w20.json`
- Window log: `window_logs/Ale_2_rf_fo_seed99_earlystop_logsample_w20_windows.parquet`

Checks:

| check | result |
| --- | --- |
| `early_stop_reason` | `fo_window_covers_horizon` |
| `Z_final <= 99950.709` | true (`99950.709`) |
| window-log rows | 4 |
| RF rows | 3 |
| F&O rows | 1 |
| full-horizon F&O reslim | 1796.616190 s |
| full-horizon F&O status | `solved` |
| instrumentation overhead | 0.514685% |

Window-log phases:

| phase | window_start | window_end | status | Z_before | Z_after | accepted |
| --- | ---: | ---: | --- | ---: | ---: | --- |
| RF | 1 | 10 | solved | 2517294.000 | 396126.490 | true |
| RF | 6 | 15 | solved | 396126.490 | 122075.683 | true |
| RF | 10 | 19 | solved | 122075.683 | 99950.709 | true |
| FO_sweep | 1 | 19 | solved | 99950.709 | 99950.709 | false |
