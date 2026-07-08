# IncT instance generator

This folder contains the deterministic generator used to extend the PSP real
instances into larger IncT horizons.

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
GAMSPy datasets. Regenerating `2X`, `3X`, `4X`, and `5X` for `j = 2..10`
reproduces all 36 available instances exactly:

- `NUM_PERIODS`
- `PRODUCTS`
- `A_RECORDS`
- `D_RECORDS`

The suffix `_1` family is excluded from this exact correspondence because it is
a legacy thesis instance with an external base that is not represented by the
repository's `Ale_1` file. This is why the exact validation scope is
`Ale_2..Ale_10`.

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

- `Ale_2`
- `Ale_3`
- `Ale_4`
- `Ale_5`
- `Ale_6`

This preserves the existing convention `IncTkX_j <-> Ale_j`, so the generated
files are:

- `experiments/GAMSPy/8X/IncT8x_2.py` ... `IncT8x_6.py`
- `experiments/GAMSPy/10X/IncT10x_2.py` ... `IncT10x_6.py`

The metadata and exact validation report are stored in
`experiments/instance_generator/generation_manifest.json`.
