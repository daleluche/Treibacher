# 8X/10X scale experiment

Instances: IncT8x_2..IncT8x_6 and IncT10x_2..IncT10x_6.
Budget: 3600 seconds. Seed: 1.

RF+FO uses omega=20, step_fo=10, and tl_window_fo=30s.
RF+MIP uses the RF incumbent as a MIP start for the full monolithic model.
MIP is the cold monolithic CPLEX baseline; when this is a decomposition-only rerun, the MIP column is read from the registered Sprint 2.5 results.
Executed methods in this directory: rf+fo, rf+mip.

| instance | rf+fo | rf+mip | mip | best_decomp | decomp_beats_mip | best_method | best_Z |
|---|---:|---:|---:|---|---|---|---:|
| IncT8x_2 | 135291.725000 | 131246.445000 | 131839.464000 | rf+mip | true | rf+mip | 131246.445000 |
| IncT8x_3 | 77987.822000 | 71896.386000 | 71839.478000 | rf+mip | false | mip | 71839.478000 |
| IncT8x_4 | 160989.844000 | 160602.997000 | 166073.216000 | rf+mip | true | rf+mip | 160602.997000 |
| IncT8x_5 | 60653.804000 | 58152.349000 | 59924.391000 | rf+mip | true | rf+mip | 58152.349000 |
| IncT8x_6 | 97667.582000 | 99419.134000 | 103833.803000 | rf+fo | true | rf+fo | 97667.582000 |
| IncT10x_2 | 142834.183000 | 154797.480000 | 185344.308000 | rf+fo | true | rf+fo | 142834.183000 |
| IncT10x_3 | 88476.214000 | 87275.452000 | 102753.138000 | rf+mip | true | rf+mip | 87275.452000 |
| IncT10x_4 | 172982.609000 | 376198.080000 | 185779.606000 | rf+fo | true | rf+fo | 172982.609000 |
| IncT10x_5 | 83018.375000 | 87036.326000 | 68914.120000 | rf+fo | false | mip | 68914.120000 |
| IncT10x_6 | 109047.046000 | 187103.043000 | 130545.565000 | rf+fo | true | rf+fo | 109047.046000 |

Post-hoc H2 comparison for 10X:

- Corrected decomposition wins: 4/5.
- Exploratory post-fix H2 criterion met: true.
