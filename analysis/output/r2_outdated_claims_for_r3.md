# R2 Outdated Manuscript Claims for R3

R2 updates the ILS accounting, removes ILS v1 from publishable comparisons, and
changes the block-statistics schema. The following manuscript claims should be
patched in R3; no manuscript prose was edited in R2.

## ILS Gap Values

- `paper/sections/experiments.tex:206-209` currently reports that ILS trails
  the solver primal by `0.5%` on S, `2.6%` on 2X, `10.4%` on 3X, `16.4%` on
  4X, and `23.9%` on 5X. After the R2 accounting, the corresponding mean gaps
  in `analysis/output/comparison_by_dataset.csv` are `1.3586%`, `2.8669%`,
  `12.2366%`, `17.5183%`, and `24.4331%`.

## ILS v1 Developmental Comparison

- `paper/sections/metaheuristic.tex:45-50` still reports v1-to-v2 median
  improvements. R2 retires ILS v1 from publishable comparisons because the v1
  runs are unequal-budget and have irregular coverage. This paragraph should be
  removed or rewritten without v1 performance claims.

## Cross-Run Path Relinking

- `paper/sections/introduction.tex:52-54` describes the published ILS baseline
  as including cross-run path relinking.
- `paper/sections/metaheuristic.tex:25-28` says a final cross-run relinking step
  is applied after all workers finish.

R2 excludes cross-run path relinking from the strict-budget ILS comparison and
disables it by default in the released GRASP/ILS code. The manuscript should
distinguish intra-run path relinking, which remains part of each worker, from
the historical post-hoc cross-run step, which is retained only in raw audit
fields.

## Statistical Table Framing

- Any prose around `paper/tables/tab_stats.tex` should reflect the new R2
  schema: mean and median block deltas are reported separately; p-values are
  unadjusted sensitivity analyses; five-block 8X and 10X rows are descriptive
  and receive no p-value; the heterogeneous 8X/10X pooled aggregate is retained
  in CSV only, not in the main LaTeX table.
