"""Generate IncT PSP instances by extending the demand horizon."""
from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

if __package__ in (None, ""):
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))

from experiments.matheuristics.psp_instance import PSPInstance, load_instance

ROOT = Path(__file__).resolve().parents[2]
GAMSPY_DIR = ROOT / "experiments" / "GAMSPy"
REAL_DIR = GAMSPY_DIR / "Real"
DEFAULT_BASES = ("Ale_2", "Ale_3", "Ale_4", "Ale_5", "Ale_6")
VALIDATION_BASES = tuple(f"Ale_{idx}" for idx in range(2, 11))
DEFAULT_PROVENANCE_SEED = 20260706


@dataclass(frozen=True)
class GeneratedInstance:
    """Metadata for one generated IncT instance."""

    dataset: str
    instance: str
    base_instance: str
    factor: int
    provenance_seed: int
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


def base_suffix(base_name: str) -> int:
    """Return the numeric suffix from an Ale_j instance name."""
    return int(base_name.rsplit("_", 1)[1])


def inct_instance_name(factor: int, suffix: int) -> str:
    """Return the historical IncT instance name for a factor and Ale suffix."""
    if factor == 2:
        return f"IncT2X_{suffix}"
    return f"IncT{factor}x_{suffix}"


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


def render_instance(template_path: Path, dataset: str, instance: str, factor: int) -> str:
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
    provenance_seed: int,
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
    for base_name in selected_bases:
        suffix = base_suffix(base_name)
        instance = inct_instance_name(factor, suffix)
        template_path = REAL_DIR / f"{base_name}.py"
        text = render_instance(template_path, dataset=dataset, instance=instance, factor=factor)
        output_path = output_dir / f"{instance}.py"
        if not dry_run:
            output_path.write_text(text, encoding="utf-8")
        generated.append(
            GeneratedInstance(
                dataset=dataset,
                instance=instance,
                base_instance=base_name,
                factor=factor,
                provenance_seed=provenance_seed,
                path=output_path,
            )
        )
    return generated


def normalized_records(text: str, varname: str) -> list[tuple[str, str, float]]:
    """Return normalized literal records for exact comparisons."""
    _, _, literal = extract_list_literal(text, varname)
    return [(str(first), str(second), float(value)) for first, second, value in ast.literal_eval(literal)]


def scalar_int(text: str, varname: str) -> int:
    """Return an integer scalar assignment from generated instance text."""
    match = re.search(rf"^{re.escape(varname)}\s*=\s*(\d+)", text, flags=re.MULTILINE)
    if not match:
        raise ValueError(f"{varname} assignment not found.")
    return int(match.group(1))


def products_literal(text: str) -> list[str]:
    """Return the PRODUCTS list from generated instance text."""
    _, _, literal = extract_list_literal(text, "PRODUCTS")
    return [str(item) for item in ast.literal_eval(literal)]


def validate_exact_existing_families() -> dict[str, object]:
    """Validate exact regeneration of IncT2X--IncT5x for Ale_2..Ale_10."""
    temp_root = ROOT / "experiments" / "instance_generator" / "_tmp_validation"
    if temp_root.exists():
        for path in sorted(temp_root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()

    failures: list[dict[str, str]] = []
    checked = 0
    for factor in (2, 3, 4, 5):
        dataset = f"{factor}X"
        for base_name in VALIDATION_BASES:
            suffix = base_suffix(base_name)
            instance = inct_instance_name(factor, suffix)
            existing_path = GAMSPY_DIR / dataset / f"{instance}.py"
            generated_text = render_instance(
                REAL_DIR / f"{base_name}.py",
                dataset=dataset,
                instance=instance,
                factor=factor,
            )
            existing_text = existing_path.read_text(encoding="utf-8")
            checked += 1
            checks = {
                "NUM_PERIODS": scalar_int(generated_text, "NUM_PERIODS") == scalar_int(existing_text, "NUM_PERIODS"),
                "PRODUCTS": products_literal(generated_text) == products_literal(existing_text),
                "A_RECORDS": normalized_records(generated_text, "A_RECORDS")
                == normalized_records(existing_text, "A_RECORDS"),
                "D_RECORDS": normalized_records(generated_text, "D_RECORDS")
                == normalized_records(existing_text, "D_RECORDS"),
            }
            for field, passed in checks.items():
                if not passed:
                    failures.append({"dataset": dataset, "instance": instance, "field": field})

    for path in sorted(temp_root.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    passed = checked - len({(item["dataset"], item["instance"]) for item in failures})
    return {
        "scope": "IncT2X--IncT5x, Ale_2--Ale_10 only",
        "excluded": "family suffix _1 is legacy and has an external thesis base not present as Ale_1",
        "checked_instances": checked,
        "passed_instances": passed,
        "failed_instances": checked - passed,
        "failures": failures,
    }


def write_manifest(generated: list[GeneratedInstance], validation: dict[str, object], provenance_seed: int) -> Path:
    """Write generation metadata for the created 8X/10X sets."""
    manifest_path = ROOT / "experiments" / "instance_generator" / "generation_manifest.json"
    payload = {
        "provenance_seed": provenance_seed,
        "deterministic": True,
        "randomness_used": False,
        "base_instances": list(DEFAULT_BASES),
        "generated": [
            {
                "dataset": item.dataset,
                "instance": item.instance,
                "base_instance": item.base_instance,
                "factor": item.factor,
                "provenance_seed": item.provenance_seed,
                "path": str(item.path.relative_to(ROOT)),
            }
            for item in generated
        ],
        "exact_validation": validation,
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return manifest_path


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="Generate IncT horizon-extension PSP instances.")
    parser.add_argument("--seed", type=int, default=DEFAULT_PROVENANCE_SEED)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--factors", nargs="+", type=int, default=[8, 10])
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    """Run the IncT instance generator."""
    args = parse_args(argv)
    validation = validate_exact_existing_families()
    print("Exact validation against existing IncT2X--IncT5x instances")
    print(
        f"passed={validation['passed_instances']}/{validation['checked_instances']} "
        f"failed={validation['failed_instances']}"
    )
    if validation["failures"]:
        raise SystemExit(f"Exact validation failed: {validation['failures']}")
    if args.validate_only:
        return 0

    generated: list[GeneratedInstance] = []
    for factor in args.factors:
        generated.extend(
            generate_set(
                factor=factor,
                count=args.count,
                provenance_seed=args.seed,
                output_root=GAMSPY_DIR,
                dry_run=args.dry_run,
            )
        )
    if not args.dry_run:
        manifest_path = write_manifest(generated, validation, args.seed)
        print(f"Manifest written to {manifest_path}")
    for item in generated:
        action = "Would write" if args.dry_run else "Wrote"
        print(f"{action} {item.path} from {item.base_instance} provenance_seed={item.provenance_seed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
