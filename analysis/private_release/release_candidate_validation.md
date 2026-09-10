# Validated Release Candidate Report

R3 base SHA: ce7fa16875fb76659ff6edce60b79a5740ded156

## Candidate

The builder creates `release/dist/` and
`release/psp_electrofused_benchmark_v1.zip` as a validated release candidate.
The release directory is derived output and is not versioned. Source
documentation lives in `analysis/release_spec/README.template.md`.

## Identifier Coding

Product identifiers are coded from private labels to `P01`--`P50` in staging
copies only. The private reverse map is versioned in
`analysis/private_release/product_code_map.csv` and is excluded from the public
package. The invariance report records 1,554 validated staged files.

## Content Scan

The built distribution was scanned for private product prefixes, excluded real
order-book scripts and result folders, private mapping files, local absolute
paths, and private verification scripts. No occurrence was found in the
validated candidate.

## Self-Sufficiency

The ZIP was unpacked in an empty temporary directory and checked using only
package-local files:

```text
python code/reproduce_release.py
python code/verify_release.py
```

The first command regenerated the compact public analysis tables, and the
second validated checksums, inventory, and selected public table dimensions.

## Reproducibility Criterion

ZIP entries are written with deterministic metadata and compression settings.
The decisive reproducibility criterion is the SHA-256 content manifest in
`checksums.sha256`, validated by `code/verify_release.py`.

## Inventory

The candidate contains 1,635 files and is checked against
`analysis/release_spec/expected_inventory.txt`. Public analysis outputs are
copied only from `analysis/release_spec/public_analysis_outputs.txt`.
