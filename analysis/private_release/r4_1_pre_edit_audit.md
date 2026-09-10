# R4.1 Pre-Edit Audit

Base audited release commit: `09b830c53e787ee80dcd89856a0b1524b1be8db7`

R3 base SHA: `ce7fa16875fb76659ff6edce60b79a5740ded156`

The audit was run before editing R4.1 implementation files. It inspected the
current `release/dist` tree and `release/psp_electrofused_benchmark_v1.zip`
candidate produced by R4.

## Commands And Functions

- File inventory: Python script over `release/dist` with `Path.rglob("*")`.
- JSON absolute-path count: recursive JSON walk over every `*.json`, checking
  `window_log_path` against `^[A-Za-z]:[\\/]`.
- Text counts: UTF-8 read over text-like files for forbidden public strings.
- Exact `Ale_1` token: regular expression
  `(?<![A-Za-z0-9_])Ale_1(?![A-Za-z0-9_])`, so `Ale_10` is not counted.
- CSV row counts: semantic per-file scan of the three named CSVs.

## Recomputed Counts

| Check | Count |
|---|---:|
| files in current dist | 1,635 |
| ZIP entries | 1,635 |
| JSON files | 1,526 |
| JSON `window_log_path` fields with absolute Windows path | 177 |
| text occurrences of repository name | 180 |
| text occurrences of corporate model identifier | 1,680 |
| text occurrences of private product prefix | 0 |
| text occurrences of `REAL_1` | 0 |
| exact-token occurrences of `Ale_1` | 136 |
| public result filenames with exact-token `Ale_1` | 0 |
| `master_instances.csv` rows with exact-token `Ale_1` | 9 |
| `master_runs.csv` rows with exact-token `Ale_1` | 38 |
| `bks_counterfactual_without_mip10800.csv` rows with exact-token `Ale_1` | 1 |

## Interpretation

The candidate needs correction before any public deposit. The false negative in
R4 came from scanning only unescaped path text; JSON-escaped Windows paths were
not decoded semantically. The legacy `Ale_1` case is present in public analysis
tables and must be excluded by exact-token scope rules. Historical `Ale_2` to
`Ale_10` labels must remain in scope but be canonicalized to `S_2` to `S_10`.
