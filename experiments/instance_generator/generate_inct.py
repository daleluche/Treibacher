"""Generate IncT PSP instances by extending the demand horizon."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

if __package__ in (None, ""):
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))

from experiments.matheuristics.psp_instance import PSPInstance, load_instance

ROOT = Path(__file__).resolve().parents[2]
GAMSPY_DIR = ROOT / "experiments" / "GAMSPy"
REAL_DIR = GAMSPY_DIR / "Real"
DEFAULT_BASES = ("Ale_2", "Ale_3", "Ale_4", "Ale_5", "Ale_6")
DEFAULT_SEED = 20260706
VALIDATION_KEYS = (
    "total_demand",
    "nonzero_records",
    "nonzero_per_product_mean",
    "nonzero_per_product_std",
    "demand_per_product_mean",
    "demand_per_product_std",
    "demand_per_period_mean",
    "demand_per_period_std",
    "positive_quantity_mean",
    "positive_quantity_std",
)


@dataclass(frozen=True)
class GeneratedInstance:
    """Metadata for one generated IncT instance."""

    dataset: str
    instance: str
    base_instance: str
    factor: int
    seed: int
    path: Path


def extract_list_literal(text: str, varname: str) -> tuple[int, int, str]:
    """Return ``(start, end, literal_text)`` for a top-level list assignment."""
    match = re.search(rf"^{re.escape(varname)}\s*=\s*\[", text, flags=re.MULTILINE)
    if not match:
        raise ValueError(f"{varname} assignment not found.")
    start = text.find("[", match.start())
    depth = 0
    for pos in range(start, len(text)):
        if text[pos] == "[":
            depth += 1
        elif text[pos] == "]":
            depth -= 1
            if depth == 0:
                return start, pos + 1, text[start : pos + 1]
    raise ValueError(f"{varname} list does not terminate.")


def replace_scalar(text: str, varname: str, value: str) -> str:
    """Replace a simple scalar assignment preserving generated-script style."""
    return re.sub(rf"^{re.escape(varname)}\s*=.*$", f"{varname:<12}= {value}", text, flags=re.MULTILINE)


def replace_num_periods(text: str, periods: int) -> str:
    """Replace the NUM_PERIODS assignment and header period count."""
    text = re.sub(r"^NUM_PERIODS\s*=.*$", f"NUM_PERIODS   = {periods}", text, flags=re.MULTILINE)
    text = re.sub(r"ao longo de \d+ periodos", f"ao longo de {periods} periodos", text)
    return text


def demand_records_literal(records: list[list[object]]) -> str:
    """Format D_RECORDS as a stable Python list literal."""
    lines = ["["]
    for product, period, value in records:
        value_text = f"{float(value):.10g}"
        lines.append(f"    [{product!r}, {str(period)!r}, {value_text}],")
    lines.append("]")
    return "\n".join(lines)


def generate_demand_records(inst: PSPInstance, factor: int) -> list[list[object]]:
    """Extend real demand by repeating its period pattern in ``factor`` blocks.

    Reverse engineering of the existing IncT2X--IncT5x files shows that each
    positive real demand record is copied once per 19-period block, preserving
    both the product-period quantities and the period-load profile.
    """
    records: list[list[object]] = []
    for product_idx, product in enumerate(inst.products):
        for block in range(factor):
            offset = block * inst.T
            for period_idx, value in enumerate(inst.D[product_idx], start=1):
                if value > 0:
                    records.append([product, str(offset + period_idx), float(value)])
    records.sort(key=lambda row: (row[0], int(row[1]), float(row[2])))
    return records


def render_instance(template_path: Path, dataset: str, instance: str, factor: int, seed: int) -> str:
    """Render one generated GAMSPy instance script from a real-instance template."""
    template = template_path.read_text(encoding="utf-8")
    base = load_instance(template_path)
    records = generate_demand_records(base, factor=factor)

    text = template
    text = text.replace(f"GAMSPy - {base.name}", f"GAMSPy - {instance}", 1)
    text = text.replace(f"Gerado automaticamente a partir de: {base.name}.gms", f"Gerado automaticamente a partir de: {instance}.gms", 1)
    text = replace_scalar(text, "INSTANCE", repr(instance))
    text = replace_scalar(text, "DATASET", repr(dataset))
    text = replace_scalar(text, "SOURCE_GMS", repr(f"{instance}.gms"))
    text = replace_num_periods(text, base.T * factor)
    start, end, _ = extract_list_literal(text, "D_RECORDS")
    text = text[:start] + demand_records_literal(records) + text[end:]
    return text


def generate_set(
    factor: int,
    count: int,
    seed: int,
    output_root: Path,
    bases: Iterable[str] = DEFAULT_BASES,
    dry_run: bool = False,
) -> list[GeneratedInstance]:
    """Generate one IncT factor set and return written instance metadata."""
    dataset = f"{factor}X"
    output_dir = output_root / dataset
    selected_bases = list(bases)[:count]
    if len(selected_bases) != count:
        raise ValueError(f"Requested {count} instances but only {len(selected_bases)} bases were provided.")
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    generated = []
    for idx, base_name in enumerate(selected_bases, start=1):
        instance = f"IncT{factor}x_{idx}"
        instance_seed = seed + factor * 1000 + idx
        template_path = REAL_DIR / f"{base_name}.py"
        text = render_instance(template_path, dataset=dataset, instance=instance, factor=factor, seed=instance_seed)
        output_path = output_dir / f"{instance}.py"
        if not dry_run:
            output_path.write_text(text, encoding="utf-8")
        generated.append(
            GeneratedInstance(
                dataset=dataset,
                instance=instance,
                base_instance=base_name,
                factor=factor,
                seed=instance_seed,
                path=output_path,
            )
        )
    return generated


def instance_stats(paths: Iterable[Path]) -> dict[str, float]:
    """Compute aggregate demand statistics for a collection of instances."""
    per_instance = []
    for path in paths:
        inst = load_instance(path)
        demand = inst.D
        positive = demand[demand > 0]
        per_instance.append(
            {
                "total_demand": float(demand.sum()),
                "nonzero_records": float((demand > 0).sum()),
                "nonzero_per_product_mean": float((demand > 0).sum(axis=1).mean()),
                "nonzero_per_product_std": float((demand > 0).sum(axis=1).std(ddof=0)),
                "demand_per_product_mean": float(demand.sum(axis=1).mean()),
                "demand_per_product_std": float(demand.sum(axis=1).std(ddof=0)),
                "demand_per_period_mean": float(demand.sum(axis=0).mean()),
                "demand_per_period_std": float(demand.sum(axis=0).std(ddof=0)),
                "positive_quantity_mean": float(positive.mean()),
                "positive_quantity_std": float(positive.std(ddof=0)),
            }
        )
    if not per_instance:
        raise ValueError("No instances supplied for statistics.")
    return {key: float(np.mean([row[key] for row in per_instance])) for key in VALIDATION_KEYS}


def validate_against_existing_2x(seed: int, tolerance: float = 0.15) -> dict[str, dict[str, float | bool]]:
    """Generate a temporary 2X set and compare aggregate statistics to existing 2X."""
    temp_root = ROOT / "experiments" / "instance_generator" / "_tmp_validation"
    if temp_root.exists():
        for path in sorted(temp_root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
    generated = generate_set(2, count=5, seed=seed, output_root=temp_root, dry_run=False)
    synthetic_stats = instance_stats(item.path for item in generated)
    existing_stats = instance_stats(sorted((GAMSPY_DIR / "2X").glob("*.py")))
    report: dict[str, dict[str, float | bool]] = {}
    for key in VALIDATION_KEYS:
        existing = existing_stats[key]
        synthetic = synthetic_stats[key]
        rel_diff = 0.0 if existing == 0 else abs(synthetic - existing) / abs(existing)
        report[key] = {
            "existing": existing,
            "synthetic": synthetic,
            "relative_difference": rel_diff,
            "passed": bool(rel_diff <= tolerance),
        }
    for path in sorted(temp_root.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    return report


def write_manifest(generated: list[GeneratedInstance], validation: dict[str, dict[str, float | bool]], seed: int) -> Path:
    """Write generation metadata for the created 8X/10X sets."""
    manifest_path = ROOT / "experiments" / "instance_generator" / "generation_manifest.json"
    payload = {
        "seed": seed,
        "base_instances": list(DEFAULT_BASES),
        "generated": [
            {
                "dataset": item.dataset,
                "instance": item.instance,
                "base_instance": item.base_instance,
                "factor": item.factor,
                "seed": item.seed,
                "path": str(item.path.relative_to(ROOT)),
            }
            for item in generated
        ],
        "validation_2x": validation,
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return manifest_path


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="Generate IncT horizon-extension PSP instances.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--factors", nargs="+", type=int, default=[8, 10])
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    """Run the IncT instance generator."""
    args = parse_args(argv)
    validation = validate_against_existing_2x(seed=args.seed)
    failed = [key for key, row in validation.items() if not row["passed"]]
    print("2X validation against existing instances")
    for key, row in validation.items():
        print(
            f"{key}: existing={row['existing']:.6f} synthetic={row['synthetic']:.6f} "
            f"rel_diff={row['relative_difference']:.4f} passed={row['passed']}"
        )
    if failed:
        raise SystemExit(f"2X validation failed for: {', '.join(failed)}")
    if args.validate_only:
        return 0

    generated: list[GeneratedInstance] = []
    for factor in args.factors:
        generated.extend(
            generate_set(
                factor=factor,
                count=args.count,
                seed=args.seed,
                output_root=GAMSPY_DIR,
                dry_run=args.dry_run,
            )
        )
    if not args.dry_run:
        manifest_path = write_manifest(generated, validation, args.seed)
        print(f"Manifest written to {manifest_path}")
    for item in generated:
        action = "Would write" if args.dry_run else "Wrote"
        print(f"{action} {item.path} from {item.base_instance} seed={item.seed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
