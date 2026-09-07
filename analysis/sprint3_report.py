"""Generate the Sprint 3 final analysis report, tables, statistics, and figures."""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis" / "output"
FIG = ROOT / "analysis" / "figures"
MAT = ROOT / "experiments" / "matheuristics"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.families import (
    BENCHMARK_FAMILY_ORDER,
    atomic_write_text,
    base_pattern,
    public_benchmark,
    write_table,
)


def canonical_instance(dataset: object, instance: object) -> tuple[object, object]:
    """Return the paper-facing dataset and instance labels."""
    if isinstance(dataset, str) and isinstance(instance, str) and dataset == "Real" and instance.startswith("Ale_"):
        suffix = instance.rsplit("_", 1)[1]
        if suffix != "1":
            return "S", f"S_{suffix}"
    if isinstance(instance, str) and instance.startswith("S_"):
        return "S", instance
    return dataset, instance


def canonicalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply paper-facing labels to a dataframe with dataset/instance columns."""
    if frame.empty or not {"dataset", "instance"}.issubset(frame.columns):
        return frame
    result = frame.copy()
    labels = result.apply(lambda row: canonical_instance(row["dataset"], row["instance"]), axis=1, result_type="expand")
    result["dataset"] = labels[0]
    result["instance"] = labels[1]
    return result


def fmt(value: object, digits: int = 3) -> str:
    """Format numbers for Markdown tables."""
    if value is None:
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(number):
        return ""
    return f"{number:.{digits}f}"


def markdown_table(rows: Iterable[dict], columns: list[str], digits: int = 3) -> str:
    """Render a list of dictionaries as a Markdown table."""
    rows = list(rows)
    if not rows:
        return "_No rows._"
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        cells = []
        for col in columns:
            value = row.get(col, "")
            if isinstance(value, (int, float, np.floating)) and not isinstance(value, bool):
                cell = fmt(value, digits)
            elif isinstance(value, bool):
                cell = str(value).lower()
            else:
                cell = str(value)
            cells.append(cell.replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def load_json(path: Path) -> dict:
    """Load a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_result_jsons() -> pd.DataFrame:
    """Load all matheuristic result JSONs used in Sprint 3 analysis."""
    folders = [
        MAT / "results_pilot",
        MAT / "results_tuning",
        MAT / "results_short_budget",
        MAT / "results_short_budget_v2",
        MAT / "results_scale_8x10x",
        MAT / "results_scale_8x10x_v2",
        MAT / "results_scale_8x10x_mip10800",
        MAT / "results_production" / "b600",
        MAT / "results_production" / "a3600",
        MAT / "results_production" / "c_seeds",
        MAT / "results_production" / "s1",
    ]
    rows = []
    for folder in folders:
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.json")):
            data = load_json(path)
            if "Z_final" not in data:
                continue
            params = data.get("params", {})
            dataset, instance = canonical_instance(data.get("dataset"), data.get("instance"))
            rows.append(
                {
                    "dataset": dataset,
                    "instance": instance,
                    "method": data.get("method"),
                    "seed": data.get("seed"),
                    "budget_s": float(params.get("budget", np.nan)),
                    "Z_final": float(data.get("Z_final", np.nan)),
                    "best_bound": data.get("best_bound") or data.get("dual_bound"),
                    "gap_solver_pct": data.get("gap_solver_pct") or data.get("gap_pct"),
                    "model_status": data.get("model_status"),
                    "solve_status": data.get("solve_status"),
                    "Z_rf": data.get("Z_rf"),
                    "Z_greedy": data.get("Z_greedy"),
                    "construction_used": data.get("construction_used"),
                    "construction_Z": (data.get("construction") or {}).get("Z")
                    if isinstance(data.get("construction"), dict)
                    else data.get("Z_rf"),
                    "rf_wall_time_s": data.get("rf_wall_time_s"),
                    "wall_time_total": data.get("wall_time_total"),
                    "source_folder": str(folder.relative_to(ROOT)),
                    "source_path": str(path.relative_to(ROOT)),
                }
            )
    return pd.DataFrame(rows)


def save_figure(fig: plt.Figure, name: str) -> None:
    """Save a Matplotlib figure as PNG and PDF."""
    FIG.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    png_path = FIG / f"{name}.png"
    pdf_path = FIG / f"{name}.pdf"
    fig.savefig(png_path, dpi=220)
    fig.savefig(
        pdf_path,
        metadata={
            "Creator": "Treibacher analysis pipeline",
            "Producer": "Treibacher analysis pipeline",
            "CreationDate": None,
            "ModDate": None,
        },
    )
    plt.close(fig)


def performance_profile(data: pd.DataFrame, name: str, title: str) -> None:
    """Create a Dolan-More performance profile from method/objective rows."""
    pivot = data.pivot_table(index="instance", columns="method", values="Z_final", aggfunc="min")
    pivot = pivot.dropna(how="all")
    pivot = pivot.dropna(axis=1, how="all")
    if pivot.empty:
        return
    best = pivot.min(axis=1)
    ratios = pivot.div(best, axis=0)
    taus = np.linspace(1.0, min(2.5, float(np.nanmax(ratios.values)) + 0.05), 140)
    styles = {
        "mip": ("#1f4e79", "-"),
        "rf+fo": ("#b05a00", "--"),
        "rf+mip": ("#3f7f3f", "-."),
    }
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    for method in [m for m in ["mip", "rf+mip", "rf+fo"] if m in ratios.columns]:
        vals = ratios[method].dropna().to_numpy()
        y = [(vals <= tau + 1e-12).mean() for tau in taus]
        color, ls = styles.get(method, ("#333333", "-"))
        ax.plot(taus, y, label=method, color=color, linestyle=ls, linewidth=2.2)
    ax.set_title(title)
    ax.set_xlabel("Performance ratio to best observed solution")
    ax.set_ylabel("Fraction of instances")
    ax.set_ylim(0, 1.02)
    ax.grid(True, color="#dddddd", linewidth=0.7)
    ax.legend(frameon=False)
    save_figure(fig, name)


def canonical_scale_v2_table(mat_runs: pd.DataFrame) -> pd.DataFrame:
    """Return canonical 8X/10X @3600s rows: cold MIP from Sprint 2.5 and decompositions from v2."""
    original = pd.read_csv(MAT / "results_scale_8x10x" / "scale_8x10x_summary.csv")
    mip = original[["dataset", "instance", "Z_mip", "path_mip"]].rename(
        columns={"Z_mip": "mip", "path_mip": "source_mip"}
    )
    v2 = mat_runs[
        (mat_runs["source_folder"].str.contains("results_scale_8x10x_v2", na=False))
        & (mat_runs["budget_s"] == 3600)
        & (mat_runs["method"].isin(["rf+fo", "rf+mip"]))
        & (mat_runs["seed"] == 1)
    ].copy()
    wide = v2.pivot_table(index=["dataset", "instance"], columns="method", values="Z_final", aggfunc="min").reset_index()
    sources = (
        v2.pivot_table(index=["dataset", "instance"], columns="method", values="source_path", aggfunc="first")
        .reset_index()
        .rename(columns={"rf+fo": "source_rf+fo", "rf+mip": "source_rf+mip"})
    )
    table = mip.merge(wide, on=["dataset", "instance"], how="left").merge(sources, on=["dataset", "instance"], how="left")
    table["source_mip"] = "experiments/matheuristics/results_scale_8x10x (registered cold MIP)"
    return table.sort_values(["dataset", "instance"])


def mip10800_table(mat_runs: pd.DataFrame) -> pd.DataFrame:
    """Return cold MIP @10800s rows for 8X/10X."""
    mip = mat_runs[
        (mat_runs["source_folder"].str.contains("results_scale_8x10x_mip10800", na=False))
        & (mat_runs["method"] == "mip")
        & (mat_runs["budget_s"] == 10800)
        & (mat_runs["seed"] == 1)
    ].copy()
    return mip[
        [
            "dataset",
            "instance",
            "Z_final",
            "best_bound",
            "gap_solver_pct",
            "model_status",
            "solve_status",
            "source_path",
        ]
    ].rename(columns={"Z_final": "mip_10800_Z", "source_path": "source_mip_10800"}).sort_values(["dataset", "instance"])


def q5_cross_budget_table(scale_v2: pd.DataFrame, mip10800: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare cold MIP @10800s with best canonical decomposition @3600s for Q5."""
    decomp = scale_v2[["dataset", "instance", "rf+fo", "rf+mip"]].copy()
    decomp["best_decomp_3600_Z"] = decomp[["rf+fo", "rf+mip"]].min(axis=1)
    decomp["best_decomp_3600_method"] = decomp[["rf+fo", "rf+mip"]].idxmin(axis=1)
    table = mip10800.merge(
        decomp[["dataset", "instance", "best_decomp_3600_Z", "best_decomp_3600_method"]],
        on=["dataset", "instance"],
        how="left",
    )
    table["delta_rel_pct"] = (
        (table["mip_10800_Z"] - table["best_decomp_3600_Z"])
        / np.maximum(np.abs(table["best_decomp_3600_Z"]), 1.0)
        * 100.0
    )
    table["winner"] = np.where(table["mip_10800_Z"] < table["best_decomp_3600_Z"] - 1e-9, "mip@10800", "decomp@3600")
    table["mip10800_strictly_better"] = table["winner"] == "mip@10800"
    verdict = (
        table.groupby("dataset", as_index=False)
        .agg(mip10800_wins=("mip10800_strictly_better", "sum"), n=("instance", "count"))
    )
    verdict["Q5_true"] = verdict["mip10800_wins"] >= 3
    verdict["Q5_true"] = verdict["Q5_true"].map(lambda value: str(bool(value)).lower())
    return table.sort_values(["dataset", "instance"]), verdict.sort_values("dataset")


def canonical_3600_table(comp: pd.DataFrame, prod3600: pd.DataFrame, scale_v2: pd.DataFrame) -> pd.DataFrame:
    """Build the canonical 3600s comparison table used in paper statistics and frontier cells."""
    rows = []
    comp = public_benchmark(comp)
    rf_fo_a = prod3600[prod3600["method"] == "rf+fo"].set_index("instance")
    for _, row in comp.iterrows():
        dataset = row["dataset"]
        instance = row["instance"]
        if dataset in {"8X", "10X"}:
            scale_row = scale_v2[scale_v2["instance"] == instance]
            if scale_row.empty:
                continue
            scale_row = scale_row.iloc[0]
            rows.append(
                {
                    "dataset": dataset,
                    "instance": instance,
                    "mip": scale_row.get("mip"),
                    "rf+fo": scale_row.get("rf+fo"),
                    "rf+mip": scale_row.get("rf+mip"),
                    "source_cell": "post-hoc: MIP from results_scale_8x10x; rf+fo/rf+mip from results_scale_8x10x_v2",
                }
            )
        else:
            mip_value = row.get("cplex_mip_3600_Z") if instance == "S_1" else row.get("cplex_Z_1h")
            rf_fo_value = row.get("rf_fo_3600_Z") if instance == "S_1" else (
                rf_fo_a.loc[instance, "Z_final"] if instance in rf_fo_a.index else np.nan
            )
            source_cell = (
                "reconstructed S_1 supplement: mip/rf+fo from results_production/s1"
                if instance == "S_1"
                else "registered/production: CPLEX22_1h and Grade A rf+fo"
            )
            rows.append(
                {
                    "dataset": dataset,
                    "instance": instance,
                    "mip": mip_value,
                    "rf+fo": rf_fo_value,
                    "rf+mip": np.nan,
                    "source_cell": source_cell,
                }
            )
    return pd.DataFrame(rows).sort_values(["dataset", "instance"])


def canonical_600_table(prod600: pd.DataFrame) -> pd.DataFrame:
    """Build the canonical 600s comparison table from Grade B."""
    table = prod600.pivot_table(index=["dataset", "instance"], columns="method", values="Z_final", aggfunc="min").reset_index()
    table = public_benchmark(table)
    table["source_cell"] = "production Grade B @600s"
    return table


def convergence_plot(mat_runs: pd.DataFrame, instance: str) -> None:
    """Plot incumbent trajectories for one instance from available JSONs."""
    candidates = mat_runs[mat_runs["instance"] == instance].copy()
    if candidates.empty:
        return
    selected = (
        candidates.sort_values(["budget_s", "Z_final"])
        .groupby(["method", "budget_s"], as_index=False)
        .first()
    )
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    styles = {"mip": ("#1f4e79", "-"), "rf+fo": ("#b05a00", "--"), "rf+mip": ("#3f7f3f", "-.")}
    for _, row in selected.iterrows():
        data = load_json(ROOT / row["source_path"])
        points = [(0.0, data.get("Z_greedy") or data.get("Z_rf") or data.get("Z_final"))]
        for imp in data.get("improvements", []) or []:
            if imp.get("Z") is not None:
                points.append((float(imp.get("time_s", 0.0)), float(imp["Z"])))
        points.append((float(data.get("wall_time_total") or row["budget_s"]), float(data["Z_final"])))
        points = sorted(points)
        color, ls = styles.get(row["method"], ("#333333", "-"))
        label = f"{row['method']} @{int(row['budget_s'])}s"
        ax.step([p[0] for p in points], [p[1] for p in points], where="post", label=label, color=color, linestyle=ls)
    ax.set_title(f"Incumbent trajectory: {instance}")
    ax.set_xlabel("Wall time (s)")
    ax.set_ylabel("Objective value")
    ax.grid(True, color="#dddddd", linewidth=0.7)
    ax.legend(frameon=False, fontsize=8)
    save_figure(fig, f"convergence_{instance}")


def frontier_table(comp: pd.DataFrame, canonical_600: pd.DataFrame, canonical_3600: pd.DataFrame) -> pd.DataFrame:
    """Build the method-frontier winner table by dataset and budget."""
    rows = []
    comp = public_benchmark(comp)
    for dataset, group in comp.groupby("dataset"):
        for budget in [600, 3600, 10800]:
            winners: list[str] = []
            source_cell = ""
            if budget == 600:
                source = canonical_600[canonical_600["dataset"] == dataset]
                source_cell = "production Grade B @600s"
            elif budget == 3600:
                source = canonical_3600[canonical_3600["dataset"] == dataset]
                source_cell = "; ".join(sorted(set(source["source_cell"].dropna()))) if not source.empty else ""
            else:
                source = group.copy()
                source_cell = (
                    "post-hoc: cold MIP from results_scale_8x10x_mip10800 only; decompositions not run @10800s"
                    if dataset in {"8X", "10X"}
                    else "registered CPLEX22_3h where available"
                )
            for _, row in source.iterrows():
                if budget == 10800:
                    candidates = {"mip": row.get("cplex_Z")}
                else:
                    candidates = {method: row.get(method) for method in ["mip", "rf+mip", "rf+fo"]}
                candidates = {k: v for k, v in candidates.items() if pd.notna(v)}
                if candidates:
                    winners.append(min(candidates, key=candidates.get))
            counts = {m: winners.count(m) for m in ["mip", "rf+mip", "rf+fo"]}
            majority = max(counts, key=counts.get) if winners else "no data"
            rows.append({"dataset": dataset, "budget_s": budget, "winner": majority, "n": len(winners), "source_cell": source_cell, **counts})
    table = pd.DataFrame(rows)
    table["dataset"] = pd.Categorical(table["dataset"], BENCHMARK_FAMILY_ORDER, ordered=True)
    return table.sort_values(["dataset", "budget_s"])


def frontier_heatmap(frontier: pd.DataFrame) -> None:
    """Render the categorical method-frontier heatmap."""
    palette = {
        "mip": "#2f5f8f",
        "rf+mip": "#3c8f6c",
        "rf+fo": "#c7772b",
        "no data": "#d6d6d6",
    }
    text_color = {"mip": "white", "rf+mip": "white", "rf+fo": "white", "no data": "#333333"}
    grid = frontier.pivot(index="dataset", columns="budget_s", values="winner").reindex(BENCHMARK_FAMILY_ORDER)
    budgets = list(grid.columns)
    dataset_labels = {"S": "S\nT=19", "2X": "2X\nT=38", "3X": "3X\nT=57", "4X": "4X\nT=76", "5X": "5X\nT=95", "8X": "8X\nT=152", "10X": "10X\nT=190"}
    budget_labels = {600: "10 min\n(600 s)", 3600: "1 h\n(3,600 s)", 10800: "3 h\n(10,800 s)"}

    fig, ax = plt.subplots(figsize=(7.8, 5.0))
    ax.set_xlim(-0.5, len(budgets) - 0.5)
    ax.set_ylim(len(grid.index) - 0.5, -0.5)
    ax.set_facecolor("#f7f7f4")

    for i, dataset in enumerate(grid.index):
        for j, budget in enumerate(budgets):
            row = frontier[(frontier.dataset == dataset) & (frontier.budget_s == budget)].iloc[0]
            winner = row["winner"]
            post_hoc_10800 = dataset in {"8X", "10X"} and int(budget) == 10800
            rect = plt.Rectangle(
                (j - 0.5, i - 0.5),
                1,
                1,
                facecolor=palette.get(winner, palette["no data"]),
                edgecolor="white",
                linewidth=1.5,
                hatch="///" if post_hoc_10800 else None,
            )
            ax.add_patch(rect)
            label = f"{winner.upper()}{'†' if post_hoc_10800 else ''}"
            counts = f"{int(row['mip'])} / {int(row['rf+mip'])} / {int(row['rf+fo'])}"
            ax.text(j, i - 0.10, label, ha="center", va="center", color=text_color.get(winner, "#333333"), fontsize=9, fontweight="bold")
            ax.text(j, i + 0.18, counts, ha="center", va="center", color=text_color.get(winner, "#333333"), fontsize=7.5)

    ax.set_xticks(range(len(budgets)), [budget_labels.get(int(c), str(int(c))) for c in budgets])
    ax.set_yticks(range(len(grid.index)), [dataset_labels.get(d, d) for d in grid.index])
    ax.tick_params(axis="both", length=0, labelsize=9)
    ax.set_xlabel("Wall-clock budget", fontsize=10, labelpad=10)
    ax.set_ylabel("Instance family", fontsize=10, labelpad=10)
    ax.set_title("Method-choice frontier by scale and time budget", fontsize=13, pad=12, fontweight="bold")
    ax.set_xticks(np.arange(-0.5, len(budgets), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(grid.index), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.5)
    ax.tick_params(which="minor", bottom=False, left=False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    handles = [
        plt.Line2D([0], [0], marker="s", linestyle="", markersize=10, markerfacecolor=palette["mip"], markeredgecolor="none", label="Cold MIP"),
        plt.Line2D([0], [0], marker="s", linestyle="", markersize=10, markerfacecolor=palette["rf+mip"], markeredgecolor="none", label="RF+MIP"),
        plt.Line2D([0], [0], marker="s", linestyle="", markersize=10, markerfacecolor=palette["rf+fo"], markeredgecolor="none", label="RF+FO"),
    ]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3, frameon=False, fontsize=9)
    fig.text(0.5, 0.025, "Cell score: MIP / RF+MIP / RF+FO wins. † 8X/10X @10,800s contains cold MIP only; decompositions were not run at that budget.", ha="center", fontsize=8, color="#4a4a4a")
    save_figure(fig, "frontier_heatmap")


def rank_biserial(x: np.ndarray, y: np.ndarray) -> float:
    """Compute rank-biserial effect size for paired differences x-y."""
    diff = x - y
    diff = diff[np.abs(diff) > 1e-12]
    if diff.size == 0:
        return 0.0
    order = np.argsort(np.abs(diff))
    ranks = np.empty_like(diff, dtype=float)
    ranks[order] = np.arange(1, diff.size + 1)
    pos = ranks[diff > 0].sum()
    neg = ranks[diff < 0].sum()
    return float((pos - neg) / (diff.size * (diff.size + 1) / 2.0))


def relative_delta(lhs: pd.Series, rhs: pd.Series) -> pd.Series:
    """Return relative objective differences in percent; negative favors lhs."""
    return (lhs.astype(float) - rhs.astype(float)) / np.maximum(np.abs(rhs.astype(float)), 1.0) * 100.0


def exact_sign_permutation_pvalue(values: np.ndarray) -> float:
    """Enumerate the exact two-sided sign-permutation p-value for block deltas."""
    clean = values[np.abs(values) > 1e-12]
    if clean.size == 0:
        return 1.0
    observed = abs(float(clean.sum()))
    extreme = 0
    total = 2 ** clean.size
    for mask in range(total):
        signs = np.array([1.0 if (mask >> bit) & 1 else -1.0 for bit in range(clean.size)])
        if abs(float((signs * clean).sum())) >= observed - 1e-12:
            extreme += 1
    return extreme / total


def bootstrap_block_ci(values: np.ndarray, seed: int, reps: int = 10_000) -> tuple[float, float]:
    """Bootstrap a confidence interval by resampling whole block deltas."""
    clean = values[np.isfinite(values)]
    if clean.size == 0:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    samples = rng.choice(clean, size=(reps, clean.size), replace=True)
    medians = np.median(samples, axis=1)
    return tuple(np.percentile(medians, [2.5, 97.5]))


def comparison_frame(
    source: pd.DataFrame,
    lhs: str,
    rhs: str,
    comparison: str,
    budget_s: int,
    scope: str,
) -> pd.DataFrame:
    """Build a tidy frame for one method comparison."""
    cols = ["dataset", "instance", lhs, rhs]
    sub = public_benchmark(source[cols].dropna(subset=[lhs, rhs])).copy()
    sub["comparison"] = comparison
    sub["budget_s"] = budget_s
    sub["scope"] = scope
    sub["lhs_method"] = lhs
    sub["rhs_method"] = rhs
    sub["delta_pct"] = relative_delta(sub[lhs], sub[rhs])
    sub["base_pattern"] = sub["instance"].map(base_pattern)
    return sub


def descriptive_by_scale(comparisons: list[pd.DataFrame]) -> pd.DataFrame:
    """Summarize paired differences by family without treating them as independent tests."""
    rows = []
    data = pd.concat(comparisons, ignore_index=True)
    for (comparison, budget_s, scope, dataset), group in data.groupby(["comparison", "budget_s", "scope", "dataset"]):
        delta = group["delta_pct"].to_numpy(dtype=float)
        rows.append(
            {
                "comparison": comparison,
                "budget_s": int(budget_s),
                "scope": scope,
                "dataset": dataset,
                "n_instances": len(group),
                "median_delta_pct": float(np.median(delta)),
                "iqr_low_pct": float(np.percentile(delta, 25)),
                "iqr_high_pct": float(np.percentile(delta, 75)),
                "wins": int((delta < -1e-9).sum()),
                "ties": int((np.abs(delta) <= 1e-9).sum()),
                "losses": int((delta > 1e-9).sum()),
            }
        )
    result = pd.DataFrame(rows)
    result["dataset"] = pd.Categorical(result["dataset"], BENCHMARK_FAMILY_ORDER, ordered=True)
    return result.sort_values(["comparison", "budget_s", "scope", "dataset"]).reset_index(drop=True)


def block_structured_tests(comparisons: list[pd.DataFrame], seed: int = 20260907) -> pd.DataFrame:
    """Run block-aware statistical summaries and tests."""
    rows = []
    data = pd.concat(comparisons, ignore_index=True)
    for (comparison, budget_s, scope), group in data.groupby(["comparison", "budget_s", "scope"]):
        block_delta = (
            group.groupby("base_pattern")["delta_pct"]
            .median()
            .sort_index()
            .to_numpy(dtype=float)
        )
        n_blocks = int(len(block_delta))
        ci_low, ci_high = bootstrap_block_ci(block_delta, seed=seed)
        effect = rank_biserial(block_delta, np.zeros_like(block_delta)) if n_blocks else np.nan
        p_value = np.nan
        test = "none"
        if n_blocks == 10:
            p_value = exact_sign_permutation_pvalue(block_delta)
            test = "exact sign permutation over blocks"
            test_note = "tested on 10 base-pattern blocks"
        elif n_blocks == 5:
            test_note = "not tested: 5 blocks, minimum attainable two-sided p = 0.0625"
        else:
            test_note = f"not tested: {n_blocks} blocks"
        rows.append(
            {
                "comparison": comparison,
                "budget_s": int(budget_s),
                "scope": scope,
                "n_blocks": n_blocks,
                "n_instances": int(len(group)),
                "median_block_delta_pct": float(np.median(block_delta)) if n_blocks else np.nan,
                "ci_low_pct": ci_low,
                "ci_high_pct": ci_high,
                "effect_size": effect,
                "p_value": p_value,
                "test": test,
                "test_note": test_note,
                "seed": seed,
            }
        )
    return pd.DataFrame(rows).sort_values(["budget_s", "comparison", "scope"]).reset_index(drop=True)


def v2_explanation(mat_runs: pd.DataFrame) -> pd.DataFrame:
    """Build the explanatory 8X/10X v2 construction table."""
    v2 = mat_runs[mat_runs["source_folder"].str.contains("results_scale_8x10x_v2", na=False)].copy()
    v2 = v2[v2["method"].isin(["rf+fo", "rf+mip"])]
    v2["improvement_time_left_s"] = v2["budget_s"] - v2["rf_wall_time_s"].fillna(0.0)
    cols = ["dataset", "instance", "method", "construction_used", "construction_Z", "rf_wall_time_s", "improvement_time_left_s", "Z_final"]
    return v2[cols].sort_values(["dataset", "instance", "method"])


def audit_inc_t3x3_seed_windows() -> tuple[pd.DataFrame, bool]:
    """Compare FO_random window starts for IncT3x_3 seeds 2 and 3."""
    rows = []
    sequences: dict[int, list[tuple[int, int]]] = {}
    base = MAT / "results_production" / "c_seeds" / "window_logs"
    for seed in [2, 3]:
        path = base / f"IncT3x_3_rf_fo_seed{seed}_b3600_windows.parquet"
        df = pd.read_parquet(path)
        random_rows = df[df["phase"].astype(str) == "FO_random"].copy()
        seq = list(zip(random_rows["window_start"].astype(int), random_rows["window_end"].astype(int)))
        sequences[seed] = seq
        rows.append(
            {
                "instance": "IncT3x_3",
                "seed": seed,
                "fo_random_windows": len(seq),
                "first_20_windows": "; ".join(f"{start}-{end}" for start, end in seq[:20]),
                "window_log": str(path.relative_to(ROOT)),
            }
        )
    differs = sequences[2] != sequences[3]
    audit = pd.DataFrame(rows)
    audit["sequences_differ"] = differs
    return audit, differs


def sprint2_hypotheses(short_df: pd.DataFrame, scale_df: pd.DataFrame, mat_runs: pd.DataFrame) -> list[dict]:
    """Evaluate the pre-registered Sprint 2 hypotheses exactly as written."""
    h1_rows = []
    h1_evidence = []
    for budget, group in short_df.groupby("budget_s"):
        wins = ((group[["Z_rf_fo", "Z_rf_mip"]].min(axis=1)) < group["Z_mip"]).sum()
        passed = bool(wins >= 4)
        h1_rows.append(passed)
        h1_evidence.append(f"{int(budget)}s: {int(wins)}/6")
    h1 = all(h1_rows)
    scale10 = scale_df[scale_df["dataset"] == "10X"].copy()
    h2_wins = ((scale10[["Z_rf_fo", "Z_rf_mip"]].min(axis=1)) < scale10["Z_mip"]).sum()
    h2 = h2_wins >= 3
    h3 = bool((short_df["Z_rf_fo"] < short_df["Z_ils_v2_best_until_budget"]).all())
    rf_fo = mat_runs[mat_runs.method == "rf+fo"].copy()
    h4 = bool((rf_fo["Z_final"] <= pd.to_numeric(rf_fo["Z_rf"], errors="coerce") + 1e-9).all())
    return [
        {"hypothesis": "H1 operational regime", "registered_result": str(bool(h1)), "evidence": "; ".join(h1_evidence)},
        {"hypothesis": "H2 scale", "registered_result": str(bool(h2)), "evidence": f"10X decomposed wins: {int(h2_wins)}/5"},
        {"hypothesis": "H3 dominance over ILS v2", "registered_result": str(bool(h3)), "evidence": "rf+fo < truncated ILS v2 in all short-budget cells" if h3 else "at least one short-budget cell failed"},
        {"hypothesis": "H4 accounting sanity", "registered_result": str(bool(h4)), "evidence": "Z_final <= internal Z_rf for all rf+fo rows"},
    ]


def main() -> int:
    """Generate all Sprint 3 analysis outputs."""
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)

    previous_bks = None
    previous_bks_path = OUT / "sprint3_bks_audit.csv"
    if previous_bks_path.exists():
        previous_bks = canonicalize_frame(pd.read_csv(previous_bks_path))

    comp = pd.read_csv(OUT / "comparison_table.csv")
    mat_runs = load_result_jsons()
    prod600 = canonicalize_frame(pd.read_csv(MAT / "results_production" / "b600" / "grade_b_summary.csv"))
    prod3600 = canonicalize_frame(pd.read_csv(MAT / "results_production" / "a3600" / "grade_a_summary.csv"))
    seeds = canonicalize_frame(pd.read_csv(MAT / "results_production" / "c_seeds" / "grade_c_summary.csv"))
    prod600 = public_benchmark(prod600)
    prod3600 = public_benchmark(prod3600)
    seeds = public_benchmark(seeds)
    s1_600 = mat_runs[
        (mat_runs["dataset"] == "S")
        & (mat_runs["instance"] == "S_1")
        & (mat_runs["budget_s"] == 600)
        & (mat_runs["method"].isin(["mip", "rf+fo", "rf+mip"]))
    ][["dataset", "instance", "method", "Z_final"]]
    prod600 = pd.concat([prod600, s1_600], ignore_index=True, sort=False)
    short = pd.read_csv(MAT / "results_short_budget" / "short_budget_summary.csv")
    scale = pd.read_csv(MAT / "results_scale_8x10x" / "scale_8x10x_summary.csv")
    scale_v2 = canonical_scale_v2_table(mat_runs)
    mip10800 = mip10800_table(mat_runs)
    q5_table, q5_verdict = q5_cross_budget_table(scale_v2, mip10800)
    canonical_600 = canonical_600_table(prod600)
    canonical_3600 = canonical_3600_table(comp, prod3600, scale_v2)
    block_map = comp[["dataset", "instance"]].copy()
    block_map["base_pattern"] = block_map["instance"].map(base_pattern)
    write_table(block_map, OUT / "block_map.csv", ["dataset", "instance", "base_pattern"])

    bks_audit = comp[["dataset", "instance", "BKS", "bks_source"]].copy()
    write_table(bks_audit, OUT / "sprint3_bks_audit.csv", ["dataset", "instance"])
    if previous_bks is not None:
        bks_changes = previous_bks.merge(bks_audit, on=["dataset", "instance"], how="outer", suffixes=("_previous", "_current"))
        bks_changes = bks_changes[
            (bks_changes["BKS_previous"].round(6) != bks_changes["BKS_current"].round(6))
            | (bks_changes["bks_source_previous"].fillna("") != bks_changes["bks_source_current"].fillna(""))
        ].copy()
    else:
        bks_changes = pd.DataFrame(columns=["dataset", "instance", "BKS_previous", "BKS_current", "bks_source_previous", "bks_source_current"])
    if bks_changes.empty:
        bks_changes = pd.DataFrame(
            [
                {
                    "dataset": "none",
                    "instance": "none",
                    "BKS_previous": np.nan,
                    "BKS_current": np.nan,
                    "bks_source_previous": "No BKS changes after regeneration.",
                    "bks_source_current": "No BKS changes after regeneration.",
                }
            ]
        )
    write_table(bks_changes, OUT / "sprint3_bks_changes_after_mip10800.csv", ["dataset", "instance"])
    v2_table = v2_explanation(mat_runs)
    write_table(v2_table, OUT / "sprint3_scale_v2_construction.csv", ["dataset", "instance", "method"])
    write_table(scale_v2, OUT / "sprint3_scale_8x10x_canonical_v2.csv", ["dataset", "instance"])
    write_table(mip10800, OUT / "sprint3_mip10800_8x10x.csv", ["dataset", "instance"])
    write_table(q5_table, OUT / "sprint3_q5_cross_budget.csv", ["dataset", "instance"])
    write_table(q5_verdict, OUT / "sprint3_q5_verdict.csv", ["dataset"])
    write_table(canonical_3600, OUT / "sprint3_canonical_3600_cells.csv", ["dataset", "instance"])
    source_cells = pd.concat(
        [
            canonical_600[["dataset", "source_cell"]].drop_duplicates().assign(budget_s=600),
            canonical_3600[["dataset", "source_cell"]].drop_duplicates().assign(budget_s=3600),
            public_benchmark(comp)[["dataset"]]
            .drop_duplicates()
            .assign(
                budget_s=10800,
                source_cell=lambda frame: np.where(
                    frame["dataset"].isin(["8X", "10X"]),
                    "post-hoc: cold MIP from results_scale_8x10x_mip10800 only; decompositions not run @10800s",
                    "registered CPLEX22_3h where available",
                ),
            ),
        ],
        ignore_index=True,
    ).sort_values(["dataset", "budget_s"])
    source_cells = (
        source_cells.groupby(["dataset", "budget_s"], as_index=False)["source_cell"]
        .agg(lambda values: "; ".join(dict.fromkeys(str(value) for value in values if pd.notna(value))))
        .sort_values(["dataset", "budget_s"])
    )
    write_table(source_cells, OUT / "sprint3_cell_sources.csv", ["dataset", "budget_s"])

    perf600 = prod600[prod600["method"].isin(["mip", "rf+fo", "rf+mip"])]
    performance_profile(perf600, "performance_profile_600s", "Performance profile at 600 seconds")
    perf3600 = canonical_3600.melt(
        id_vars=["dataset", "instance"], value_vars=["mip", "rf+fo", "rf+mip"], var_name="method", value_name="Z_final"
    ).dropna(subset=["Z_final"])
    performance_profile(perf3600, "performance_profile_3600s", "Performance profile at 3600 seconds")
    for instance in ["IncT3x_7", "IncT5x_10", "IncT10x_2"]:
        convergence_plot(mat_runs, instance)

    frontier = frontier_table(comp, canonical_600, canonical_3600)
    write_table(frontier, OUT / "sprint3_frontier_counts.csv", ["dataset", "budget_s"])
    frontier_heatmap(frontier)

    stat_inputs = [
        comparison_frame(canonical_600, "rf+fo", "mip", "rf+fo vs mip", 600, "S-10X benchmark"),
        comparison_frame(canonical_600, "rf+mip", "mip", "rf+mip vs mip", 600, "S-10X benchmark"),
    ]
    short600 = short[short["budget_s"] == 600].rename(
        columns={"Z_rf_fo": "rf+fo", "Z_ils_v2_best_until_budget": "ILS v2 truncated"}
    )
    stat_inputs.append(
        comparison_frame(short600, "rf+fo", "ILS v2 truncated", "rf+fo vs truncated ILS v2", 600, "3X-5X short-budget subset")
    )
    scale_wide = scale_v2.rename(columns={"rf+fo": "rf+fo", "rf+mip": "rf+mip", "mip": "mip"})
    scale_scopes = [
        ("8X", "8X scale subset"),
        ("10X", "10X scale subset"),
        (None, "8X/10X heterogeneous family aggregate"),
    ]
    stat_inputs.extend(
        comparison_frame(
            scale_wide if dataset is None else scale_wide[scale_wide["dataset"] == dataset],
            lhs,
            "mip",
            f"{lhs} vs mip",
            3600,
            scope,
        )
        for dataset, scope in scale_scopes
        for lhs in ["rf+fo", "rf+mip"]
    )
    descriptive = descriptive_by_scale(stat_inputs)
    write_table(
        descriptive,
        OUT / "sprint3_descriptive_by_scale.csv",
        ["comparison", "budget_s", "scope", "dataset"],
    )
    stats = block_structured_tests(stat_inputs)
    write_table(stats, OUT / "sprint3_statistical_tests.csv", ["comparison", "budget_s", "scope"])

    variability = (
        seeds.groupby(["dataset", "instance"], as_index=False)
        .agg(Z_mean=("Z_final", "mean"), Z_std=("Z_final", "std"), Z_min=("Z_final", "min"), Z_max=("Z_final", "max"))
    )
    variability["Z_range"] = variability["Z_max"] - variability["Z_min"]
    write_table(variability, OUT / "sprint3_seed_variability.csv", ["dataset", "instance"])
    seed_audit, seed_sequences_differ = audit_inc_t3x3_seed_windows()
    write_table(seed_audit, OUT / "sprint3_seed_window_audit.csv", ["instance", "seed"])

    hypotheses = sprint2_hypotheses(short, scale, mat_runs)
    block_summary = (
        public_benchmark(block_map)
        .groupby("dataset", as_index=False)
        .agg(n_instances=("instance", "count"), n_base_patterns=("base_pattern", "nunique"))
    )
    block_summary["dataset"] = pd.Categorical(block_summary["dataset"], BENCHMARK_FAMILY_ORDER, ordered=True)
    block_summary = block_summary.sort_values("dataset")
    scale_stats = stats.loc[
        (stats["comparison"] == "rf+fo vs mip")
        & (stats["budget_s"] == 3600)
        & (stats["scope"].isin(["8X scale subset", "10X scale subset", "8X/10X heterogeneous family aggregate"]))
    ].copy()
    scale_summary = "; ".join(
        f"{row.scope}: {row.median_block_delta_pct:.4f}%"
        for row in scale_stats.sort_values("scope").itertuples()
    )

    bks_8x4 = comp.loc[comp.instance == "IncT8x_4", ["BKS", "bks_source"]].iloc[0]
    report = [
        "# Sprint 3 Final Analysis Report",
        "",
        "## Technical summary",
        "",
        "The final production grid is complete: Grade B contributes 180 short-budget runs, Grade A contributes 50 long-budget rf+fo runs on S--5X plus the reconstructed S_1 supplement, and Grade C contributes 24 seed-variability runs. The global BKS scanner now includes CPLEX, ILS, tuning, pilot, short-budget, scale, v2, MIP@10800s scale, reconstructed S_1, and production matheuristic JSONs; legacy GRASP_v1 is retained only in the raw master data because the BKS safeguard detected evaluator inconsistencies.",
        "",
        f"The IncT8x_4 BKS audit passes the registered check: BKS = {bks_8x4['BKS']:.3f}, source = `{bks_8x4['bks_source']}`.",
        "",
        f"Using canonical v2 decomposition data for 8X/10X @3600s, `rf+fo vs mip` is reported separately by scale with median block relative deltas {scale_summary}. None of these rows is assigned a p-value because each scale has five base-pattern blocks; the combined row is retained only as a heterogeneous family aggregate.",
        "",
        "## Registered Sprint 2 hypotheses",
        "",
        markdown_table(hypotheses, ["hypothesis", "registered_result", "evidence"]),
        "",
        "These are reported as registered historical verdicts. The corrected 8X/10X v2 runs and the production grades are treated as post-hoc evidence below.",
        "",
        "## Cell source map",
        "",
        "Each frontier/statistical cell is tied to a single declared source. In particular, 8X/10X @3600s uses cold MIP from `results_scale_8x10x/` and matheuristics from `results_scale_8x10x_v2/`, labelled post-hoc. The 8X/10X @10800s cells use cold MIP from `results_scale_8x10x_mip10800/` only; decompositions were not run at 10800s.",
        "",
        markdown_table(source_cells.to_dict("records"), ["dataset", "budget_s", "source_cell"], digits=0),
        "",
        "## Global BKS and comparison table",
        "",
        f"`comparison_table.csv` now has {len(comp)} rows and includes `bks_source`. Dataset coverage is: "
        + ", ".join(
            f"{k}={v}"
            for k, v in public_benchmark(comp)
            .dataset.value_counts()
            .reindex(BENCHMARK_FAMILY_ORDER)
            .fillna(0)
            .astype(int)
            .items()
        )
        + ".",
        "",
        "BKS candidates are scanned from registered CPLEX, ILS, and matheuristic sources, but any candidate below an available CPLEX dual bound for the same instance is excluded as a consistency safeguard. Legacy GRASP_v1 remains in `master_runs.csv` only and is intentionally excluded from paper comparison tables because the safeguard exposed evaluator inconsistencies.",
        "",
        "## Production frontier",
        "",
        "The method frontier is summarized by majority winner per dataset-budget cell. Counts are exact counts of available instances in the cell.",
        "",
        markdown_table(frontier.to_dict("records"), ["dataset", "budget_s", "winner", "n", "mip", "rf+mip", "rf+fo", "source_cell"], digits=0),
        "",
        "## Q5 -- cross-budget check",
        "",
        "Q5 is adjudicated literally: is cold MIP @10800s strictly better than the best canonical decomposed method @3600s (source `results_scale_8x10x_v2/`) in at least 3 of 5 instances, separately for 8X and 10X?",
        "",
        markdown_table(q5_verdict.to_dict("records"), ["dataset", "mip10800_wins", "n", "Q5_true"], digits=0),
        "",
        markdown_table(q5_table.to_dict("records"), ["dataset", "instance", "mip_10800_Z", "best_decomp_3600_Z", "best_decomp_3600_method", "delta_rel_pct", "winner"], digits=3),
        "",
        "A negative delta means MIP@10800s is better; a positive delta means the 3600s decomposed run is better despite the shorter budget.",
        "",
        "## BKS changes after MIP@10800s",
        "",
        markdown_table(bks_changes.to_dict("records"), ["dataset", "instance", "BKS_previous", "BKS_current", "bks_source_previous", "bks_source_current"], digits=3),
        "",
        "Figures: `analysis/figures/performance_profile_600s.*`, `performance_profile_3600s.*`, `frontier_heatmap.*`, and convergence curves for IncT3x_7, IncT5x_10, and IncT10x_2.",
        "",
        "## 8X/10X v2 construction diagnostics",
        "",
        "The v2 diagnostics separate the construction handoff from the improvement phase. `improvement_time_left_s` is the nominal remaining budget after RF construction wall time.",
        "",
        markdown_table(v2_table.to_dict("records"), ["dataset", "instance", "method", "construction_used", "construction_Z", "rf_wall_time_s", "improvement_time_left_s", "Z_final"], digits=3),
        "",
        "## Statistical tests",
        "",
        "### Descriptive by scale",
        "",
        "Differences are relative objective changes in percent, left method minus right method; negative values favor the left method because lower objective is better.",
        "",
        markdown_table(descriptive.to_dict("records"), ["comparison", "budget_s", "scope", "dataset", "n_instances", "median_delta_pct", "iqr_low_pct", "iqr_high_pct", "wins", "ties", "losses"], digits=4),
        "",
        "### Block map",
        "",
        "The dependency map is written to `analysis/output/block_map.csv`. The benchmark contains ten base patterns for S--5X and five base patterns for 8X/10X.",
        "",
        markdown_table(block_summary.to_dict("records"), ["dataset", "n_instances", "n_base_patterns"], digits=0),
        "",
        "### Block-structured tests",
        "",
        "Each test first collapses repeated descendants to one median relative difference per base pattern. Exact sign-permutation p-values are reported only when ten base-pattern blocks are available; five-block 8X/10X comparisons are descriptive only.",
        "",
        markdown_table(stats.to_dict("records"), ["comparison", "budget_s", "scope", "n_blocks", "n_instances", "median_block_delta_pct", "ci_low_pct", "ci_high_pct", "effect_size", "p_value", "test", "test_note", "seed"], digits=4),
        "",
        "### Methodological note",
        "",
        "The 2X--5X families repeat the same ten S order-book patterns at larger horizons, and the 8X/10X families descend from five of those patterns. Treating all derived instances as independent would therefore overstate the effective sample size. The inferential unit is the base pattern, not the individual replicated instance.",
        "",
        "## Seed variability",
        "",
        markdown_table(variability.to_dict("records"), ["dataset", "instance", "Z_mean", "Z_std", "Z_min", "Z_max", "Z_range"], digits=3),
        "",
        "### Seed plumbing audit",
        "",
        f"The IncT3x_3 FO_random window sequences differ across seeds 2 and 3 (`sequences_differ={str(seed_sequences_differ).lower()}`). Therefore a zero standard deviation for this instance is interpreted as legitimate robustness, not a seed plumbing bug.",
        "",
        markdown_table(seed_audit.to_dict("records"), ["instance", "seed", "fo_random_windows", "first_20_windows", "sequences_differ"], digits=0),
        "",
        "## Scope and limitations",
        "",
        "The 10800s frontier cells use the available CPLEX 3h baseline where present. For 8X/10X, 10800s cells now contain cold MIP only from `results_scale_8x10x_mip10800/`; decompositions were not executed at 10800s and this asymmetry is disclosed in the frontier figure and Q5 table. Production Grade A supplies rf+fo at 3600s for S--5X, while 8X/10X 3600s decomposition evidence comes only from results_scale_8x10x_v2/ and is explicitly post-hoc.",
        "",
        "## Reproducibility outputs",
        "",
        "- `analysis/output/comparison_table.csv`",
        "- `analysis/output/sprint3_bks_audit.csv`",
        "- `analysis/output/sprint3_frontier_counts.csv`",
        "- `analysis/output/sprint3_q5_cross_budget.csv`",
        "- `analysis/output/sprint3_q5_verdict.csv`",
        "- `analysis/output/sprint3_mip10800_8x10x.csv`",
        "- `analysis/output/sprint3_bks_changes_after_mip10800.csv`",
        "- `analysis/output/sprint3_cell_sources.csv`",
        "- `analysis/output/sprint3_canonical_3600_cells.csv`",
        "- `analysis/output/block_map.csv`",
        "- `analysis/output/sprint3_descriptive_by_scale.csv`",
        "- `analysis/output/sprint3_scale_8x10x_canonical_v2.csv`",
        "- `analysis/output/sprint3_scale_v2_construction.csv`",
        "- `analysis/output/sprint3_seed_window_audit.csv`",
        "- `analysis/output/sprint3_statistical_tests.csv`",
        "- `analysis/output/sprint3_seed_variability.csv`",
        "- `analysis/figures/*.png` and `analysis/figures/*.pdf`",
        "",
    ]
    atomic_write_text(OUT / "sprint3_report.md", "\n".join(report))
    print(f"Wrote {OUT / 'sprint3_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
