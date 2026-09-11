# 8X/10X scale experiment

Instances: IncT8x_2..IncT8x_6 and IncT10x_2..IncT10x_6.
Budget: 3600 seconds. Seed: 1.

RF+FO uses omega=20, step_fo=10, and tl_window_fo=30s.
RF+MIP uses the RF incumbent as a MIP start for the full monolithic model.
MIP is the cold monolithic CPLEX baseline.

| instance | rf+fo | rf+mip | mip | best_method | best_Z |
|---|---:|---:|---:|---|---:|
| IncT8x_2 | 141146.399000 | 134500.543000 | 131839.464000 | mip | 131839.464000 |
| IncT8x_3 | 79473.057000 | 68783.650000 | 71839.478000 | rf+mip | 68783.650000 |
| IncT8x_4 | 159958.731000 | 158113.714000 | 166073.216000 | rf+mip | 158113.714000 |
| IncT8x_5 | 71855.978000 | 61371.845000 | 59924.391000 | mip | 59924.391000 |
| IncT8x_6 | 100008.734000 | 98744.057000 | 103833.803000 | rf+mip | 98744.057000 |
| IncT10x_2 | 209676.831000 | 165438.755000 | 185344.308000 | rf+mip | 165438.755000 |
| IncT10x_3 | 128314.728000 | 102151.544000 | 102753.138000 | rf+mip | 102151.544000 |
| IncT10x_4 | 216208.276000 | 188575.590000 | 185779.606000 | mip | 185779.606000 |
| IncT10x_5 | 154102.825000 | 165170.737000 | 68914.120000 | mip | 68914.120000 |
| IncT10x_6 | 161011.652000 | 127960.821000 | 130545.565000 | rf+mip | 127960.821000 |
