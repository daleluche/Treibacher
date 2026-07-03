# Treibacher

Repository for computational experiments related to a scientific article on the process selection problem.

## Repository Structure

```text
.
├── data/
│   └── comparisons/          Comparative spreadsheets used in the analysis
├── docs/                     Supporting manuscript notes and documentation
├── experiments/
│   ├── GAMSPy/               GAMSPy/CPLEX models and results
│   └── GRASP/                GRASP/ILS implementations and results
└── legacy/
    └── delphi/               Historical Delphi implementation
```

## Experiment Families

- `experiments/GAMSPy`: generated Python/GAMSPy models for the `Real`, `2X`, `3X`, `4X`, and `5X` instance sets, plus CPLEX output summaries.
- `experiments/GRASP`: Python implementations and output folders for GRASP and ILS variants.
- `data/comparisons`: spreadsheet comparisons among CPLEX, GRASP, ILS, and MIP results.
- `legacy/delphi`: original Delphi source kept as historical reference.

## Running the GAMSPy Experiments

Install the required Python packages and GAMSPy solver support:

```bash
pip install gamspy pandas
gamspy install solver CPLEX
```

Run from the repository root:

```bash
python experiments/GAMSPy/run_all.py
python experiments/GAMSPy/run_all.py Real
python experiments/GAMSPy/run_all.py 2X 3X
```

## Running the GRASP/ILS Experiments

Run from the repository root:

```bash
python experiments/GRASP/run_grasp_all.py
python experiments/GRASP/run_all_ils.py
```

## Curation Notes

This repository is a curated copy of `D:\Projects\Treibacher`.

The following generated or transient files were intentionally not copied:

- Python bytecode and `__pycache__` folders
- Office lock files such as `.~lock*`

The original experiment and result folder layout was otherwise preserved under `experiments/` to reduce the risk of breaking relative paths used by the scripts.
