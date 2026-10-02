"""Summarize the controlled gamma=0 excess-penalty experiment."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.families import atomic_write_text, write_table

OUT = ROOT / "analysis" / "output"
GAMSPY = ROOT / "experiments" / "GAMSPy"
GAMMA0 = GAMSPY / "variant_gamma0" / "results_gamma0"
DATASETS = ["2X", "3X", "4X", "5X"]
EPS = 1e-6


def load_json(path: Path) -> dict:
    """Load one result JSON."""
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def collect_rows() -> pd.DataFrame:
    """Collect gamma=0 and canonical gamma=0.001 objectives."""
    rows = []
    for dataset in DATASETS:
        for original_path in sorted((GAMSPY / dataset / "results_3horas").glob("*.json")):
            original = load_json(original_path)
            name = original["instance"]
            gamma0_path = GAMMA0 / f"{name}.json"
            if not gamma0_path.exists():
                raise FileNotFoundError(f"Missing gamma=0 result: {gamma0_path}")
            gamma0 = load_json(gamma0_path)
            z_gamma0 = gamma0.get("objective_value")
            z_original = original.get("objective_value")
            rows.append(
                {
                    "dataset": dataset,
                    "instance": name,
                    "T": original.get("num_periods"),
                    "Z_gamma0": z_gamma0,
                    "bound_gamma0": gamma0.get("best_bound"),
                    "gap_gamma0_pct": gamma0.get("gap_pct"),
                    "status_gamma0": str(gamma0.get("model_status", "")).replace("ModelStatus.", ""),
                    "time_gamma0_s": gamma0.get("wall_time_s"),
                    "Z_gamma0001": z_original,
                    "bound_gamma0001": original.get("best_bound"),
                    "gap_gamma0001_pct": original.get("gap_pct"),
                    "status_gamma0001": str(original.get("model_status", "")).replace("ModelStatus.", ""),
                    "time_gamma0001_s": original.get("wall_time_s"),
                    "delta_abs": z_original - z_gamma0 if z_gamma0 is not None and z_original is not None else None,
                    "delta_pct_vs_gamma0001": (
                        100.0 * (z_original - z_gamma0) / max(abs(z_original), 1.0)
                        if z_gamma0 is not None and z_original is not None
                        else None
                    ),
                }
            )
    return pd.DataFrame(rows)


def write_note(df: pd.DataFrame, by_set: pd.DataFrame) -> None:
    """Write a factual markdown note for the manuscript authors."""
    def to_markdown(frame: pd.DataFrame) -> str:
        """Render a small dataframe as a GitHub-style markdown table."""
        display = frame.copy()
        headers = list(display.columns)
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
        ]
        for _, row in display.iterrows():
            values = []
            for header in headers:
                value = row[header]
                if pd.isna(value):
                    values.append("")
                elif isinstance(value, float):
                    values.append(f"{value:.6f}")
                else:
                    values.append(str(value))
            lines.append("| " + " | ".join(values) + " |")
        return "\n".join(lines)

    lines = [
        "# Gamma=0 controlled excess-penalty check",
        "",
        "This note reports the controlled variant with objective `sum F`, cumulative demand inequalities, and no excess variable.",
        "It is descriptive only and does not interpret or revise Section 6.4.",
        "",
        "## By Dataset",
        "",
        to_markdown(by_set.round(6)),
        "",
        "## Sanity Check",
        "",
        f"`Z(gamma=0) <= Z(gamma=0.001)` holds for all {len(df)} instances.",
        "",
        "## Instance Table",
        "",
        to_markdown(
            df[
                [
                    "dataset",
                    "instance",
                    "T",
                    "Z_gamma0",
                    "Z_gamma0001",
                    "delta_abs",
                    "delta_pct_vs_gamma0001",
                    "status_gamma0",
                    "gap_gamma0_pct",
                ]
            ].round(6)
        ),
        "",
    ]
    atomic_write_text(OUT / "gamma_effect_note.md", "\n".join(lines))


def main() -> int:
    """Generate gamma effect CSVs and enforce the monotonicity sanity check."""
    OUT.mkdir(parents=True, exist_ok=True)
    df = collect_rows()
    violations = df[df["Z_gamma0"] > df["Z_gamma0001"] + EPS]
    if not violations.empty:
        print("FATAL: gamma=0 objective exceeds canonical gamma=0.001 objective.")
        print(violations[["dataset", "instance", "Z_gamma0", "Z_gamma0001"]].to_string(index=False))
        return 1

    by_set = (
        df.groupby("dataset", as_index=False)
        .agg(
            n=("instance", "count"),
            Z_gamma0_mean=("Z_gamma0", "mean"),
            Z_gamma0001_mean=("Z_gamma0001", "mean"),
            delta_abs_mean=("delta_abs", "mean"),
            delta_abs_median=("delta_abs", "median"),
            delta_pct_mean=("delta_pct_vs_gamma0001", "mean"),
            delta_pct_median=("delta_pct_vs_gamma0001", "median"),
            gamma0_gap_mean_pct=("gap_gamma0_pct", "mean"),
            gamma0001_gap_mean_pct=("gap_gamma0001_pct", "mean"),
            gamma0_time_mean_s=("time_gamma0_s", "mean"),
            gamma0001_time_mean_s=("time_gamma0001_s", "mean"),
        )
        .sort_values("dataset")
    )
    write_table(df, OUT / "gamma_effect.csv", ["dataset", "instance"])
    write_table(by_set, OUT / "gamma_effect_by_set.csv", ["dataset"])
    write_note(df, by_set)
    print(f"Wrote {OUT / 'gamma_effect.csv'}")
    print(f"Wrote {OUT / 'gamma_effect_by_set.csv'}")
    print(f"Wrote {OUT / 'gamma_effect_note.md'}")
    print("Gamma=0 sanity check passed for all instances.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
