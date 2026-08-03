# IncT instance generator

This folder contains the deterministic generator used to extend the homogeneous
PSP set `S` into larger IncT horizons.

## Thesis rule

The IncT family follows the rule documented in the thesis, Section 6.2.2: the
demand of the original horizon is repeated exactly in each 19-period block.
For a factor `k`, an original demand record `(product, t, quantity)` is copied
to:

- `t`
- `t + 19`
- `t + 2 * 19`
- ...
- `t + (k - 1) * 19`

Therefore `T = 19 * k`, product totals are multiplied by `k`, and individual
positive demand quantities are not split or resampled.

## Independent confirmation

The implementation was independently checked against the existing generated
GAMSPy datasets. After reconstructing `S_1` from the first 19-period block of
`IncT2X_1`, regenerating `2X`, `3X`, `4X`, and `5X` for `j = 1..10`
reproduces all 40 available instances exactly:

- `NUM_PERIODS`
- `PRODUCTS`
- `A_RECORDS`
- `D_RECORDS`

The repository's legacy `Ale_1` file is not part of this homogeneous set:
its horizon and process matrix differ from the `S` family. It is retained in
the repository for provenance but is not used as an IncT base.

## Determinism

Generation is deterministic. The `provenance_seed` in
`generation_manifest.json` is retained only as run provenance for Sprint 2; no
random sampling is used by the generator.

## Commands

Validate exact regeneration of the existing families:

```powershell
python experiments\instance_generator\generate_inct.py --validate-only
```

Generate the Sprint 2 scale-up sets:

```powershell
python experiments\instance_generator\generate_inct.py
```

## Generated sets

The Sprint 2.5 generation uses these base instances:

- `S_2`
- `S_3`
- `S_4`
- `S_5`
- `S_6`

This preserves the existing convention `IncTkX_j <-> S_j`, so the generated
files are:

- `experiments/GAMSPy/8X/IncT8x_2.py` ... `IncT8x_6.py`
- `experiments/GAMSPy/10X/IncT10x_2.py` ... `IncT10x_6.py`

The metadata and exact validation report are stored in
`experiments/instance_generator/generation_manifest.json`.
