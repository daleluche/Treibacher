# Cold MIP 10800s on 8X/10X

Method: `rf_fo_psp.py --method mip --budget 10800 --seed 1 --threads 0 --log-windows`.

| instance | Z_mip_10800 | best_bound | gap_pct | model_status | solve_status | wall_s |
|---|---:|---:|---:|---|---|---:|
| IncT8x_2 | 128054.148000 | 119114.375350 | 6.981244 | Integer | ResourceInterrupt | 10825.464 |
| IncT8x_3 | 67597.088000 | 56443.211709 | 16.500528 | Integer | ResourceInterrupt | 10853.419 |
| IncT8x_4 | 159561.553000 | 146138.917624 | 8.412199 | Integer | ResourceInterrupt | 10823.465 |
| IncT8x_5 | 59137.359000 | 51343.598242 | 13.179082 | Integer | ResourceInterrupt | 10821.202 |
| IncT8x_6 | 95679.146000 | 86447.032741 | 9.649034 | Integer | ResourceInterrupt | 10858.298 |
| IncT10x_2 | 163595.478000 | 121983.558742 | 25.435862 | Integer | ResourceInterrupt | 10892.084 |
| IncT10x_3 | 80690.614000 | 63022.489107 | 21.896134 | Integer | ResourceInterrupt | 10871.607 |
| IncT10x_4 | 168985.520000 | 149996.931600 | 11.236814 | Integer | ResourceInterrupt | 10860.405 |
| IncT10x_5 | 66696.973000 | 56266.832414 | 15.638102 | Integer | ResourceInterrupt | 10871.540 |
| IncT10x_6 | 111304.255000 | 89998.806037 | 19.141630 | Integer | ResourceInterrupt | 10858.446 |
