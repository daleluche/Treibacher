# Short-Budget V2 Post-Hoc Regression

These runs are post-hoc Sprint 3.2 checks for the adaptive greedy construction policy.
They do not replace the pre-registered Sprint 2 short-budget results.

Configuration:

- Budget: 300 seconds.
- Seed: 1.
- `rf+fo`: `omega = 20`, `step_fo = 10`, `tl_window_fo = 30`.
- Construction rule: greedy construction is used when `budget_rf / n_windows < 10s`.

Acceptance criterion:

| instance | method | construction | Z_final | ILS v2 @300s | passed |
| --- | --- | --- | ---: | ---: | --- |
| IncT5x_10 | rf+fo | greedy | 19557.383 | 26440.814 | true |
| IncT5x_10 | rf+mip | greedy | 20291.053 | 26440.814 | true |
| IncT5x_3 | rf+fo | greedy | 64099.456 | 69520.774 | true |
| IncT5x_3 | rf+mip | greedy | 59061.483 | 69520.774 | true |
