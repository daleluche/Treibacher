"""Strict equal-budget accounting for ILS v2 comparison values.

The ILS v2 JSON files contain complete improvement trajectories, but their
hard-stop runtime exceeds the declared 3600 second budget and the summary files
also include a cross-run path-relinking value.  This module reconstructs the
comparison value directly from the run JSON trajectories: within-run path
relinking before the cutoff remains eligible, while improvements after the
cutoff and cross-run path relinking are reported separately.

This partially reverts the accounting decision from commit 7b1e941: counting
the cross-run path-relinking solution is methodologically coherent for the
algorithm, but it violates the paper's equal-wall-time comparison protocol.
"""
from __future__ import annotations

import json
import math
import re
import sys
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.families import BENCHMARK_FAMILY_ORDER, REAL_ORDER_BOOK, atomic_write_text, write_table
from experiments.matheuristics.psp_instance import evaluate, load_instance

OUT = ROOT / "analysis" / "output"
DEFAULT_CUTOFF_S = 3600.0
EPS = 1e-6


@dataclass(frozen=True)
class IlsSource:
    """A collection of ILS v2 run and summary JSON files."""

    run_pattern: str
    summary_pattern: str


ILS_V2_SOURCES = [
    IlsSource("experiments/GRASP/results_ils_v2/*_run*.json", "experiments/GRASP/results_ils_v2/*_summary.json"),
    IlsSource(
        "experiments/matheuristics/results_production/s1/S_1_run*.json",
        "experiments/matheuristics/results_production/s1/S_1_summary.json",
    ),
    IlsSource(
        "experiments/matheuristics/results_production/real/REAL_1_run*.json",
        "experiments/matheuristics/results_production/real/REAL_1_summary.json",
    ),
]


def load_json(path: Path) -> dict:
    """Read a JSON file with UTF-8 encoding."""
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def canonical_instance(dataset: str | None, instance: str | None) -> tuple[str | None, str | None, str | None]:
    """Return the paper-facing dataset and instance name."""
    if instance is None:
        return dataset, instance, None
    if instance == "REAL_1":
        return REAL_ORDER_BOOK, instance, None
    if dataset == "Real" and instance.startswith("Ale_"):
        suffix = instance.rsplit("_", 1)[1]
        if suffix == "1":
            return dataset, instance, "Legacy Ale_1 is retained for provenance outside the benchmark."
        return "S", f"S_{suffix}", None
    if instance.startswith("S_"):
        return "S", instance, None
    return dataset, instance, None


def run_sort_key(path: Path) -> tuple[str, int]:
    """Return a stable run-file ordering key."""
    match = re.search(r"_run(\d+)\.json$", path.name)
    return (path.name, int(match.group(1)) if match else 0)


def summary_key(dataset: str | None, instance: str | None) -> tuple[str | None, str | None]:
    """Return the canonical key used to match summaries and runs."""
    ds, inst, _ = canonical_instance(dataset, instance)
    return ds, inst


def best_improvement_at_cutoff(improvements: Iterable[dict], cutoff_s: float) -> tuple[float, float, str | None]:
    """Return the best trajectory value found no later than ``cutoff_s``."""
    best_z = math.inf
    best_time = math.nan
    best_tag: str | None = None
    for item in improvements:
        time_s = item.get("time_s")
        value = item.get("Z")
        if time_s is None or value is None:
            continue
        if float(time_s) <= cutoff_s + EPS and float(value) < best_z:
            best_z = float(value)
            best_time = float(time_s)
            best_tag = item.get("tag")
    if math.isinf(best_z):
        return math.nan, math.nan, None
    return best_z, best_time, best_tag


def instance_path(dataset: str, instance: str) -> Path | None:
    """Resolve the GAMSPy source file for a canonical instance."""
    if dataset == REAL_ORDER_BOOK and instance == "REAL_1":
        return ROOT / "experiments" / "GAMSPy" / "S" / "REAL_1.py"
    if dataset == "Real" and instance == "Ale_1":
        return ROOT / "experiments" / "GAMSPy" / "Real" / "Ale_1.py"
    if dataset == "S" and instance.startswith("S_"):
        return ROOT / "experiments" / "GAMSPy" / "S" / f"{instance}.py"
    candidate = ROOT / "experiments" / "GAMSPy" / dataset / f"{instance}.py"
    return candidate if candidate.exists() else None


def validate_schedule(dataset: str, instance: str, schedule: list[int] | None, expected_z: float) -> bool:
    """Return whether a stored schedule evaluates to ``expected_z``."""
    if schedule is None:
        return False
    path = instance_path(dataset, instance)
    if path is None or not path.exists():
        return False
    try:
        inst = load_instance(path)
        z_value, _, _ = evaluate(schedule, inst)
    except Exception:
        return False
    return abs(float(z_value) - float(expected_z)) <= 1e-2


def collect_summary_values(root: Path = ROOT) -> dict[tuple[str | None, str | None], dict]:
    """Collect ILS v2 summary values, including cross-run path relinking."""
    summaries: dict[tuple[str | None, str | None], dict] = {}
    for source in ILS_V2_SOURCES:
        for path in sorted(root.glob(source.summary_pattern)):
            data = load_json(path)
            key = summary_key(data.get("dataset"), data.get("instance"))
            summaries[key] = {
                "Z_best_with_cross_pr": data.get("Z_best"),
                "cross_run_pr_z": data.get("cross_run_pr_z"),
                "summary_time_limit_s": data.get("time_limit_s"),
                "summary_source_path": str(path.relative_to(root)),
                "summary_T": data.get("T"),
                "summary_J": data.get("J"),
                "summary_I": data.get("I"),
            }
    return summaries


def collect_run_audit(cutoff_s: float = DEFAULT_CUTOFF_S, root: Path = ROOT) -> pd.DataFrame:
    """Return one audit row per raw ILS v2 execution record."""
    rows: list[dict] = []
    for source in ILS_V2_SOURCES:
        for path in sorted(root.glob(source.run_pattern), key=run_sort_key):
            data = load_json(path)
            dataset, instance, note = canonical_instance(data.get("dataset"), data.get("instance"))
            z_at_cutoff, selected_time, selected_tag = best_improvement_at_cutoff(data.get("improvements") or [], cutoff_s)
            final_z = float(data["objective"]) if data.get("objective") is not None else math.nan
            total_time = float(data.get("total_time", math.nan))
            rows.append(
                {
                    "method": "ILS_v2",
                    "dataset": dataset,
                    "instance": instance,
                    "run_id": data.get("run_id"),
                    "seed": data.get("seed"),
                    "Z_at_cutoff": z_at_cutoff,
                    "selected_time_s": selected_time,
                    "selected_tag": selected_tag,
                    "final_objective": final_z,
                    "time_to_best_s": data.get("time_to_best"),
                    "total_time_s": total_time,
                    "overrun_s": total_time - cutoff_s if pd.notna(total_time) else math.nan,
                    "source_run_hard_stop_compliant": False,
                    "value_found_within_budget": pd.notna(z_at_cutoff),
                    "comparison_eligible": pd.notna(z_at_cutoff),
                    "T_json": data.get("T"),
                    "J_json": data.get("J"),
                    "I_json": data.get("I"),
                    "iterations": data.get("iterations"),
                    "source_path": str(path.relative_to(root)),
                    "paper_note": note,
                    "scheduling": data.get("scheduling"),
                }
            )
    return pd.DataFrame(rows)


def build_instance_audit(
    run_audit: pd.DataFrame | None = None,
    summaries: dict[tuple[str | None, str | None], dict] | None = None,
    cutoff_s: float = DEFAULT_CUTOFF_S,
    root: Path = ROOT,
) -> pd.DataFrame:
    """Return one strict-budget audit row per canonical ILS v2 instance."""
    if run_audit is None:
        run_audit = collect_run_audit(cutoff_s=cutoff_s, root=root)
    if summaries is None:
        summaries = collect_summary_values(root=root)

    rows: list[dict] = []
    for (dataset, instance), group in run_audit.groupby(["dataset", "instance"], dropna=False, sort=True):
        eligible = group[group["comparison_eligible"].astype(bool)].copy()
        if eligible.empty:
            selected = group.sort_values(["source_path"]).iloc[0]
            z_at_cutoff = math.nan
        else:
            selected = eligible.sort_values(["Z_at_cutoff", "selected_time_s", "source_path"]).iloc[0]
            z_at_cutoff = float(selected["Z_at_cutoff"])
        z_best_untruncated = float(group["final_objective"].min())
        summary = summaries.get((dataset, instance), {})
        z_best_with_cross_pr = summary.get("Z_best_with_cross_pr")
        if z_best_with_cross_pr is None or pd.isna(z_best_with_cross_pr):
            z_best_with_cross_pr = z_best_untruncated
        z_best_with_cross_pr = float(z_best_with_cross_pr)

        schedule_available = bool(abs(float(selected["final_objective"]) - z_at_cutoff) <= EPS) if pd.notna(z_at_cutoff) else False
        schedule_validated = False
        if schedule_available and isinstance(selected.get("scheduling"), list):
            schedule_validated = validate_schedule(dataset, instance, selected["scheduling"], z_at_cutoff)

        rows.append(
            {
                "method": "ILS_v2",
                "dataset": dataset,
                "instance": instance,
                "n_runs": int(len(group)),
                "Z_at_cutoff": z_at_cutoff,
                "Z_mean_at_cutoff": float(eligible["Z_at_cutoff"].mean()) if not eligible.empty else math.nan,
                "Z_std_at_cutoff": float(eligible["Z_at_cutoff"].std(ddof=1)) if len(eligible) > 1 else 0.0,
                "Z_worst_at_cutoff": float(eligible["Z_at_cutoff"].max()) if not eligible.empty else math.nan,
                "Z_best_untruncated": z_best_untruncated,
                "Z_best_with_cross_pr": z_best_with_cross_pr,
                "postbudget_gain_pct": 100.0 * (z_at_cutoff - z_best_untruncated) / z_at_cutoff
                if pd.notna(z_at_cutoff)
                else math.nan,
                "cross_pr_gain_pct": 100.0 * (z_best_untruncated - z_best_with_cross_pr) / z_best_untruncated
                if z_best_untruncated
                else math.nan,
                "total_noncompliant_gain_pct": 100.0 * (z_at_cutoff - z_best_with_cross_pr) / z_at_cutoff
                if pd.notna(z_at_cutoff)
                else math.nan,
                "selected_run_id": selected.get("run_id"),
                "selected_time_s": selected.get("selected_time_s"),
                "selected_source_path": selected.get("source_path"),
                "schedule_available": schedule_available,
                "schedule_validated": schedule_validated,
                "source_run_hard_stop_compliant": False,
                "value_found_within_budget": bool(pd.notna(z_at_cutoff)),
                "comparison_eligible": bool(pd.notna(z_at_cutoff)),
                "cutoff_s": float(cutoff_s),
                "summary_source_path": summary.get("summary_source_path"),
            }
        )
    return pd.DataFrame(rows)


def master_run_rows(cutoff_s: float = DEFAULT_CUTOFF_S, root: Path = ROOT) -> tuple[list[dict], list[dict], pd.DataFrame, pd.DataFrame]:
    """Return master-dataset rows for strict ILS v2 and separate ILS_v2_pr."""
    run_audit = collect_run_audit(cutoff_s=cutoff_s, root=root)
    summaries = collect_summary_values(root=root)
    instance_audit = build_instance_audit(run_audit=run_audit, summaries=summaries, cutoff_s=cutoff_s, root=root)

    run_rows: list[dict] = []
    for _, row in run_audit.iterrows():
        run_rows.append(
            {
                "method": "ILS_v2",
                "dataset": row["dataset"],
                "instance": row["instance"],
                "run_id": row["run_id"],
                "seed": row["seed"],
                "Z": row["Z_at_cutoff"],
                "bound": None,
                "gap_solver_pct": None,
                "time_to_best_s": row["selected_time_s"],
                "total_time_s": row["total_time_s"],
                "time_budget_s": cutoff_s,
                "model_status": None,
                "iterations": row["iterations"],
                "T": row["T_json"],
                "J": row["J_json"],
                "I": row["I_json"],
                "source_path": row["source_path"],
                "paper_note": row["paper_note"],
                "summary_record": False,
                "value_found_within_budget": row["value_found_within_budget"],
                "source_run_hard_stop_compliant": False,
                "comparison_eligible": row["comparison_eligible"],
                "selected_time_s": row["selected_time_s"],
                "schedule_available": None,
                "schedule_validated": None,
            }
        )

    pr_rows: list[dict] = []
    for _, row in instance_audit.iterrows():
        pr_rows.append(
            {
                "method": "ILS_v2_pr",
                "dataset": row["dataset"],
                "instance": row["instance"],
                "run_id": "summary_cross_run_pr",
                "seed": None,
                "Z": row["Z_best_with_cross_pr"],
                "bound": None,
                "gap_solver_pct": None,
                "time_to_best_s": row["selected_time_s"],
                "total_time_s": cutoff_s,
                "time_budget_s": cutoff_s,
                "model_status": None,
                "iterations": None,
                "T": None,
                "J": None,
                "I": None,
                "source_path": row["summary_source_path"],
                "paper_note": "Cross-run path relinking is reported separately from equal-budget comparisons.",
                "summary_record": True,
                "value_found_within_budget": False,
                "source_run_hard_stop_compliant": False,
                "comparison_eligible": False,
                "selected_time_s": row["selected_time_s"],
                "schedule_available": row["schedule_available"],
                "schedule_validated": row["schedule_validated"],
            }
        )
    return run_rows, pr_rows, run_audit, instance_audit


def universe_counts(run_audit: pd.DataFrame, instance_audit: pd.DataFrame) -> dict[str, int]:
    """Return the four execution universes requested by the audit."""
    derived = instance_audit[instance_audit["dataset"].isin(["S", "2X", "3X", "4X", "5X"])]
    return {
        "raw_ils_execution_records": int(len(run_audit)),
        "derived_instances_for_comparisons": int(len(derived)),
        "real_order_book_instances": int((instance_audit["dataset"] == REAL_ORDER_BOOK).sum()),
        "legacy_ale1_instances": int(((instance_audit["dataset"] == "Real") & (instance_audit["instance"] == "Ale_1")).sum()),
    }


def write_report(run_audit: pd.DataFrame, instance_audit: pd.DataFrame, path: Path, cutoff_s: float) -> None:
    """Write a compact Markdown audit report."""
    public = instance_audit[instance_audit["dataset"].isin(BENCHMARK_FAMILY_ORDER)]
    noschedule = instance_audit[~instance_audit["schedule_available"].astype(bool)]
    counts = universe_counts(run_audit, instance_audit)
    gains = instance_audit[["postbudget_gain_pct", "cross_pr_gain_pct", "total_noncompliant_gain_pct"]].agg(["mean", "median", "max"])
    family = (
        public[public["dataset"].isin(["2X", "3X", "4X", "5X"])]
        .groupby("dataset")["total_noncompliant_gain_pct"]
        .mean()
        .reindex(["2X", "3X", "4X", "5X"])
    )

    def md_table(frame: pd.DataFrame, floatfmt: str = ".6f") -> list[str]:
        """Format a small dataframe as a GitHub-flavored Markdown table."""
        if frame.empty:
            return ["None."]
        headers = [str(column) for column in frame.columns]
        out_lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
        for _, record in frame.iterrows():
            cells = []
            for value in record:
                if pd.isna(value):
                    cells.append("")
                elif isinstance(value, (float, np.floating)):
                    cells.append(format(float(value), floatfmt))
                else:
                    cells.append(str(value))
            out_lines.append("| " + " | ".join(cells) + " |")
        return out_lines

    lines = [
        "# ILS v2 strict equal-budget audit",
        "",
        f"The comparison value is reconstructed from each run trajectory using only improvements with `time_s <= {cutoff_s:.1f}`. Within-run path relinking before the cutoff remains eligible; cross-run path relinking from summary files is reported as `ILS_v2_pr` and excluded from equal-budget comparisons.",
        "",
        "## Execution universes",
        "",
        "| universe | count |",
        "|---|---:|",
    ]
    for key, value in counts.items():
        lines.append(f"| {key} | {value} |")
    lines.extend(
        [
            "",
            "## Non-compliant gain metrics",
            "",
            *md_table(gains.reset_index(names="metric")),
            "",
            "## Mean total non-compliant gain by large family",
            "",
            *md_table(family.reset_index(name="mean_total_noncompliant_gain_pct")),
            "",
            "## Instances without a reproducible strict-budget schedule",
            "",
        ]
    )
    if noschedule.empty:
        lines.append("None.")
    else:
        cols = ["dataset", "instance", "Z_at_cutoff", "selected_source_path", "selected_time_s"]
        lines.extend(md_table(noschedule[cols]))
    lines.append("")
    atomic_write_text(path, "\n".join(lines) + "\n")


def output_stem(cutoff_s: float) -> str:
    """Return the audit filename stem for a cutoff."""
    if abs(float(cutoff_s) - DEFAULT_CUTOFF_S) <= EPS:
        return "ils_equal_budget"
    return f"ils_equal_budget_{int(round(float(cutoff_s)))}"


def write_outputs(cutoff_s: float = DEFAULT_CUTOFF_S, root: Path = ROOT, out: Path = OUT) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build and write the ILS equal-budget audit CSV and report files."""
    _, _, run_audit, instance_audit = master_run_rows(cutoff_s=cutoff_s, root=root)
    out.mkdir(parents=True, exist_ok=True)
    run_export = run_audit.drop(columns=["scheduling"], errors="ignore")
    stem = output_stem(cutoff_s)
    write_table(run_export, out / f"{stem}_runs.csv", ["dataset", "instance", "run_id"])
    write_table(instance_audit, out / f"{stem}.csv", ["dataset", "instance"])
    write_report(run_audit, instance_audit, out / f"{stem}_report.md", cutoff_s=cutoff_s)
    return run_audit, instance_audit


def main() -> int:
    """Command-line entry point for regenerating the audit artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cutoff", type=float, default=DEFAULT_CUTOFF_S, help="Wall-clock cutoff in seconds.")
    args = parser.parse_args()
    run_audit, instance_audit = write_outputs(cutoff_s=args.cutoff)
    counts = universe_counts(run_audit, instance_audit)
    noschedule = instance_audit[~instance_audit["schedule_available"].astype(bool)]
    print("ILS v2 strict equal-budget audit")
    for key, value in counts.items():
        print(f"{key}: {value}")
    print("Instances without strict-budget schedules:")
    print(noschedule[["dataset", "instance", "Z_at_cutoff", "selected_source_path"]].to_string(index=False))
    print("Gain metrics (mean/median/max):")
    print(instance_audit[["postbudget_gain_pct", "cross_pr_gain_pct", "total_noncompliant_gain_pct"]].agg(["mean", "median", "max"]).round(6).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
