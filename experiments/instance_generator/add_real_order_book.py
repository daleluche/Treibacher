"""Build the original real order-book PSP instance from the recovered GAMS demand table."""
from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "experiments" / "GAMSPy" / "S" / "S_1.py"
TARGET = ROOT / "experiments" / "GAMSPy" / "S" / "REAL_1.py"

EXPECTED_TOTAL = 279400.0
EXPECTED_DEMAND_PRODUCTS = 36
EXPECTED_DEMAND_RECORDS = 126
EXPECTED_J = 159
EXPECTED_A_RECORDS_IN_SOURCE = 1014

DEMAND_BLOCK_1 = {
    "EK8A_24": [0, 1000, 250, 0, 0, 0, 0, 0, 0],
    "EK8A_30": [0, 0, 250, 0, 0, 0, 0, 0, 0],
    "EK8A_36": [0, 1000, 750, 0, 0, 0, 0, 0, 0],
    "EK8A_46": [0, 1000, 500, 1000, 0, 0, 0, 0, 1500],
    "EK8A_54": [0, 0, 1000, 0, 0, 0, 0, 0, 0],
    "EK8A_60": [0, 1000, 0, 500, 0, 0, 0, 0, 2000],
    "EK8A_80": [0, 1000, 500, 1000, 0, 0, 0, 0, 1500],
    "EK8A_100": [0, 0, 750, 0, 1000, 700, 0, 0, 0],
    "EK8A_120": [0, 500, 500, 0, 250, 0, 0, 0, 500],
    "EK8A_150": [0, 0, 500, 0, 500, 0, 500, 0, 500],
    "EK8A_FFF": [0, 250, 0, 0, 0, 0, 0, 750, 1000],
    "EK8R_10_20": [400, 0, 0, 0, 0, 0, 0, 0, 0],
    "EK8R_20_40": [1650, 0, 0, 0, 0, 0, 0, 0, 0],
    "EK8R_40_F": [0, 0, 0, 0, 0, 4000, 0, 0, 0],
    "EK8R_3_5_7": [0, 1000, 0, 0, 0, 0, 0, 0, 0],
    "EK8R_4_10": [0, 0, 0, 0, 0, 0, 4000, 4000, 0],
    "EK8R_6_10": [0, 3000, 1000, 0, 0, 0, 0, 0, 0],
    "EK8R_70_F": [0, 3000, 3000, 1000, 0, 0, 0, 0, 0],
    "EK8R_08_20": [0, 0, 0, 2000, 0, 0, 0, 0, 0],
    "EK8R_10_36": [0, 0, 0, 0, 0, 0, 2000, 0, 0],
    "EK8R_12_16": [0, 0, 0, 5000, 4000, 3000, 0, 0, 0],
    "EK8R_16_F": [0, 0, 0, 0, 8000, 0, 0, 0, 0],
    "EK8R_18_F": [0, 0, 0, 10000, 0, 0, 0, 0, 0],
    "EK8RM_05_16_4": [0, 0, 0, 0, 0, 0, 3000, 3000, 1500],
    "EK8RM_6_8": [0, 0, 0, 0, 0, 0, 0, 0, 3000],
    "EK8RM_8_12": [0, 0, 0, 0, 0, 0, 0, 0, 3000],
    "EK8RM_12_16": [0, 0, 0, 0, 0, 0, 0, 5000, 0],
    "EK8RM_12_30": [0, 0, 0, 0, 0, 0, 4500, 0, 12000],
    "EK8RM_30_50": [0, 0, 0, 0, 0, 0, 3000, 4500, 0],
    "EK8RM_50_F": [0, 0, 0, 0, 0, 0, 3000, 0, 0],
    "EK8RM_28_F": [0, 0, 0, 0, 0, 0, 0, 0, 7500],
}

DEMAND_BLOCK_2 = {
    "EK8A_16": [0, 0, 250, 0, 0, 0, 0, 0, 0, 0],
    "EK8A_24": [500, 0, 0, 0, 0, 0, 0, 0, 250, 0],
    "EK8A_30": [0, 0, 0, 0, 0, 0, 0, 0, 1000, 0],
    "EK8A_36": [0, 0, 1000, 1000, 0, 0, 0, 0, 0, 500],
    "EK8A_46": [0, 0, 1000, 1000, 0, 0, 0, 0, 0, 3500],
    "EK8A_54": [0, 0, 0, 0, 0, 0, 0, 0, 0, 1000],
    "EK8A_60": [0, 1000, 1000, 1000, 0, 0, 1000, 0, 0, 3050],
    "EK8A_80": [0, 1000, 1000, 1000, 1000, 0, 0, 0, 0, 2000],
    "EK8A_100": [0, 0, 1000, 0, 0, 0, 0, 0, 0, 0],
    "EK8A_120": [0, 500, 0, 0, 500, 0, 0, 850, 0, 1000],
    "EK8A_150": [0, 500, 0, 500, 0, 500, 500, 0, 0, 500],
    "EK8A_FFF": [0, 0, 0, 0, 0, 0, 1000, 0, 0, 0],
    "EK8R_10_20": [0, 0, 0, 0, 500, 0, 0, 0, 0, 0],
    "EK8R_20_40": [0, 0, 0, 0, 1500, 0, 0, 0, 0, 0],
    "EK8R_4_10": [0, 0, 1000, 0, 0, 0, 0, 0, 0, 0],
    "EK8R_08_20": [0, 0, 1000, 0, 0, 0, 0, 0, 0, 0],
    "EK8R_18_F": [0, 0, 0, 0, 0, 0, 3000, 0, 0, 0],
    "EK8RM_4_6": [0, 0, 0, 6000, 0, 0, 0, 0, 0, 0],
    "EK8RM_6_8": [1500, 3000, 0, 0, 0, 0, 0, 0, 0, 0],
    "EK8RM_8_12": [3000, 3000, 0, 0, 0, 0, 3000, 3000, 3000, 6000],
    "EK8RM_8_20": [0, 0, 5000, 5000, 5000, 0, 0, 0, 0, 0],
    "EK8RM_12_30": [0, 9000, 0, 0, 0, 0, 3000, 0, 0, 0],
    "EK8RM_18_30": [3000, 0, 0, 0, 0, 0, 3000, 0, 0, 0],
    "EK8RM_01_4_4": [3000, 3000, 3000, 0, 0, 0, 0, 0, 0, 0],
    "EK8RM_30_50": [3000, 4500, 4500, 4500, 2000, 0, 4500, 3000, 1500, 0],
    "EK8RM_50_F": [0, 0, 0, 0, 0, 3000, 0, 0, 0, 0],
}


def extract_literal(source: str, name: str):
    """Extract a top-level literal assignment from a GAMSPy instance script."""
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise ValueError(f"Could not extract {name} from {SOURCE}")


def demand_records(products: list[str]) -> list[list[object]]:
    """Return nonzero demand records in product and period order."""
    values = {product: [0.0] * 19 for product in products}
    for product, amounts in DEMAND_BLOCK_1.items():
        values[product][:9] = [float(value) for value in amounts]
    for product, amounts in DEMAND_BLOCK_2.items():
        values[product][9:] = [float(value) for value in amounts]
    return [
        [product, str(period), float(value)]
        for product in products
        for period, value in enumerate(values[product], start=1)
        if value > 0.0
    ]


def totals_by_product(records: list[list[object]]) -> dict[str, float]:
    """Aggregate demand records by product."""
    totals: dict[str, float] = defaultdict(float)
    for product, _, value in records:
        totals[str(product)] += float(value)
    return dict(totals)


def render_records(records: list[list[object]]) -> str:
    """Render records as Python source with deterministic formatting."""
    lines = ["D_RECORDS = ["]
    for product, period, value in records:
        value_text = str(int(value)) + ".0" if float(value).is_integer() else repr(float(value))
        lines.append(f"    [{product!r}, {period!r}, {value_text}],")
    lines.append("]")
    return "\n".join(lines)


def replace_assignment(source: str, name: str, replacement: str) -> str:
    """Replace a top-level list assignment in source text."""
    pattern = rf"{name}\s*=\s*\[.*?\]\n\n"
    new_text, count = re.subn(pattern, replacement + "\n\n", source, count=1, flags=re.DOTALL)
    if count != 1:
        raise ValueError(f"Could not replace {name}")
    return new_text


def main() -> int:
    """Build REAL_1.py and validate the recovered demand table."""
    source = SOURCE.read_text(encoding="utf-8")
    products = extract_literal(source, "PRODUCTS")
    a_records = extract_literal(source, "A_RECORDS")
    s1_d_records = extract_literal(source, "D_RECORDS")
    real_d_records = demand_records(products)

    if "NUM_PROCESSES = 159" not in source:
        raise SystemExit("Validation failed: S_1 NUM_PROCESSES is not 159")
    if len(a_records) != EXPECTED_A_RECORDS_IN_SOURCE:
        raise SystemExit(
            f"Validation failed: S_1 A_RECORDS has {len(a_records)} records, "
            f"expected {EXPECTED_A_RECORDS_IN_SOURCE}"
        )
    if sum(value for _, _, value in real_d_records) != EXPECTED_TOTAL:
        raise SystemExit("Validation failed: REAL_1 total demand is not 279400.0")
    if totals_by_product(real_d_records) != totals_by_product(s1_d_records):
        raise SystemExit("Validation failed: REAL_1 product totals differ from S_1")
    if len(totals_by_product(real_d_records)) != EXPECTED_DEMAND_PRODUCTS:
        raise SystemExit("Validation failed: REAL_1 does not have 36 products with demand")
    if len(real_d_records) != EXPECTED_DEMAND_RECORDS:
        raise SystemExit("Validation failed: REAL_1 does not have 126 nonzero demand records")

    text = source
    text = text.replace("GAMSPy - S_1", "GAMSPy - REAL_1")
    text = text.replace("Gerado automaticamente a partir de: S_1.gms", "Gerado automaticamente a partir da carteira real recuperada")
    text = text.replace("INSTANCE    = 'S_1'", "INSTANCE    = 'REAL_1'")
    text = text.replace("SOURCE_GMS  = 'S_1.gms'", "SOURCE_GMS  = 'REAL_1.gms'")
    text = replace_assignment(text, "D_RECORDS", render_records(real_d_records))
    TARGET.write_text(text, encoding="utf-8")

    print(f"Wrote {TARGET}")
    print(f"J = {EXPECTED_J}")
    print(f"A_RECORDS = {len(a_records)}")
    print(f"Demand total = {sum(value for _, _, value in real_d_records):.1f}")
    print(f"Demand products = {len(totals_by_product(real_d_records))}")
    print(f"Demand records = {len(real_d_records)}")
    print("Product totals match S_1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
