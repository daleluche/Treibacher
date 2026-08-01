"""Generate LaTeX tables for the PSP manuscript from analysis outputs."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis" / "output"
PAPER_TABLES = ROOT / "paper" / "tables"
DATASET_ORDER = ["Real", "2X", "3X", "4X", "5X", "8X", "10X"]
EPS = 1e-6

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.matheuristics.psp_instance import load_instance


def esc(value: object) -> str:
    """Escape a value for LaTeX table cells."""
    text = "" if value is None or (isinstance(value, float) and math.isnan(value)) else str(value)
    return (
        text.replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("_", r"\_")
        .replace("#", r"\#")
    )


def fmt_num(value: object, digits: int = 1) -> str:
    """Format a numeric value for compact manuscript tables."""
    if value is None or pd.isna(value):
        return "--"
    return f"{float(value):,.{digits}f}".replace(",", r"\,")


def fmt_int(value: object) -> str:
    """Format an integer value for LaTeX."""
    if value is None or pd.isna(value):
        return "--"
    return f"{int(round(float(value))):,}".replace(",", r"\,")


def fmt_pct(value: object) -> str:
    """Format a percentage with two decimals."""
    if value is None or pd.isna(value):
        return "--"
    return f"{float(value):.2f}"


def fmt_p(value: object) -> str:
    """Format p-values for manuscript tables."""
    if value is None or pd.isna(value):
        return "--"
    value = float(value)
    return r"$<0.0001$" if value < 0.0001 else f"{value:.4f}"


def value_range(values: Iterable[object], formatter=fmt_int) -> str:
    """Return a single value or a min--max range."""
    clean = [float(v) for v in values if pd.notna(v)]
    if not clean:
        return "--"
    lo, hi = min(clean), max(clean)
    if abs(lo - hi) <= EPS:
        return formatter(lo)
    return f"{formatter(lo)}--{formatter(hi)}"


def write_table(path: Path, caption: str, label: str, headers: list[str], rows: list[list[object]]) -> None:
    """Write a small booktabs LaTeX table."""
    align = "l" + "r" * (len(headers) - 1)
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\footnotesize",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        r"\resizebox{\linewidth}{!}{%",
        rf"\begin{{tabular}}{{{align}}}",
        r"\toprule",
        " & ".join(headers) + r" \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(" & ".join(str(cell) for cell in row) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}%", r"}", r"\end{table}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def dataset_sort(frame: pd.DataFrame) -> pd.DataFrame:
    """Sort a dataframe by the canonical dataset order."""
    result = frame.copy()
    result["_rank"] = result["dataset"].map({d: i for i, d in enumerate(DATASET_ORDER)})
    return result.sort_values(["_rank", "dataset"]).drop(columns=["_rank"])


def make_tab_instances() -> None:
    """Generate the instance-dimension table."""
    rows = []
    for dataset in DATASET_ORDER:
        paths = sorted((ROOT / "experiments" / "GAMSPy" / dataset).glob("*.py"))
        dims = []
        for path in paths:
            inst = load_instance(path)
            binaries = inst.J * inst.T
            continuous = 2 * inst.I * inst.T + 1
            constraints = inst.I * inst.T + inst.T + 1
            dims.append((inst.T, inst.J, inst.I, binaries, continuous, constraints))
        if not dims:
            continue
        frame = pd.DataFrame(dims, columns=["T", "J", "I", "binary", "continuous", "constraints"])
        rows.append(
            [
                esc(dataset),
                fmt_int(len(dims)),
                value_range(frame["T"]),
                value_range(frame["J"]),
                value_range(frame["I"]),
                value_range(frame["binary"]),
                value_range(frame["continuous"]),
                value_range(frame["constraints"]),
            ]
        )
    write_table(
        PAPER_TABLES / "tab_instances.tex",
        "Benchmark dimensions by instance family.",
        "tab:instances",
        ["Set", "Inst.", "$T$", "$J$", "$I$", "Binary vars.", "Continuous vars.", "Constraints"],
        rows,
    )


def make_tab_gamma() -> None:
    """Generate the gamma-effect table."""
    detail = pd.read_csv(OUT / "gamma_effect.csv")
    summary = pd.read_csv(OUT / "gamma_effect_by_set.csv")
    optima = (
        detail.assign(optimal=detail["status_gamma0"].eq("OptimalGlobal") & (detail["gap_gamma0_pct"].abs() <= EPS))
        .groupby("dataset")["optimal"]
        .sum()
        .to_dict()
    )
    rows = []
    for _, row in dataset_sort(summary).iterrows():
        rows.append(
            [
                esc(row["dataset"]),
                fmt_int(row["n"]),
                fmt_int(optima.get(row["dataset"], 0)),
                fmt_pct(row["gamma0_gap_mean_pct"]),
                fmt_pct(row["gamma0001_gap_mean_pct"]),
                fmt_num(row["gamma0_time_mean_s"], 1),
                fmt_num(row["gamma0001_time_mean_s"], 1),
                fmt_num(row["delta_abs_mean"], 1),
                fmt_pct(row["delta_pct_mean"]),
            ]
        )
    write_table(
        PAPER_TABLES / "tab_gamma.tex",
        r"Controlled effect of removing the excess penalty ($\gamma=0$).",
        "tab:gamma",
        [
            "Set",
            "Inst.",
            "Opt. ($\\gamma=0$)",
            "Gap $\\gamma=0$ (\\%)",
            "Gap $\\gamma=0.001$ (\\%)",
            "Time $\\gamma=0$ (s)",
            "Time $\\gamma=0.001$ (s)",
            "$\\Delta Z$",
            "$\\Delta$ (\\%)",
        ],
        rows,
    )


def canonical_gap(z: object, bks: object) -> float:
    """Return the relative gap to BKS in percent."""
    if pd.isna(z) or pd.isna(bks):
        return np.nan
    return 100.0 * (float(z) - float(bks)) / max(abs(float(bks)), 1.0)


def load_ils_truncated(budget_s: float) -> dict[str, float]:
    """Return the best ILS v2 objective achieved by each instance before a budget."""
    best: dict[str, float] = {}
    for path in (ROOT / "experiments" / "GRASP" / "results_ils_v2").glob("*_run*.json"):
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        instance = data["instance"]
        values = [float(item["Z"]) for item in data.get("improvements", []) if float(item.get("time_s", 0.0)) <= budget_s]
        if not values:
            continue
        z = min(values)
        best[instance] = min(best.get(instance, z), z)
    return best


def method_summary(comp: pd.DataFrame, z_columns: dict[str, str], status_map: dict[str, pd.Series] | None = None) -> list[list[str]]:
    """Build per-dataset method rows with mean gap, wins, and proven optima."""
    rows = []
    status_map = status_map or {}
    for dataset in DATASET_ORDER:
        subset = comp[comp["dataset"] == dataset].copy()
        if subset.empty:
            continue
        values = pd.DataFrame({method: subset[col] for method, col in z_columns.items()}, index=subset.index)
        minima = values.min(axis=1, skipna=True)
        for method, col in z_columns.items():
            z = subset[col]
            n = int(z.notna().sum())
            if n == 0:
                rows.append([esc(dataset), esc(method), "0", "--", "0", "0"])
                continue
            gaps = [canonical_gap(a, b) for a, b in zip(z, subset["BKS"])]
            wins = int(((z <= minima + EPS) & z.notna()).sum())
            status = status_map.get(method)
            proven = int((status.loc[subset.index].fillna("") == "OptimalGlobal").sum()) if status is not None else 0
            rows.append([esc(dataset), esc(method), fmt_int(n), fmt_pct(np.nanmean(gaps)), fmt_int(wins), fmt_int(proven)])
    return rows


def make_tab_main3600() -> None:
    """Generate the 3600-second comparison table."""
    comp = pd.read_csv(OUT / "comparison_table.csv")
    comp["mip_3600_Z"] = np.where(comp["dataset"].isin(["8X", "10X"]), comp["cplex_mip_3600_Z"], comp["cplex_Z_1h"])
    inst = pd.read_csv(OUT / "master_instances.csv")
    cplex_1h = inst[inst["method"] == "CPLEX22_1h"].set_index("instance")["model_status"]
    mat_mip = inst[inst["method"] == "MAT_mip_3600s"].set_index("instance")["model_status"]
    comp["mip_3600_status"] = [
        mat_mip.get(row["instance"], np.nan) if row["dataset"] in ["8X", "10X"] else cplex_1h.get(row["instance"], np.nan)
        for _, row in comp.iterrows()
    ]
    rows = method_summary(
        comp,
        {
            "mip": "mip_3600_Z",
            "rf+fo": "rf_fo_3600_Z",
            "rf+mip": "rf_mip_3600_Z",
            "ILS v2": "ils2_Z_best",
        },
        {"mip": comp["mip_3600_status"]},
    )
    write_table(
        PAPER_TABLES / "tab_main3600.tex",
        "Method comparison at a 3600-second budget.",
        "tab:main3600",
        ["Set", "Method", "Inst.", "Mean gap to BKS (\\%)", "Wins", "Proven opt."],
        rows,
    )


def make_tab_short600() -> None:
    """Generate the 600-second short-budget comparison table."""
    comp = pd.read_csv(OUT / "comparison_table.csv")
    ils600 = load_ils_truncated(600.0)
    comp["ils2_600_Z"] = comp["instance"].map(ils600)
    inst = pd.read_csv(OUT / "master_instances.csv")
    mip600 = inst[inst["method"] == "MAT_mip_600s"].set_index("instance")["model_status"]
    comp["mip_600_status"] = comp["instance"].map(mip600)
    rows = method_summary(
        comp,
        {
            "mip": "cplex_mip_600_Z",
            "rf+fo": "rf_fo_600_Z",
            "rf+mip": "rf_mip_600_Z",
            "ILS v2": "ils2_600_Z",
        },
        {"mip": comp["mip_600_status"]},
    )
    write_table(
        PAPER_TABLES / "tab_short600.tex",
        "Method comparison at a 600-second budget.",
        "tab:short600",
        ["Set", "Method", "Inst.", "Mean gap to BKS (\\%)", "Wins", "Proven opt."],
        rows,
    )


def make_tab_frontier() -> None:
    """Generate the method-frontier table."""
    def compact_source(source: object) -> str:
        """Return a short source label for the frontier table."""
        text = str(source)
        if "post-hoc" in text:
            return "post-hoc"
        if "registered" in text:
            return "registered"
        if "production" in text:
            return "production"
        return text

    counts = pd.read_csv(OUT / "sprint3_frontier_counts.csv")
    sources = pd.read_csv(OUT / "sprint3_cell_sources.csv")
    merged = counts.merge(sources, on=["dataset", "budget_s"], how="left", suffixes=("", "_declared"))
    merged["_rank"] = merged["dataset"].map({d: i for i, d in enumerate(DATASET_ORDER)})
    merged = merged.sort_values(["_rank", "budget_s"]).drop(columns=["_rank"])
    rows = []
    for _, row in merged.iterrows():
        source = row.get("source_cell_declared") or row.get("source_cell")
        rows.append(
            [
                esc(row["dataset"]),
                fmt_int(row["budget_s"]),
                esc(row["winner"]),
                fmt_int(row["n"]),
                fmt_int(row.get("mip")),
                fmt_int(row.get("rf+fo")),
                fmt_int(row.get("rf+mip")),
                esc(compact_source(source)),
            ]
        )
    write_table(
        PAPER_TABLES / "tab_frontier.tex",
        "Observed method frontier by family and time budget.",
        "tab:frontier",
        ["Set", "Budget (s)", "Majority winner", "Inst.", "mip", "rf+fo", "rf+mip", "Source"],
        rows,
    )


def make_tab_q5() -> None:
    """Generate the Q5 cross-budget table."""
    df = pd.read_csv(OUT / "sprint3_q5_cross_budget.csv")
    rows = []
    for _, row in dataset_sort(df).iterrows():
        rows.append(
            [
                esc(row["dataset"]),
                esc(row["instance"]),
                fmt_num(row["mip_10800_Z"], 1),
                fmt_num(row["best_decomp_3600_Z"], 1),
                esc(row["best_decomp_3600_method"]),
                fmt_pct(row["delta_rel_pct"]),
                esc(row["winner"]),
            ]
        )
    write_table(
        PAPER_TABLES / "tab_q5.tex",
        "Cross-budget check: cold MIP at 10800 seconds versus the best decomposition at 3600 seconds.",
        "tab:q5",
        ["Set", "Instance", "mip@10800", "Best decomp.@3600", "Decomp. method", "$\\Delta$ (\\%)", "Winner"],
        rows,
    )


def make_tab_stats() -> None:
    """Generate the Wilcoxon statistical-test table."""
    df = pd.read_csv(OUT / "sprint3_statistical_tests.csv")
    rows = [
        [esc(r["comparison"]), fmt_int(r["n"]), fmt_p(r["p_value"]), fmt_num(r["rank_biserial"], 3), fmt_pct(r["median_rel_delta_pct"])]
        for _, r in df.iterrows()
    ]
    write_table(
        PAPER_TABLES / "tab_stats.tex",
        "Wilcoxon paired tests over matched cells.",
        "tab:stats",
        ["Comparison", "$n$", "$p$", "Rank-biserial", "Median $\\Delta$ (\\%)"],
        rows,
    )


def make_tab_seeds() -> None:
    """Generate the seed-variability table."""
    df = pd.read_csv(OUT / "sprint3_seed_variability.csv")
    rows = []
    for _, r in dataset_sort(df).iterrows():
        rows.append([esc(r["dataset"]), esc(r["instance"]), fmt_num(r["Z_mean"], 1), fmt_num(r["Z_std"], 1), fmt_num(r["Z_min"], 1), fmt_num(r["Z_max"], 1)])
    write_table(
        PAPER_TABLES / "tab_seeds.tex",
        "Seed variability for the production RF+FO configuration.",
        "tab:seeds",
        ["Set", "Instance", "Mean $Z$", "Std.", "Min.", "Max."],
        rows,
    )


def make_tab_scale_construction() -> None:
    """Generate the 8X/10X construction-diagnostic table."""
    df = pd.read_csv(OUT / "sprint3_scale_v2_construction.csv")
    rows = []
    for _, r in dataset_sort(df).iterrows():
        rows.append(
            [
                esc(r["dataset"]),
                esc(r["instance"]),
                esc(r["method"]),
                esc(r["construction_used"]),
                fmt_num(r["construction_Z"], 1),
                fmt_num(r["rf_wall_time_s"], 1),
                fmt_num(r["improvement_time_left_s"], 1),
                fmt_num(r["Z_final"], 1),
            ]
        )
    write_table(
        PAPER_TABLES / "tab_scale_construction.tex",
        "Construction diagnostics for post-fix 8X/10X runs.",
        "tab:scale-construction",
        ["Set", "Instance", "Method", "Construction", "$Z$ after constr.", "RF wall (s)", "Improve left (s)", "Final $Z$"],
        rows,
    )


def main() -> int:
    """Generate all manuscript tables."""
    PAPER_TABLES.mkdir(parents=True, exist_ok=True)
    make_tab_instances()
    make_tab_gamma()
    make_tab_main3600()
    make_tab_short600()
    make_tab_frontier()
    make_tab_q5()
    make_tab_stats()
    make_tab_seeds()
    make_tab_scale_construction()
    print(f"Wrote LaTeX tables to {PAPER_TABLES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
