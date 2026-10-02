"""Generate a Markdown report for the RF/FO pilot results."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from experiments.matheuristics.run_pilot import PILOT_INSTANCES, RESULTS_DIR, result_path

ROOT = Path(__file__).resolve().parents[2]
COMPARISON_TABLE = ROOT / "analysis" / "output" / "comparison_table.csv"
REPORT_PATH = RESULTS_DIR / "pilot_matheuristics_report.md"


def pct_gap(value: float | None, reference: float | None) -> float | None:
    """Return percent gap against a positive reference."""
    if value is None or reference is None or reference == 0:
        return None
    return 100.0 * (float(value) - float(reference)) / float(reference)


def load_json(path: Path) -> dict:
    """Load one JSON result or return an empty dict."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def first_warm_start_evidence(seed: int) -> tuple[str | None, list[str]]:
    """Return warm-start evidence from the first RF+FO result with log lines."""
    for _, instance, _ in PILOT_INSTANCES:
        data = load_json(result_path(instance, "rf+fo", seed))
        lines = data.get("warm_start_log_evidence_lines") or []
        if lines:
            return instance, lines
    return None, []


def markdown_table(frame: pd.DataFrame) -> str:
    """Render a small DataFrame as a GitHub-flavored Markdown table."""
    display = frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.3f}")
        else:
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else str(value))
    headers = list(display.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in headers) + " |")
    return "\n".join(lines)


def build_report(seed: int) -> str:
    """Build the Markdown report body."""
    refs = pd.read_csv(COMPARISON_TABLE).set_index("instance")
    rows = []
    wins_vs_cplex_3h = 0
    completed = 0

    for dataset, instance, _ in PILOT_INSTANCES:
        rf = load_json(result_path(instance, "rf", seed))
        rffo = load_json(result_path(instance, "rf+fo", seed))
        ref = refs.loc[instance]
        z_rffo = rffo.get("Z_final")
        cplex_3h = float(ref["cplex_Z"])
        if z_rffo is not None:
            completed += 1
            if float(z_rffo) < cplex_3h - 1e-6:
                wins_vs_cplex_3h += 1
        rows.append(
            {
                "Dataset": dataset,
                "Instance": instance,
                "RF": rf.get("Z_final"),
                "RF+FO": z_rffo,
                "CPLEX 1h": float(ref["cplex_Z_1h"]),
                "CPLEX 3h": cplex_3h,
                "ILS v2 best": float(ref["ils2_Z_best"]),
                "RF+FO gap vs CPLEX 3h (%)": pct_gap(z_rffo, cplex_3h),
                "FO accepts": rffo.get("fo_accepts"),
                "Warm start": rffo.get("warm_start_log_has_mipstart"),
                "Wall RF+FO (s)": rffo.get("wall_time_total"),
            }
        )

    table = pd.DataFrame(rows)
    verdict = "GO" if completed == len(PILOT_INSTANCES) and wins_vs_cplex_3h > 0 else "NO-GO"
    evidence_instance, evidence_lines = first_warm_start_evidence(seed)
    evidence_text = "\n".join(f"- `{line}`" for line in evidence_lines) if evidence_lines else "- Not found in captured logs."

    return "\n".join(
        [
            "# Pilot Matheuristics Report",
            "",
            f"Seed: `{seed}`",
            f"Verdict: **{verdict}**",
            "",
            "Decision rule used here: GO requires all 8 RF+FO runs to complete and at least one RF+FO incumbent to improve the CPLEX@3h primal. This is a pilot-screening rule, not a final paper conclusion.",
            "",
            "## Results",
            "",
            markdown_table(table),
            "",
            "## Warm Start Evidence",
            "",
            f"Source instance: `{evidence_instance}`" if evidence_instance else "Source instance: none",
            "",
            evidence_text,
            "",
            "## Notes",
            "",
            "- `RF` and `RF+FO` values are `Z_final` from `experiments/matheuristics/results_pilot`.",
            "- Reference values are read from `analysis/output/comparison_table.csv`.",
        ]
    )


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="Generate the RF/FO pilot report.")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=Path, default=REPORT_PATH)
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    """Write the pilot report."""
    args = parse_args(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(args.seed)
    args.out.write_text(report + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
