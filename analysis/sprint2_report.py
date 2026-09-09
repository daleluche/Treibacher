"""Generate the Sprint 2 report with pre-registered hypothesis checks."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.families import atomic_write_text

OUTPUT_DIR = ROOT / "analysis" / "output"
REPORT_PATH = OUTPUT_DIR / "sprint2_report.md"
COMPARISON_TABLE = OUTPUT_DIR / "comparison_table.csv"

MATHEURISTICS_DIR = ROOT / "experiments" / "matheuristics"
TUNING_DIR = MATHEURISTICS_DIR / "results_tuning"
SHORT_DIR = MATHEURISTICS_DIR / "results_short_budget"
SCALE_DIR = MATHEURISTICS_DIR / "results_scale_8x10x"
PILOT_DIR = MATHEURISTICS_DIR / "results_pilot"


def fmt(value: object, digits: int = 3) -> str:
    """Format values for compact markdown tables."""
    if value is None:
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(number):
        return ""
    return f"{number:.{digits}f}"


def bool_text(value: bool) -> str:
    """Return a stable textual boolean."""
    return "true" if bool(value) else "false"


def markdown_table(rows: Iterable[dict], columns: list[str], formats: dict[str, int] | None = None) -> str:
    """Render dictionaries as a GitHub-flavored markdown table."""
    formats = formats or {}
    rows = list(rows)
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, sep]
    for row in rows:
        cells = []
        for column in columns:
            value = row.get(column)
            if isinstance(value, bool):
                cells.append(bool_text(value))
            elif isinstance(value, (float, int)) and not isinstance(value, bool):
                cells.append(fmt(value, formats.get(column, 3)))
            else:
                cells.append("" if value is None else str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def load_json(path: Path) -> dict:
    """Load one JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def matheuristic_json_paths() -> list[Path]:
    """Return all Sprint 1/2 matheuristic JSON result paths."""
    paths: list[Path] = []
    for directory in (PILOT_DIR, TUNING_DIR, SHORT_DIR, SCALE_DIR):
        if directory.exists():
            paths.extend(sorted(directory.glob("*.json")))
    return paths


def load_matheuristic_runs() -> pd.DataFrame:
    """Load all matheuristic JSON outputs into one dataframe."""
    rows = []
    for path in matheuristic_json_paths():
        data = load_json(path)
        params = data.get("params", {})
        rows.append(
            {
                "instance": data.get("instance"),
                "dataset": data.get("dataset"),
                "method": data.get("method"),
                "seed": data.get("seed"),
                "budget": float(params.get("budget", math.nan)),
                "Z_final": float(data.get("Z_final", math.nan)),
                "Z_rf": float(data.get("Z_rf", math.nan)),
                "source_file": str(path.relative_to(ROOT)),
            }
        )
    return pd.DataFrame(rows)


def tuning_table() -> pd.DataFrame:
    """Build the tuning table from tuning JSONs."""
    rows = []
    for path in sorted(TUNING_DIR.glob("*.json")):
        data = load_json(path)
        params = data.get("params", {})
        rows.append(
            {
                "instance": data["instance"],
                "omega": int(params["omega"]),
                "tl_fo": float(params["tl_fo"]),
                "step_fo": int(params["step_fo"]),
                "Z_final": float(data["Z_final"]),
                "fo_accepts": int(data.get("fo_accepts", 0)),
                "fo_sweeps_completed": int(data.get("fo_sweeps_completed", 0)),
            }
        )
    return pd.DataFrame(rows).sort_values(["instance", "omega", "tl_fo"])


def updated_bks_table(mat_runs: pd.DataFrame) -> pd.DataFrame:
    """Compute BKS after incorporating matheuristic outputs."""
    comparison = pd.read_csv(COMPARISON_TABLE)
    base = comparison[["dataset", "instance", "BKS"]].copy()
    base["BKS_source"] = "analysis_table"

    mat_best = (
        mat_runs.dropna(subset=["Z_final"])
        .sort_values(["instance", "Z_final"])
        .groupby("instance", as_index=False)
        .first()[["instance", "dataset", "method", "budget", "Z_final", "source_file"]]
        .rename(
            columns={
                "method": "matheuristic_method",
                "budget": "matheuristic_budget",
                "Z_final": "matheuristic_best",
                "source_file": "matheuristic_source",
            }
        )
    )
    merged = base.merge(mat_best, on=["dataset", "instance"], how="outer")
    merged["updated_BKS"] = merged.apply(
        lambda row: min(
            value
            for value in [row.get("BKS"), row.get("matheuristic_best")]
            if pd.notna(value)
        ),
        axis=1,
    )
    merged["updated_source"] = merged.apply(
        lambda row: row["matheuristic_method"]
        if pd.notna(row.get("matheuristic_best")) and row["matheuristic_best"] <= row["updated_BKS"] + 1e-9
        else row.get("BKS_source", "analysis_table"),
        axis=1,
    )
    relevant = merged[
        merged["instance"].astype(str).str.contains("IncT3x_|IncT4x_|IncT5x_|IncT8x_|IncT10x_", regex=True)
    ].copy()
    return relevant.sort_values(["dataset", "instance"])


def evaluate_h1(short_df: pd.DataFrame) -> tuple[bool, pd.DataFrame, pd.DataFrame]:
    """Evaluate H1 for 300s and 600s short-budget rows."""
    rows = []
    details = []
    for budget, group in short_df.groupby("budget_s"):
        wins = 0
        for _, row in group.iterrows():
            best_decomp = min(float(row["Z_rf_fo"]), float(row["Z_rf_mip"]))
            cplex = float(row["Z_mip"])
            win = best_decomp < cplex
            wins += int(win)
            details.append(
                {
                    "instance": row["instance"],
                    "budget_s": int(budget),
                    "best_decomp": best_decomp,
                    "cplex_mip": cplex,
                    "decomp_beats_mip": win,
                }
            )
        rows.append({"budget_s": int(budget), "wins": wins, "required": 4, "passed": wins >= 4})
    summary = pd.DataFrame(rows).sort_values("budget_s")
    return bool(summary["passed"].all()), summary, pd.DataFrame(details).sort_values(["budget_s", "instance"])


def evaluate_h2(scale_df: pd.DataFrame) -> tuple[bool, pd.DataFrame]:
    """Evaluate H2 on 10X @3600s rows."""
    rows = []
    for _, row in scale_df[scale_df["dataset"] == "10X"].iterrows():
        best_decomp = min(float(row["Z_rf_fo"]), float(row["Z_rf_mip"]))
        cplex = float(row["Z_mip"])
        rows.append(
            {
                "instance": row["instance"],
                "best_decomp": best_decomp,
                "cplex_mip": cplex,
                "decomp_beats_mip": best_decomp < cplex,
            }
        )
    details = pd.DataFrame(rows).sort_values("instance")
    passed = int(details["decomp_beats_mip"].sum()) >= 3
    return passed, details


def evaluate_h3(short_df: pd.DataFrame) -> tuple[bool, pd.DataFrame]:
    """Evaluate H3 for rf+fo versus truncated ILS v2 in all short-budget cells."""
    details = short_df.copy()
    details["rf_fo_beats_ils_v2"] = details["Z_rf_fo"].astype(float) < details[
        "Z_ils_v2_best_until_budget"
    ].astype(float)
    return bool(details["rf_fo_beats_ils_v2"].all()), details.sort_values(["budget_s", "instance"])


def evaluate_h4(mat_runs: pd.DataFrame) -> tuple[bool, pd.DataFrame, pd.DataFrame]:
    """Evaluate whether rf+fo ever worsens the matching RF reference."""
    rf_fo = mat_runs[mat_runs["method"] == "rf+fo"].copy()
    internal = rf_fo.copy()
    internal["comparison"] = "internal_Z_rf"
    internal["rf_reference"] = internal["Z_rf"]
    internal["passed"] = internal["Z_final"] <= internal["rf_reference"] + 1e-9

    rf = mat_runs[mat_runs["method"] == "rf"][["instance", "seed", "budget", "Z_final", "source_file"]].rename(
        columns={"Z_final": "standalone_rf_reference", "source_file": "standalone_rf_source"}
    )
    standalone = rf_fo.merge(rf, on=["instance", "seed", "budget"], how="inner")
    standalone["comparison"] = "standalone_rf_json"
    standalone["passed"] = standalone["Z_final"] <= standalone["standalone_rf_reference"] + 1e-9

    evidence = internal[
        ["instance", "dataset", "seed", "budget", "Z_final", "rf_reference", "comparison", "passed", "source_file"]
    ].rename(columns={"rf_reference": "Z_rf_reference"})
    standalone_evidence = standalone[
        [
            "instance",
            "dataset",
            "seed",
            "budget",
            "Z_final",
            "standalone_rf_reference",
            "comparison",
            "passed",
            "source_file",
        ]
    ].rename(columns={"standalone_rf_reference": "Z_rf_reference"})
    combined = pd.concat([evidence, standalone_evidence], ignore_index=True)
    violations = combined[~combined["passed"]].copy()
    return bool(combined["passed"].all()), combined.sort_values(["comparison", "dataset", "instance", "budget"]), violations


def write_report() -> None:
    """Write the Sprint 2 report markdown."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    mat_runs = load_matheuristic_runs()
    tuning_df = tuning_table()
    short_df = pd.read_csv(SHORT_DIR / "short_budget_summary.csv")
    scale_df = pd.read_csv(SCALE_DIR / "scale_8x10x_summary.csv")
    bks_df = updated_bks_table(mat_runs)

    h1_passed, h1_summary, h1_details = evaluate_h1(short_df)
    h2_passed, h2_details = evaluate_h2(scale_df)
    h3_passed, h3_details = evaluate_h3(short_df)
    h4_passed, h4_evidence, h4_violations = evaluate_h4(mat_runs)

    h_summary = [
        {
            "hypothesis": "H1",
            "criterion": "best(rf+fo, rf+mip) < cold MIP in >=4/6 instances at both 300s and 600s",
            "passed": h1_passed,
        },
        {
            "hypothesis": "H2",
            "criterion": "best(rf+fo, rf+mip) < cold MIP in >=3/5 10X instances at 3600s",
            "passed": h2_passed,
        },
        {
            "hypothesis": "H3",
            "criterion": "rf+fo < truncated ILS v2 in every short-budget cell",
            "passed": h3_passed,
        },
        {
            "hypothesis": "H4",
            "criterion": "no rf+fo run has Z_final greater than its RF reference",
            "passed": h4_passed,
        },
    ]

    lines = [
        "# Sprint 2 Report",
        "",
        "This report evaluates the pre-registered Sprint 2 hypotheses literally.",
        "It does not choose the paper narrative.",
        "",
        "## Hypothesis Verdicts",
        "",
        markdown_table(h_summary, ["hypothesis", "criterion", "passed"]),
        "",
        "## Updated BKS Accounting",
        "",
        "BKS is recomputed after adding matheuristic outputs from tuning, pilot, short-budget, and 8X/10X runs.",
        "",
        markdown_table(
            bks_df[
                [
                    "dataset",
                    "instance",
                    "BKS",
                    "matheuristic_best",
                    "matheuristic_method",
                    "matheuristic_budget",
                    "updated_BKS",
                    "updated_source",
                ]
            ].to_dict("records"),
            [
                "dataset",
                "instance",
                "BKS",
                "matheuristic_best",
                "matheuristic_method",
                "matheuristic_budget",
                "updated_BKS",
                "updated_source",
            ],
        ),
        "",
        "## Tuning Grid",
        "",
        markdown_table(
            tuning_df.to_dict("records"),
            ["instance", "omega", "tl_fo", "step_fo", "Z_final", "fo_accepts", "fo_sweeps_completed"],
        ),
        "",
        "## Short-Budget Experiment",
        "",
        markdown_table(
            short_df[
                [
                    "dataset",
                    "instance",
                    "budget_s",
                    "Z_rf_fo",
                    "Z_rf_mip",
                    "Z_mip",
                    "Z_ils_v2_best_until_budget",
                    "best_method",
                    "best_Z",
                ]
            ].to_dict("records"),
            [
                "dataset",
                "instance",
                "budget_s",
                "Z_rf_fo",
                "Z_rf_mip",
                "Z_mip",
                "Z_ils_v2_best_until_budget",
                "best_method",
                "best_Z",
            ],
        ),
        "",
        "## 8X/10X Scale Experiment",
        "",
        markdown_table(
            scale_df[["dataset", "instance", "Z_rf_fo", "Z_rf_mip", "Z_mip", "best_method", "best_Z"]].to_dict(
                "records"
            ),
            ["dataset", "instance", "Z_rf_fo", "Z_rf_mip", "Z_mip", "best_method", "best_Z"],
        ),
        "",
        "## H1 Evidence",
        "",
        markdown_table(h1_summary.to_dict("records"), ["budget_s", "wins", "required", "passed"]),
        "",
        markdown_table(
            h1_details.to_dict("records"),
            ["instance", "budget_s", "best_decomp", "cplex_mip", "decomp_beats_mip"],
        ),
        "",
        "## H2 Evidence",
        "",
        markdown_table(
            h2_details.to_dict("records"), ["instance", "best_decomp", "cplex_mip", "decomp_beats_mip"]
        ),
        "",
        "## H3 Evidence",
        "",
        markdown_table(
            h3_details[
                ["instance", "budget_s", "Z_rf_fo", "Z_ils_v2_best_until_budget", "rf_fo_beats_ils_v2"]
            ].to_dict("records"),
            ["instance", "budget_s", "Z_rf_fo", "Z_ils_v2_best_until_budget", "rf_fo_beats_ils_v2"],
        ),
        "",
        "## H4 Evidence",
        "",
        "RF reference includes the RF phase inside each rf+fo JSON and any standalone rf JSON with the same "
        "instance, seed, and budget.",
        "",
        f"Checked comparisons: {len(h4_evidence)}. Violations: {len(h4_violations)}.",
        "",
    ]
    if h4_violations.empty:
        lines.append("No H4 violations were found.")
    else:
        lines.append(
            markdown_table(
                h4_violations.to_dict("records"),
                [
                    "instance",
                    "dataset",
                    "seed",
                    "budget",
                    "Z_final",
                    "Z_rf_reference",
                    "comparison",
                    "source_file",
                ],
            )
        )
    lines.append("")

    atomic_write_text(REPORT_PATH, "\n".join(lines) + "\n")


def main() -> int:
    """Generate the report and print its path."""
    write_report()
    print(f"Sprint 2 report written to {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
