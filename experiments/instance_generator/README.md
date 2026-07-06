# IncT instance generator

This folder contains the reproducible generator used to extend the PSP real
instances into larger IncT horizons.

## Source interpretation

The thesis text referenced for Sections 6.2.1 and 6.2.2 was not available as a
clean structured source in this repository. The available
`docs/metaheuristicas.docx` is a methodological note about the metaheuristics,
not the original instance-generation section. Therefore, the implementation
uses reverse engineering against the existing `experiments/GAMSPy/2X`,
`3X`, `4X`, and `5X` datasets.

## Reverse-engineered decisions

The existing IncT instances show these invariants:

- `T = 19 * k` for the `kX` sets.
- Total demand per product is exactly multiplied by `k`.
- Positive demand quantities are preserved; the positive-quantity mean and
  standard deviation are stable across `2X` to `5X`.
- The period-load profile is preserved across blocks: for example,
  `IncT2X_2` is exactly `Ale_2` repeated in two consecutive 19-period blocks.

Given those facts, `generate_inct.py` extends each selected real instance by
copying every positive demand record once per block. A real demand at period
`t` becomes demands at `t`, `t + 19`, `t + 38`, and so on. This preserves the
minimum positive quantity rule implied by the real data because demand chunks
are not split into smaller quantities.

The script records a seed in the manifest for reproducibility of the generation
run. In the compatibility mode used here, the block-copy rule itself is
deterministic because it matches the existing IncT datasets better than uniform
random reassignment over the extended horizon.

## Validation

The command below builds a temporary synthetic 2X set from the same rule and
compares aggregate demand statistics against the existing 2X data:

```powershell
python experiments\instance_generator\generate_inct.py --validate-only
```

The validation checks total demand, nonzero demand records, demand per product,
demand per period, and positive-quantity statistics. The accepted tolerance is
15 percent per metric. With seed `20260706`, all checked metrics pass.

## Generated sets

The Sprint 2.5 generation uses:

- base instances: `Ale_2`, `Ale_3`, `Ale_4`, `Ale_5`, `Ale_6`
- seed recorded in the manifest: `20260706`
- generated factors: `8X` and `10X`

Output files are written under:

- `experiments/GAMSPy/8X/IncT8x_1.py` ... `IncT8x_5.py`
- `experiments/GAMSPy/10X/IncT10x_1.py` ... `IncT10x_5.py`

The metadata and validation report are stored in
`experiments/instance_generator/generation_manifest.json`.
