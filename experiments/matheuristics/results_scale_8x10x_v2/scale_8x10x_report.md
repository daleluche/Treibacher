# 8X/10X scale experiment

Instances: IncT8x_2..IncT8x_6 and IncT10x_2..IncT10x_6.
Budget: 3600 seconds. Seed: 1.

RF+FO uses omega=20, step_fo=10, and tl_window_fo=30s.
RF+MIP uses the RF incumbent as a MIP start for the full monolithic model.
MIP is the cold monolithic CPLEX baseline; when this is a decomposition-only rerun, the MIP column is read from the registered Sprint 2.5 results.
Executed methods in this directory: rf+fo, rf+mip.

| instance | rf+fo | rf+mip | mip | best_decomp | decomp_beats_mip | best_method | best_Z |
|---|---:|---:|---:|---|---|---|---:|
| IncT8x_2 |  |  | 131839.464000 |  | false | mip | 131839.464000 |
| IncT8x_3 |  |  | 71839.478000 |  | false | mip | 71839.478000 |
| IncT8x_4 |  |  | 166073.216000 |  | false | mip | 166073.216000 |
| IncT8x_5 |  |  | 59924.391000 |  | false | mip | 59924.391000 |
| IncT8x_6 |  |  | 103833.803000 |  | false | mip | 103833.803000 |
| IncT10x_2 |  |  | 185344.308000 |  | false | mip | 185344.308000 |
| IncT10x_3 |  |  | 102753.138000 |  | false | mip | 102753.138000 |
| IncT10x_4 |  |  | 185779.606000 |  | false | mip | 185779.606000 |
| IncT10x_5 |  | 87036.326000 | 68914.120000 | rf+mip | false | mip | 68914.120000 |
| IncT10x_6 |  |  | 130545.565000 |  | false | mip | 130545.565000 |

Post-hoc H2 comparison for 10X:

- Corrected decomposition wins: 0/5.
- Exploratory post-fix H2 criterion met: false.
