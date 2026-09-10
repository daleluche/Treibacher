# PSP Electrofused-Grains Benchmark, Validated Release Candidate

This directory is a validated release candidate for the computational study of
the Process Selection Problem in electrofused grains. It is not a public
deposit, does not contain a DOI, and is not the final data-availability
statement.

## Contents

The candidate contains 60 derived benchmark instances with coded product
identifiers, selected feasible solutions, dual bounds, incumbent trajectories,
per-window logs, public analysis outputs used to build tables and figures, and
the controlled `gamma=0` results used to isolate the inventory penalty effect.

The plant's real order book, scripts that reconstruct it, the reversible product
mapping, private audit signatures, and private result folders are excluded.

## Identifier Coding

Product identifiers are coded from the private labels to neutral codes `P01` to
`P50`. The coding is deterministic and reversible inside the private repository,
but the reverse map and salt are not included here. This is identifier coding,
not a guarantee of anonymity.

## Reproduction Modes

Analysis reproduction does not require CPLEX. From an unpacked package, run:

```bash
python code/reproduce_release.py
python code/verify_release.py
```

Reexecution of the solvers is separate and requires GAMSPy plus a licensed CPLEX
installation. The solver-facing scripts are included for inspection and reuse,
but the packaged analysis can be checked without a solver license.

## Reproducibility Criterion

The archive is built with deterministic ZIP metadata, but the primary
reproducibility criterion is the SHA-256 content manifest in
`checksums.sha256`. `verify_release.py` validates file contents against that
manifest and checks the declared inventory.

## Inventory

`MANIFEST.expected_inventory.txt` declares the expected file list and
`MANIFEST.public_analysis_outputs.txt` declares the analysis-output allowlist.
The builder fails if the generated distribution contains files outside the
versioned inventory or omits expected files.
