# Public Analysis Source Matrix

The public package regenerates all declared analysis outputs from package-local
raw evidence. The included `analysis_output/` files are references for
comparison only; `code/reproduce_release.py` does not read them during
calculation.

| Output group | Public outputs | Raw evidence used |
|---|---|---|
| Instance metadata | `master_runs.csv`, `master_instances.csv`, `comparison_table.csv`, `comparison_by_dataset.csv` | `instances/gamspy_py/`, exact CPLEX JSONs in `results/experiments/GAMSPy/`, GRASP/ILS JSONs in `results/experiments/GRASP/`, matheuristic JSONs in `results/experiments/matheuristics/` |
| Equal-budget ILS | `ils_equal_budget.csv`, `ils_equal_budget_runs.csv`, `ils_equal_budget_600.csv`, `ils_equal_budget_600_runs.csv` | ILS v2 run and summary JSONs in `results/experiments/GRASP/results_ils_v2/`, plus S_1 supplement JSONs in `results/experiments/matheuristics/results_production/s1/` |
| Gamma trade-off | `gamma_effect.csv`, `gamma_effect_by_set.csv`, `gamma_tradeoff_2x.csv`, `gamma_tradeoff_all.csv` | 40 gamma=0 JSONs in `results/experiments/GAMSPy/variant_gamma0/results_gamma0/`, canonical gamma=0.001 CPLEX JSONs, and public instance scripts |
| Frontier and scale | `sprint3_frontier_counts.csv`, `sprint3_canonical_3600_cells.csv`, `sprint3_cell_sources.csv`, `sprint3_scale_8x10x_canonical_v2.csv`, `sprint3_mip10800_8x10x.csv`, `sprint3_q5_cross_budget.csv`, `sprint3_q5_verdict.csv` | Short-budget, production, v2 scale, and MIP@10800 matheuristic JSONs plus runner summary CSVs |
| Diagnostics and statistics | `sprint3_descriptive_by_scale.csv`, `sprint3_scale_v2_construction.csv`, `sprint3_seed_variability.csv`, `sprint3_seed_window_audit.csv`, `sprint3_statistical_tests.csv`, `sprint3_bks_audit.csv`, `bks_counterfactual_without_mip10800.csv`, `block_map.csv` | Regenerated master/frontier tables, v2 construction fields in JSON, and Grade C window-log parquet files |
