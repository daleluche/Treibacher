# Manuscript Number Provenance

This file maps the manuscript's empirical and configuration numbers to versioned
repository artifacts. Commands are intended to be run from the repository root.

## UNVERIFIED Lines

| Value | Local | Reason |
|---|---|---|
| 2011 | `paper/sections/introduction.tex:35` | Historical shorthand for the earlier thesis-era verdict; no cited or versioned artifact now carries the exact year after removal of the uncited thesis entry. |

All other empirical numbers listed below are traced to versioned CSV, JSON, script, or
instance artifacts.

## Abstract, Introduction, and Conclusions

| Value | Local | Source | Command of verification |
|---|---|---|---|
| 60 derived instances | `paper/main.tex:62`, `paper/main.tex:102`, `paper/sections/introduction.tex:92`, `paper/sections/conclusions.tex:39` | `experiments/GAMSPy/S`, `2X`, `3X`, `4X`, `5X`, `8X`, `10X` | `python analysis/verify_manuscript_numbers.py` |
| 19 to 190 periods | `paper/main.tex:63`, `paper/sections/introduction.tex:62`, `paper/sections/introduction.tex:93` | GAMSPy instance files parsed by `experiments/matheuristics/psp_instance.py` | `python analysis/verify_manuscript_numbers.py` |
| about 150 periods upward | `paper/main.tex:74`, `paper/sections/introduction.tex:67`, `paper/sections/conclusions.tex:29` | `analysis/output/sprint3_frontier_counts.csv`; `analysis/output/sprint3_descriptive_by_scale.csv` | `python analysis/verify_manuscript_numbers.py` |
| 5--10 minutes; 1--3 hours | `paper/sections/introduction.tex:64` | Protocol budgets in `experiments/matheuristics/run_production.py` and result JSON `params.budget` | `python analysis/sprint3_report.py && python analysis/verify_manuscript_numbers.py` |
| `|T| <= 95` | `paper/sections/conclusions.tex:58` | `experiments/GAMSPy/5X/*.py`; `analysis/output/comparison_by_dataset.csv` | `python analysis/verify_manuscript_numbers.py` |

## Experiments Section

| Value | Local | Source | Command of verification |
|---|---|---|---|
| real order book plus 60 derived instances | `paper/sections/experiments.tex:7` | `experiments/GAMSPy/S/REAL_1.py` plus 60 public instance files | `python analysis/verify_manuscript_numbers.py` |
| `|J|=159`, `|I|=50` | `paper/sections/experiments.tex:9` | GAMSPy instance files parsed by `load_instance` | `python analysis/verify_manuscript_numbers.py` |
| all 40 files of 2X--5X match record by record | `paper/sections/experiments.tex:15` | `experiments/instance_generator/README.md`; `experiments/instance_generator/generation_manifest.json`; generated families in `experiments/GAMSPy/{2X,3X,4X,5X}` | `python experiments/instance_generator/generate_inct.py --validate-only` |
| 8 cores / 16 threads, 32 GB RAM, CPLEX 22.1.2 | `paper/sections/experiments.tex:30-31` | Run JSON hardware/provenance fields, e.g. `experiments/matheuristics/results_production/real/REAL_1_mip_seed1_b10800.json` | `python -c "import json; d=json.load(open('experiments/matheuristics/results_production/real/REAL_1_mip_seed1_b10800.json')); print(d['hardware'], d['versions'])"` |
| 600, 3,600, 10,800 s budgets | `paper/sections/experiments.tex:34` | Result JSON `params.budget` and production runner scripts | `python analysis/sprint3_report.py && python analysis/verify_manuscript_numbers.py` |
| two hardest 5X tuning instances | `paper/sections/experiments.tex:53` | `experiments/matheuristics/results_tuning/tuning_summary.md` | `Get-Content experiments/matheuristics/results_tuning/tuning_summary.md` |
| five base patterns for 8X and 10X | `paper/sections/experiments.tex:62`, `paper/sections/experiments.tex:277` | `experiments/GAMSPy/8X/IncT8x_2.py` ... `IncT8x_6.py`; `experiments/GAMSPy/10X/IncT10x_2.py` ... `IncT10x_6.py` | `python analysis/verify_manuscript_numbers.py` |
| Real and S close under one hour; mean 8 s | `paper/sections/experiments.tex:77-79` | `analysis/output/comparison_by_dataset.csv`; `analysis/output/comparison_table.csv` | `python analysis/compute_gaps.py && python analysis/verify_manuscript_numbers.py` |
| 2X mean 687 s; all proven optimal | `paper/sections/experiments.tex:79-80` | `analysis/output/comparison_by_dataset.csv`; `analysis/output/comparison_table.csv` | `python analysis/compute_gaps.py && python analysis/verify_manuscript_numbers.py` |
| 3X/4X/5X three-hour mean gaps 1.7%, 3.9%, 7.2% | `paper/sections/experiments.tex:81-82`, `paper/sections/experiments.tex:137` | `analysis/output/comparison_by_dataset.csv` | `python analysis/verify_manuscript_numbers.py` |
| published shortage 10,475 kg; 26 s | `paper/sections/experiments.tex:85-87` | `analysis/output/real_instance_crosscheck.md`; cited Luche et al. (2009) | `Get-Content analysis/output/real_instance_crosscheck.md` |
| reconstructed shortage 10,475 kg; objective 11,442.6 | `paper/sections/experiments.tex:89-90` | `experiments/matheuristics/results_production/real/REAL_1_mip_seed1_b10800.json` | `python analysis/verify_manuscript_numbers.py` |
| IncT5x_10 about 17% above bound | `paper/sections/experiments.tex:114`, `paper/sections/problem_model.tex:127` | `analysis/output/comparison_table.csv` | `python -c "import pandas as pd; r=pd.read_csv('analysis/output/comparison_table.csv').query(\"instance=='IncT5x_10'\").iloc[0]; print(r[['cplex_gap_pct','cplex_bound']])"` |
| 40 gamma instances at three hours | `paper/sections/experiments.tex:126-127` | `analysis/output/gamma_effect.csv` | `python analysis/verify_manuscript_numbers.py` |
| gamma=0 mean times 25, 48, 114, 178 s | `paper/sections/experiments.tex:134` | `analysis/output/gamma_effect_by_set.csv` | `python analysis/verify_manuscript_numbers.py` |
| gamma=0.001: only 2X closed; 3X--5X gaps 1.7%, 3.9%, 7.2% | `paper/sections/experiments.tex:135-137` | `analysis/output/gamma_effect_by_set.csv` | `python analysis/verify_manuscript_numbers.py` |
| holding term median 13% to 29% | `paper/sections/experiments.tex:143` | `analysis/output/gamma_effect_by_set.csv` | `python analysis/verify_manuscript_numbers.py` |
| seven of ten 2X instances have higher backlog under gamma=0.001 | `paper/sections/experiments.tex:152` | `analysis/output/gamma_tradeoff_2x.csv` | `python analysis/verify_manuscript_numbers.py` |
| 0.12% median and 1.94% max backlog increase; 34.3% median inventory fall | `paper/sections/experiments.tex:153-155` | `analysis/output/gamma_tradeoff_2x.csv` | `python analysis/verify_manuscript_numbers.py` |
| 1,836 kg backlog for 26.3 million kg-period inventory reduction | `paper/sections/experiments.tex:156` | `analysis/output/gamma_tradeoff_2x.csv` | `python analysis/verify_manuscript_numbers.py` |
| direction holds in 31 of 40 gamma instances | `paper/sections/experiments.tex:162` | `analysis/output/gamma_tradeoff_all.csv` | `python -c "import pandas as pd; d=pd.read_csv('analysis/output/gamma_tradeoff_all.csv'); print(((d.delta_shortage>0)&d.instance.str.startswith('IncT')).sum())"` |
| gamma=0 mean objective 58,200.5 in 2X--5X | `paper/sections/experiments.tex:170` | `analysis/output/gamma_effect_by_set.csv` | `python analysis/verify_manuscript_numbers.py` |
| gamma=0.001 mean objectives 63,780, 66,812, 69,842, 73,403 | `paper/sections/experiments.tex:176-177` | `analysis/output/gamma_effect_by_set.csv` | `python analysis/verify_manuscript_numbers.py` |
| ILS-v2 deficits 0.5%, 2.6%, 10.4%, 16.4%, 23.9% | `paper/sections/experiments.tex:208-209` | `analysis/output/comparison_by_dataset.csv` | `python analysis/verify_manuscript_numbers.py` |
| 10--0, 9--1, 6--4 win counts through 5X | `paper/sections/experiments.tex:220-221` | `analysis/output/comparison_by_dataset.csv`; `analysis/output/comparison_table.csv` | `python analysis/compute_gaps.py && python analysis/verify_manuscript_numbers.py` |
| IncT5x_10 RF+FO 4.6% below CPLEX@3h incumbent | `paper/sections/experiments.tex:222` | `analysis/output/comparison_table.csv`; `experiments/matheuristics/results_pilot/IncT5x_10_rf_fo_seed1.json` | `python analysis/verify_manuscript_numbers.py` |
| 600 s: 3X--5X decompositions 4--5 wins per set; 8X RF+MIP 3/5; 10X RF+FO 4/5 | `paper/sections/experiments.tex:244-246` | `analysis/output/sprint3_descriptive_by_scale.csv`; `analysis/output/sprint3_frontier_counts.csv` | `python analysis/verify_manuscript_numbers.py` |
| 0.14% median, p=0.047 | `paper/sections/experiments.tex:248-249` | `analysis/output/sprint3_statistical_tests.csv` | `python analysis/verify_manuscript_numbers.py` |
| +0.01% on S to -37.8% on 10X | `paper/sections/experiments.tex:252` | `analysis/output/sprint3_descriptive_by_scale.csv` | `python analysis/verify_manuscript_numbers.py` |
| RF+FO beats truncated ILS by median 25.7% on six pilot cells | `paper/sections/experiments.tex:255` | `analysis/output/sprint3_statistical_tests.csv`; ILS trajectories in `experiments/GRASP/results_ils_v2` | `python analysis/verify_manuscript_numbers.py` |
| H1 unsupported: 2/6 and 3/6 | `paper/sections/experiments.tex:260-261` | `analysis/output/sprint2_report.md`; `experiments/matheuristics/results_short_budget/short_budget_summary.csv` | `Get-Content analysis/output/sprint2_report.md` |
| corrected policy repairs all four failure cases | `paper/sections/experiments.tex:264` | `experiments/matheuristics/results_short_budget_v2/short_budget_v2_report.md` | `Get-Content experiments/matheuristics/results_short_budget_v2/short_budget_v2_report.md` |
| 8X and 10X: `|T|=152` and `190`; 30,210 binaries | `paper/sections/experiments.tex:274-275` | GAMSPy instance files | `python analysis/verify_manuscript_numbers.py` |
| 3600 s winners: RF+MIP 3/5 at 8X; RF+FO 3/5 at 10X | `paper/sections/experiments.tex:275-277` | `analysis/output/sprint3_frontier_counts.csv` | `python analysis/verify_manuscript_numbers.py` |
| minimum attainable two-sided p=0.0625 | `paper/sections/experiments.tex:279` | `analysis/output/sprint3_statistical_tests.csv` | `python analysis/verify_manuscript_numbers.py` |
| RF+FO +1.2% at 8X, -13.9% at 10X; RF+MIP -3.0% at 8X, +26.3% at 10X | `paper/sections/experiments.tex:280-282` | `analysis/output/sprint3_statistical_tests.csv` | `python analysis/verify_manuscript_numbers.py` |
| IncT10x_4: RF+MIP 376,198; RF+FO 172,983 | `paper/sections/experiments.tex:287-288` | `analysis/output/sprint3_scale_8x10x_canonical_v2.csv` | `python analysis/verify_manuscript_numbers.py` |
| Q5 yes: 4/5 at 8X and 3/5 at 10X; six BKS improvements | `paper/sections/experiments.tex:296-300` | `analysis/output/sprint3_q5_verdict.csv`; `analysis/output/sprint3_bks_changes_after_mip10800.csv` | `python analysis/verify_manuscript_numbers.py` |
| IncT10x_2 14.5% and IncT10x_6 2.1% resist tripled budget | `paper/sections/experiments.tex:300-301` | `analysis/output/sprint3_q5_cross_budget.csv` | `python analysis/verify_manuscript_numbers.py` |
| monolith 3x budget restores lead at 8/10 largest instances | `paper/sections/experiments.tex:303-304` | `analysis/output/sprint3_q5_cross_budget.csv` | `python analysis/verify_manuscript_numbers.py` |

## Sections 3, 4, and 5

| Value | Local | Source | Command of verification |
|---|---|---|---|
| `a_ij >= 0`, `d_it >= 0`, `x_jt in {0,1}` | `paper/sections/problem_model.tex:35-39` | Mathematical model in `paper/sections/problem_model.tex` and solver implementation | `rg -n "EQ_DEM|EQ_PROP|Binary|Positive" experiments/matheuristics/rf_fo_psp.py` |
| `gamma=0.001` | `paper/sections/problem_model.tex:68`, `paper/sections/experiments.tex:57`, `paper/sections/experiments.tex:122` | Objective evaluator and result analysis | `rg -n "0.001|PESO_ESTOQUE" experiments/matheuristics experiments/GRASP analysis` |
| largest dimensions `|J|=159`, `|T|=190`, 30,210 binaries | `paper/sections/problem_model.tex:79-80` | GAMSPy 10X instance files | `python analysis/verify_manuscript_numbers.py` |
| real order book: 19 periods, 159 processes, 50 items, 36 demanded, 279,400 kg | `paper/sections/problem_model.tex:96-97` | `experiments/GAMSPy/S/REAL_1.py` | `python analysis/verify_manuscript_numbers.py` |
| IncT factors 2--5, 8, 10; up to 190 periods | `paper/sections/problem_model.tex:103-105` | `experiments/instance_generator/generate_inct.py`; GAMSPy family folders | `python analysis/verify_manuscript_numbers.py` |
| RF parameters `sigma=10`, `delta=5`, `ell_RF=120 s`, `optcr=10^-3`, `B_RF=min{0.25B,w ell_RF}` | `paper/sections/matheuristics.tex:46-54`, `paper/sections/matheuristics.tex:153-157` | `experiments/matheuristics/rf_fo_psp.py` defaults and JSON params | `rg -n "sigma|tl_rf|optcr=0.001|budget_rf" experiments/matheuristics/rf_fo_psp.py` |
| budget guard 10 s | `paper/sections/matheuristics.tex:62`, `paper/sections/matheuristics.tex:104` | `experiments/matheuristics/rf_fo_psp.py` | `rg -n "10.0|budget_guard|greedy" experiments/matheuristics/rf_fo_psp.py` |
| FO parameters `omega=20`, step 10, `ell_FO=30 s`, `optcr=10^-2`, improvement `10^-6` | `paper/sections/matheuristics.tex:77-83`, `paper/sections/matheuristics.tex:158-160` | `experiments/matheuristics/rf_fo_psp.py`; tuning results | `rg -n "omega|step_fo|tl_fo|optcr=0.01|EPS" experiments/matheuristics/rf_fo_psp.py` |
| tuning grid `{12,20,28} x {30,60}` and selected `omega=20`, `ell_FO=30 s` | `paper/sections/matheuristics.tex:90-95` | `experiments/matheuristics/results_tuning/tuning_summary.md`; JSON files in `results_tuning` | `Get-Content experiments/matheuristics/results_tuning/tuning_summary.md` |
| RF+FO tuning: omega 12 gap +7.2%; omega 20 gap -1.1% | `paper/sections/matheuristics.tex:94-95` | `experiments/matheuristics/results_tuning/tuning_summary.md` | `Get-Content experiments/matheuristics/results_tuning/tuning_summary.md` |
| `|T| >= 152` RF+MIP skips RF | `paper/sections/matheuristics.tex:126` | `experiments/matheuristics/rf_fo_psp.py`; v2 run JSON `construction_used` | `rg -n "skip_rf_for_large_mip|152|construction_used" experiments/matheuristics/rf_fo_psp.py` |
| ILS constants: `alpha={0,...,0.30}`, tabu `[5,12]`, `|T|>40`, Or-opt 1--3, ten runs | `paper/sections/metaheuristic.tex:30-33` | `experiments/GRASP/grasp_ils_psp.py` | `rg -n "ALPHA_VALUES|TABU_TENURE|WINDOW_T_THRESH|OR_OPT_K_VALUES|n_runs" experiments/GRASP/grasp_ils_psp.py` |
| ILS v1-to-v2 median improvements 5.7%, 20.5%, 34.6%, 42.1%, 47.9%, 39.5% | `paper/sections/metaheuristic.tex:47-49` | `analysis/output/master_instances.csv` after path-relinking accounting fix | `python analysis/build_master_dataset.py && python analysis/verify_manuscript_numbers.py` |
