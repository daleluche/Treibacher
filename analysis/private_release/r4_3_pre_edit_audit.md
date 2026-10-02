# R4.3 Pre-Edit Release Audit

Starting commit: `4731cab73a2640de0488bc333ec4790b68d3cfc6`

This audit was run before R4.3 edits. It records operational defects in the
R4.2 public release candidate without reproducing private matrices, labels, or
structural signatures.

## Cross-Platform Byte Determinism

Independent Linux reconstruction of the R4.2 ZIP preserved the same 2,274 files
and the same scientific values but produced:

- size: 5,218,101 bytes
- SHA-256: `5075842b9a139c7cc1ca8359edb5bdb886566b05aa7654d01ce4477dd995afc5`

The Windows candidate had:

- size: 5,221,286 bytes
- SHA-256: `fdd9537ee72da1b28baaaabb21bcf4c683c97b6fa4ee08f1c2be64beca4ce818`

The reported byte diff was 37 files: 36 files differed only by CRLF versus LF,
and the 37th was `checksums.sha256` as a consequence. Source inspection found
public-output calls to `DataFrame.to_csv()` and `csv.writer()` without explicit
line terminators in the release builder, staging code, and public reproduction
entry points.

## Dataset Scope False Negative

In a temporary unpacked-package copy, the first row of
`analysis_output/sprint3_descriptive_by_scale.csv` was changed to
`dataset=UnknownSet`. The current `verify_public_scope()` accepted the modified
package. The cause is an analytic-schema shortcut that allows arbitrary dataset
values when columns such as `scope` or `comparison` are present.

## Instance Scope False Negative

In a temporary unpacked-package copy, the first row of
`analysis_output/master_instances.csv` was changed to
`dataset=S, instance=bad_instance`. The current `verify_public_scope()` accepted
the modified package. The cause is that the verifier checks family counts in
`instance_metadata.csv` but does not require every `(dataset, instance)` pair in
CSV, JSON, and Parquet artifacts to belong to the canonical 60-instance
registry.

## Public Objective Description

Command summary: count public instance scripts under
`release/dist/instances/gamspy_py/`.

Observed counts:

- Public instance scripts: 60
- Scripts with shortage-only objective wording: 60
- Scripts with weighted shortage-plus-excess wording: 0
- Scripts whose `EQ_OBJ` implementation contains the `0.001` excess coefficient:
  60

The code is correct; the public header comment is incomplete.

## Clean-Environment Instructions

`release/dist/code/requirements-analysis.txt` is present, but the README does
not instruct users to install it before reproduction. The verifier now reads
Parquet window logs, so a Python environment without `pyarrow` cannot run the
public verification path.

## Release-root hygiene targets before R4.3 cleanup

Observed obsolete generated items at `release/` root before applying the cleanup guard:

- `analysis_output/`
- `gamma0_variant/`
- `instances/`
- `solutions/`
- `trajectories/`
- `window_logs/`
- `checksums.sha256`
- `LICENSE`
- `README.md`

These are derived outputs from an obsolete flat release layout. The R4.3 builder now removes only these allowlisted items after confirming each resolved path is inside `ROOT/release/`. It preserves the current documented outputs `dist/`, `staging/`, and `psp_electrofused_benchmark_v1.zip`; any unexpected root item causes the build to fail instead of being deleted.
