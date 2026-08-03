"""Rebuild the homogeneous S benchmark set from archived GAMSPy instances."""
from __future__ import annotations

import ast
import re
from pathlib import Path

if __package__ in (None, ""):
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))

from experiments.instance_generator.generate_inct import extract_list_literal, replace_num_periods, replace_scalar

ROOT = Path(__file__).resolve().parents[2]
GAMSPY_DIR = ROOT / "experiments" / "GAMSPy"
SOURCE_2X_1 = GAMSPY_DIR / "2X" / "IncT2X_1.py"
LEGACY_REAL_DIR = GAMSPY_DIR / "Real"
S_DIR = GAMSPY_DIR / "S"
BASE_PERIODS = 19


def _replace_header(text: str, instance: str, periods: int) -> str:
    """Replace generated-script comments that identify the instance."""
    text = re.sub(r"GAMSPy - .+", f"GAMSPy - {instance}", text, count=1)
    text = re.sub(
        r"Gerado automaticamente a partir de: .+?\.gms",
        f"Gerado automaticamente a partir de: {instance}.gms",
        text,
        count=1,
    )
    text = re.sub(
        r"ao longo de \d+ periodos",
        f"ao longo de {periods} periodos",
        text,
        count=1,
    )
    return text


def _format_records(records: list[list[object]]) -> str:
    """Format literal records using the repository's generated-instance style."""
    lines = ["["]
    for product, period, value in records:
        lines.append(f"    [{product!r}, {str(period)!r}, {float(value):.10g}],")
    lines.append("]")
    return "\n".join(lines)


def _filter_first_block_demand(text: str) -> list[list[object]]:
    """Return demand records from the first 19-period block of IncT2X_1."""
    _, _, literal = extract_list_literal(text, "D_RECORDS")
    records = ast.literal_eval(literal)
    first = [[product, str(period), float(value)] for product, period, value in records if int(period) <= BASE_PERIODS]
    second = {
        (str(product), int(period) - BASE_PERIODS, float(value))
        for product, period, value in records
        if BASE_PERIODS < int(period) <= 2 * BASE_PERIODS
    }
    first_keyed = {(str(product), int(period), float(value)) for product, period, value in first}
    if first_keyed != second:
        raise ValueError("IncT2X_1 demand is not composed of two identical 19-period blocks.")
    return first


def rebuild_s1() -> Path:
    """Write S_1.py from the first block of IncT2X_1."""
    text = SOURCE_2X_1.read_text(encoding="utf-8")
    records = _filter_first_block_demand(text)
    text = _replace_header(text, "S_1", BASE_PERIODS)
    text = replace_scalar(text, "INSTANCE", repr("S_1"))
    text = replace_scalar(text, "DATASET", repr("S"))
    text = replace_scalar(text, "SOURCE_GMS", repr("S_1.gms"))
    text = replace_num_periods(text, BASE_PERIODS)
    start, end, _ = extract_list_literal(text, "D_RECORDS")
    text = text[:start] + _format_records(records) + text[end:]
    out_path = S_DIR / "S_1.py"
    out_path.write_text(text, encoding="utf-8")
    return out_path


def copy_s_family() -> list[Path]:
    """Copy Ale_2--Ale_10 into the S set as S_2--S_10 with renamed instances."""
    written = []
    for idx in range(2, 11):
        source = LEGACY_REAL_DIR / f"Ale_{idx}.py"
        text = source.read_text(encoding="utf-8")
        text = replace_scalar(text, "INSTANCE", repr(f"S_{idx}"))
        out_path = S_DIR / f"S_{idx}.py"
        out_path.write_text(text, encoding="utf-8")
        written.append(out_path)
    return written


def main() -> int:
    """Rebuild the S set files."""
    S_DIR.mkdir(parents=True, exist_ok=True)
    written = [rebuild_s1(), *copy_s_family()]
    for path in written:
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
