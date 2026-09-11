# R4.2 Pre-Edit Release Audit

Starting commit: `055b17156234830eab2da348408ce30c3a6a7ac5`

The audit below was run against the R4.1 public release candidate before any
R4.2 code changes. It records operational defects only; no private matrices,
labels, or structural signatures are reproduced here.

## Window Log Metadata

Command summary: inspect `release/psp_electrofused_benchmark_v1.zip`, decode all
JSON files, and compare each declared `window_log_path` against ZIP entries.

Observed counts:

- JSON files in ZIP: 2,134
- JSONs with non-null `window_log_path`: 174
- JSONs with `window_log_included=true`: 174
- Declared paths that resolve to an existing ZIP entry: 0
- Window-log files present in ZIP: 24
- Declared references matchable by basename to an included log: 24
- Declared references with no included basename match: 150
- Ambiguous basename matches among included logs: 0

Each included log basename was referenced by exactly one JSON in the current
candidate. The defect is therefore broken path publication plus incorrect
`window_log_included=true` on records whose logs were not packaged.

## Synthetic Fixture Scope

Command summary: scan ZIP file names and contents for `Synthetic` and
`synthetic_tiny`.

Observed files containing the fixture:

- `results/experiments/matheuristics/results_pilot/synthetic_tiny_rf_fo_seed1.json`
- `analysis_output/master_runs.csv`
- `analysis_output/master_instances.csv`
- `analysis_output/bks_counterfactual_without_mip10800.csv`
- `MANIFEST.expected_inventory.txt`
- `checksums.sha256`

The fixture therefore reaches both raw results and public analysis outputs.

## Structural Audit Weaknesses

Command summary: run the current structural audit and then evaluate the current
in-memory rule checker against a product-row permutation of the protected
signature.

Observed facts:

- Current public audit result: passed
- Representations examined by the current audit: 60 Python scripts
- JSON instance representations examined by the current audit: 0
- A product-row permutation of the protected signature was not detected by the
  current rule checker.

This demonstrates two R4.2 defects without printing any protected signature:
the JSON representation is outside the audited surface, and the comparison is
order-dependent.

## Unsupported Table Builder

Command summary: unpack the ZIP into a temporary directory and execute
`python code/analysis/make_paper_tables.py`.

Observed result: exit code 1. The script fails inside the unpacked package while
calling analysis code that expects the private repository layout, producing
`KeyError: 'Z_gamma0'`. This confirms that the distributed script is not a
self-sufficient public reproduction entry point and should not be included in
the release candidate.

## Lexical Audit Erratum

The R4.1 pre-edit report recorded zero public result filenames containing the
exact token `Ale_1`. That value was incorrect. A later audit found 29 such
filename occurrences, mostly in names such as `Ale_1_run...`. The cause was an
overly narrow token rule that failed to treat `_`-delimited run suffixes as
separators while still needing to avoid false positives on `Ale_10`.

The corrected lexical rule is to detect `Ale_1` when it is not part of a larger
digit sequence, including path and underscore-delimited contexts, while
explicitly not matching `Ale_10`.
