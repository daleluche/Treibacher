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
package. The current invariance report records 2,192 validated staged files,
including exact CPLEX JSONs, GRASP/ILS trajectories, matheuristic JSONs, runner
summary CSVs, and window-log parquet files needed for public reproduction.

## Content Scan

R4.1 corrected the R4 release candidate after a pre-edit audit found escaped
absolute Windows paths, residual repository/corporate identifiers, and
out-of-scope legacy rows. The corrected builder applies semantic public-scope
filtering, canonicalizes historical synthetic labels to S-family labels, removes
or relativizes local paths, and runs both textual and JSON-semantic scans before
creating the ZIP.

The final scan of the corrected candidate found zero public occurrences of the
forbidden product prefix, repository identifier, corporate model identifier,
excluded real-order-book labels, exact legacy index-1 token, local absolute
paths, private scripts, and private directories.

## Self-Sufficiency

The ZIP was unpacked in an empty temporary directory and checked using only
package-local files:

```text
python code/reproduce_release.py
python code/verify_release.py
```

The first command regenerated all outputs listed in
`MANIFEST.public_analysis_outputs.txt` from `instances/` and `results/`. It does
not read `analysis_output/` during calculation. The second command validated
checksums, inventory, public scope, private-content scans, raw source coverage,
full table-by-table equality between regenerated outputs and packaged
references, and the four sentinel counts: Q5 MIP@10800 wins `7/10` overall
(`4/5` in 8X and `3/5` in 10X), gamma shortage increases `7/10` in 2X, gamma
trade-off direction `31/40` in 2X--5X, and six strict BKS improvements.

## Reproducibility Criterion

ZIP entries are written with deterministic metadata and compression settings.
The decisive reproducibility criterion is the SHA-256 content manifest in
`checksums.sha256`, validated by `code/verify_release.py`.

## Inventory

The candidate contains 2,276 files and is checked against
`analysis/release_spec/expected_inventory.txt`. Public analysis outputs are
copied only from `analysis/release_spec/public_analysis_outputs.txt`.
