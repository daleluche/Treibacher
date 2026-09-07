"""Quantify the service-inventory trade-off induced by the holding penalty."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.families import write_table
from experiments.matheuristics.psp_instance import evaluate, load_instance

OUT = ROOT / "analysis" / "output"
GAMSPY = ROOT / "experiments" / "GAMSPy"
GAMMA0_RESULTS = GAMSPY / "variant_gamma0" / "results_gamma0"
DATASETS = ["2X", "3X", "4X", "5X"]
EPS = 1e-6


def load_json(path: Path) -> dict:
    """Load one JSON file."""
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def schedule_from_result(data: dict, horizon: int) -> list[int]:
    """Return a dense 1-indexed process schedule, using zero for idle periods."""
    if isinstance(data.get("schedule"), list):
        schedule = [int(value) for value in data["schedule"]]
        if len(schedule) != horizon:
            raise ValueError(f"Dense schedule has length {len(schedule)}, expected {horizon}.")
        return schedule

    schedule = [0] * horizon
    for item in data.get("scheduling", []):
        period = int(item["period"])
        process = int(item["process"])
        if not 1 <= period <= horizon:
            raise ValueError(f"Schedule period {period} is outside horizon 1..{horizon}.")
        schedule[period - 1] = process
    return schedule


def clean_status(value: object) -> str:
    """Normalize a GAMSPy model status value for reporting."""
    return str(value or "").replace("ModelStatus.", "")


def collect_tradeoff_rows() -> pd.DataFrame:
    """Evaluate gamma=0 and gamma=0.001 schedules for each IncT instance."""
    rows: list[dict] = []
    for dataset in DATASETS:
        for canonical_path in sorted((GAMSPY / dataset / "results_3horas").glob("*.json")):
            canonical = load_json(canonical_path)
            instance = str(canonical["instance"])
            gamma0_path = GAMMA0_RESULTS / f"{instance}.json"
            if not gamma0_path.exists():
                raise FileNotFoundError(f"Missing gamma=0 result for {instance}: {gamma0_path}")

            inst = load_instance(GAMSPY / dataset / f"{instance}.py")
            gamma0 = load_json(gamma0_path)
            gamma0_schedule = schedule_from_result(gamma0, inst.T)
            gamma001_schedule = schedule_from_result(canonical, inst.T)
            _, shortage_gamma0, excess_gamma0 = evaluate(gamma0_schedule, inst)
            _, shortage_gamma001, excess_gamma001 = evaluate(gamma001_schedule, inst)

            delta_shortage = shortage_gamma001 - shortage_gamma0
            excess_reduction = excess_gamma0 - excess_gamma001
            rows.append(
                {
                    "dataset": dataset,
                    "instance": instance,
                    "shortage_gamma0": shortage_gamma0,
                    "shortage_gamma001": shortage_gamma001,
                    "delta_shortage": delta_shortage,
                    "delta_shortage_pct": 100.0 * delta_shortage / max(abs(shortage_gamma0), 1.0),
                    "excess_gamma0": excess_gamma0,
                    "excess_gamma001": excess_gamma001,
                    "excess_reduction": excess_reduction,
                    "excess_reduction_pct": 100.0 * excess_reduction / max(abs(excess_gamma0), 1.0),
                    "both_proven_optimal": (
                        dataset == "2X"
                        and clean_status(gamma0.get("model_status")) == "OptimalGlobal"
                        and clean_status(canonical.get("model_status")) == "OptimalGlobal"
                        and abs(float(gamma0.get("gap_pct", 0.0))) <= EPS
                        and abs(float(canonical.get("gap_pct", 0.0))) <= EPS
                    ),
                }
            )
    return pd.DataFrame(rows)


def append_2x_summary_rows(two_x: pd.DataFrame) -> pd.DataFrame:
    """Append median and aggregate rows to the 2X trade-off table."""
    columns = list(two_x.columns)
    numeric = [column for column in columns if column not in {"dataset", "instance", "both_proven_optimal"}]

    median = {column: np.nan for column in columns}
    median.update({"dataset": "2X", "instance": "MEDIAN", "both_proven_optimal": True})
    for column in numeric:
        median[column] = float(two_x[column].median())

    aggregate = {column: np.nan for column in columns}
    aggregate.update({"dataset": "2X", "instance": "AGGREGATE", "both_proven_optimal": True})
    for column in [
        "shortage_gamma0",
        "shortage_gamma001",
        "delta_shortage",
        "excess_gamma0",
        "excess_gamma001",
        "excess_reduction",
    ]:
        aggregate[column] = float(two_x[column].sum())
    aggregate["delta_shortage_pct"] = 100.0 * aggregate["delta_shortage"] / max(
        abs(aggregate["shortage_gamma0"]), 1.0
    )
    aggregate["excess_reduction_pct"] = 100.0 * aggregate["excess_reduction"] / max(
        abs(aggregate["excess_gamma0"]), 1.0
    )

    return pd.concat([two_x, pd.DataFrame([median, aggregate])], ignore_index=True)


def main() -> int:
    """Write trade-off CSVs and print the acceptance-check summary."""
    OUT.mkdir(parents=True, exist_ok=True)
    all_rows = collect_tradeoff_rows()
    two_x = all_rows[all_rows["dataset"] == "2X"].copy()
    two_x_table = append_2x_summary_rows(two_x)

    write_table(two_x_table, OUT / "gamma_tradeoff_2x.csv", ["dataset", "instance"])
    write_table(all_rows, OUT / "gamma_tradeoff_all.csv", ["dataset", "instance"])

    median_shortage_pct = float(two_x["delta_shortage_pct"].median())
    median_excess_reduction_pct = float(two_x["excess_reduction_pct"].median())
    aggregate_delta_shortage = float(two_x["delta_shortage"].sum())
    aggregate_excess_reduction = float(two_x["excess_reduction"].sum())
    positive_shortage_2x = int((two_x["delta_shortage"] > EPS).sum())
    positive_shortage_all = int((all_rows["delta_shortage"] > EPS).sum())
    ratio = aggregate_excess_reduction / max(abs(aggregate_delta_shortage), 1.0)

    print("Gamma trade-off check")
    print(f"2X instances with increased shortage: {positive_shortage_2x} / {len(two_x)}")
    print(f"2X median shortage change pct: {median_shortage_pct:.2f}%")
    print(f"2X median inventory reduction pct: {median_excess_reduction_pct:.1f}%")
    print(f"2X aggregate shortage change kg: {aggregate_delta_shortage:,.0f}")
    print(f"2X aggregate inventory reduction kg-periods: {aggregate_excess_reduction:,.0f}")
    print(f"2X exchange ratio: 1:{ratio:,.0f}")
    print(f"2X-5X instances with increased shortage: {positive_shortage_all} / {len(all_rows)}")
    print(f"Wrote {OUT / 'gamma_tradeoff_2x.csv'}")
    print(f"Wrote {OUT / 'gamma_tradeoff_all.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
