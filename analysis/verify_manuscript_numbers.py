"""Verify manuscript numbers against versioned analysis artifacts.

The script intentionally checks the subset of manuscript claims that can be
recomputed mechanically from repository artifacts. Expected values are declared
here so changes in CSV/JSON outputs fail loudly instead of silently drifting into
the paper.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis" / "output"
MAT = ROOT / "experiments" / "matheuristics"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.matheuristics.psp_instance import load_instance


TOL = 1e-3


def fail(message: str) -> None:
    """Raise an assertion with a concise message."""
    raise AssertionError(message)


def assert_close(label: str, observed: float, expected: float, tol: float = TOL) -> None:
    """Assert that two floating-point values match within tolerance."""
    if observed is None or pd.isna(observed):
        fail(f"{label}: observed value is missing; expected {expected}")
    if abs(float(observed) - expected) > tol:
        fail(f"{label}: observed {observed}, expected {expected} (tol={tol})")


def assert_equal(label: str, observed: object, expected: object) -> None:
    """Assert exact equality."""
    if observed != expected:
        fail(f"{label}: observed {observed!r}, expected {expected!r}")


def read_json(path: Path) -> dict:
    """Read a JSON artifact."""
    return json.loads(path.read_text(encoding="utf-8"))


def citation_keys() -> tuple[set[str], set[str]]:
    """Return BibTeX keys and manuscript citation keys."""
    bib = (ROOT / "paper" / "references.bib").read_text(encoding="utf-8")
    entries = set(re.findall(r"@\w+\s*\{\s*([^,\s]+)", bib))
    tex = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in [ROOT / "paper" / "main.tex", *sorted((ROOT / "paper" / "sections").glob("*.tex"))]
    )
    cited: set[str] = set()
    pattern = re.compile(r"\\cite\w*\s*(?:\[[^\]]*\]\s*){0,2}\{([^}]*)\}")
    for match in pattern.finditer(tex):
        cited.update(key.strip() for key in match.group(1).split(",") if key.strip())
    return entries, cited


def verify_bibliography() -> None:
    """Verify the final bibliography size and cited-only invariant."""
    entries, cited = citation_keys()
    assert_equal("bibliography entries", len(entries), 48)
    assert_equal("uncited bibliography entries", sorted(entries - cited), [])
    assert_equal("missing bibliography entries", sorted(cited - entries), [])


def verify_instance_dimensions() -> None:
    """Verify family sizes, horizons, and model dimensions."""
    families = {
        "Real order book": (ROOT / "experiments" / "GAMSPy" / "S", ["REAL_1.py"], 1, 19),
        "S": (ROOT / "experiments" / "GAMSPy" / "S", [f"S_{i}.py" for i in range(1, 11)], 10, 19),
        "2X": (ROOT / "experiments" / "GAMSPy" / "2X", [f"IncT2X_{i}.py" for i in range(1, 11)], 10, 38),
        "3X": (ROOT / "experiments" / "GAMSPy" / "3X", [f"IncT3x_{i}.py" for i in range(1, 11)], 10, 57),
        "4X": (ROOT / "experiments" / "GAMSPy" / "4X", [f"IncT4x_{i}.py" for i in range(1, 11)], 10, 76),
        "5X": (ROOT / "experiments" / "GAMSPy" / "5X", [f"IncT5x_{i}.py" for i in range(1, 11)], 10, 95),
        "8X": (ROOT / "experiments" / "GAMSPy" / "8X", [f"IncT8x_{i}.py" for i in range(2, 7)], 5, 152),
        "10X": (ROOT / "experiments" / "GAMSPy" / "10X", [f"IncT10x_{i}.py" for i in range(2, 7)], 5, 190),
    }
    derived_count = 0
    for label, (folder, names, expected_n, expected_t) in families.items():
        assert_equal(f"{label} instance count", len(names), expected_n)
        for name in names:
            path = folder / name
            if not path.exists():
                fail(f"{label}: missing instance file {path}")
            inst = load_instance(path)
            assert_equal(f"{path.name} T", inst.T, expected_t)
            assert_equal(f"{path.name} J", inst.J, 159)
            assert_equal(f"{path.name} I", inst.I, 50)
        if label != "Real order book":
            derived_count += len(names)
    assert_equal("derived public benchmark instances", derived_count, 60)
    assert_equal("largest binary-variable count", 159 * 190, 30210)


def verify_real_order_book() -> None:
    """Verify the reconstructed real order book cross-check."""
    data = read_json(MAT / "results_production" / "real" / "REAL_1_mip_seed1_b10800.json")
    assert_close("REAL_1 shortage", data["shortage"], 10475.0)
    assert_close("REAL_1 excess", data["excess"], 967625.0)
    assert_close("REAL_1 objective", data["Z_final"], 11442.625)
    assert_close("REAL_1 solve time reported in artifact", data["wall_time_total"], 4.82, tol=0.1)
    inst = load_instance(ROOT / "experiments" / "GAMSPy" / "S" / "REAL_1.py")
    assert_equal("REAL_1 nonzero demand products", int((inst.D.sum(axis=1) > 0).sum()), 36)
    assert_close("REAL_1 total demand", float(inst.D.sum()), 279400.0)


def verify_cplex_gap_summary() -> None:
    """Verify solver-optimality and gap claims by family."""
    expected = {
        "S": (10, 0.0),
        "2X": (10, 0.0),
        "3X": (0, 1.689708),
        "4X": (0, 3.911303),
        "5X": (0, 7.206118),
        "8X": (0, 10.944417),
        "10X": (0, 18.669708),
    }
    df = pd.read_csv(OUT / "comparison_by_dataset.csv").set_index("dataset")
    for dataset, (n_opt, mean_gap) in expected.items():
        assert_close(f"{dataset} CPLEX optimal count", df.loc[dataset, "n_cplex_optimal"], n_opt)
        assert_close(f"{dataset} CPLEX mean gap", df.loc[dataset, "cplex_gap_mean_pct"], mean_gap)


def verify_ils_baseline() -> None:
    """Verify ILS-v2 mean deficit over CPLEX primal by family."""
    expected = {
        "S": 0.537680,
        "2X": 2.573469,
        "3X": 10.436313,
        "4X": 16.390512,
        "5X": 23.884445,
    }
    df = pd.read_csv(OUT / "comparison_by_dataset.csv").set_index("dataset")
    for dataset, value in expected.items():
        assert_close(f"{dataset} ILS-v2 mean gap vs CPLEX primal", df.loc[dataset, "gap_ils2_vs_primal_mean_pct"], value)


def verify_gamma_effect() -> None:
    """Verify the gamma-effect and 2X trade-off claims."""
    expected = {
        "2X": (10, 10, 0.0, 0.0, 24.85616, 666.46999, 13.121963, 63780.1724),
        "3X": (10, 10, 0.0, 1.689708, 47.70209, 10846.33321, 18.878087, 66812.4813),
        "4X": (10, 10, 0.0, 3.911303, 114.23468, 10831.93807, 24.082129, 69841.9165),
        "5X": (10, 10, 0.0, 7.206118, 178.17722, 10821.60502, 29.241352, 73402.6709),
    }
    summary = pd.read_csv(OUT / "gamma_effect_by_set.csv").set_index("dataset")
    detail = pd.read_csv(OUT / "gamma_effect.csv")
    for dataset, (n, opt_gamma0, gap0, gap001, time0, time001, delta_med, z001) in expected.items():
        assert_equal(f"{dataset} gamma rows", int(summary.loc[dataset, "n"]), n)
        opt = detail[
            (detail["dataset"] == dataset)
            & (detail["status_gamma0"] == "OptimalGlobal")
            & (detail["gap_gamma0_pct"].abs() <= 1e-6)
        ]
        assert_equal(f"{dataset} gamma=0 proven optima", len(opt), opt_gamma0)
        assert_close(f"{dataset} gamma=0 mean gap", summary.loc[dataset, "gamma0_gap_mean_pct"], gap0)
        assert_close(f"{dataset} gamma=0.001 mean gap", summary.loc[dataset, "gamma0001_gap_mean_pct"], gap001)
        assert_close(f"{dataset} gamma=0 mean time", summary.loc[dataset, "gamma0_time_mean_s"], time0, tol=0.02)
        assert_close(f"{dataset} gamma=0.001 mean time", summary.loc[dataset, "gamma0001_time_mean_s"], time001, tol=0.02)
        assert_close(f"{dataset} gamma median objective share", summary.loc[dataset, "delta_pct_median"], delta_med)
        assert_close(f"{dataset} gamma=0.001 mean objective", summary.loc[dataset, "Z_gamma0001_mean"], z001, tol=0.1)
    trade = pd.read_csv(OUT / "gamma_tradeoff_2x.csv")
    median = trade[trade["instance"] == "MEDIAN"].iloc[0]
    aggregate = trade[trade["instance"] == "AGGREGATE"].iloc[0]
    increases = trade[trade["instance"].str.startswith("IncT2X_") & (trade["delta_shortage"] > 0)]
    assert_equal("2X instances with higher backlog under gamma=0.001", len(increases), 7)
    assert_close("2X median backlog increase pct", median["delta_shortage_pct"], 0.122351)
    assert_close("2X max backlog increase pct", trade[trade["instance"].str.startswith("IncT2X_")]["delta_shortage_pct"].max(), 1.943378)
    assert_close("2X median excess reduction pct", median["excess_reduction_pct"], 34.337531)
    assert_close("2X aggregate extra backlog", aggregate["delta_shortage"], 1836.0)
    assert_close("2X aggregate excess reduction", aggregate["excess_reduction"], 26256839.0)


def verify_sprint3_statistics() -> None:
    """Verify block-statistical and frontier claims."""
    stats = pd.read_csv(OUT / "sprint3_statistical_tests.csv")
    descriptive = pd.read_csv(OUT / "sprint3_descriptive_by_scale.csv")
    q5 = pd.read_csv(OUT / "sprint3_q5_verdict.csv").set_index("dataset")
    counts = pd.read_csv(OUT / "sprint3_frontier_counts.csv")

    def stat_row(comparison: str, budget: int, scope: str) -> pd.Series:
        rows = stats[
            (stats["comparison"] == comparison)
            & (stats["budget_s"] == budget)
            & (stats["scope"] == scope)
        ]
        if len(rows) != 1:
            fail(f"Expected one stats row for {comparison}, {budget}, {scope}; observed {len(rows)}")
        return rows.iloc[0]

    row = stat_row("rf+fo vs mip", 600, "S-10X benchmark")
    assert_close("600s rf+fo vs mip median block delta", row["median_block_delta_pct"], 0.135711)
    assert_close("600s rf+fo vs mip p-value", row["p_value"], 0.046875)
    row = stat_row("rf+fo vs truncated ILS v2", 600, "3X-5X short-budget subset")
    assert_close("600s rf+fo vs ILS median block delta", row["median_block_delta_pct"], -25.666359)
    row = stat_row("rf+fo vs mip", 3600, "8X scale subset")
    assert_close("8X 3600 rf+fo median", row["median_block_delta_pct"], 1.217222)
    assert_equal("8X 3600 p-value omitted", bool(pd.isna(row["p_value"])), True)
    row = stat_row("rf+fo vs mip", 3600, "10X scale subset")
    assert_close("10X 3600 rf+fo median", row["median_block_delta_pct"], -13.894392)
    assert_equal("10X 3600 p-value omitted", bool(pd.isna(row["p_value"])), True)
    row = stat_row("rf+mip vs mip", 3600, "8X scale subset")
    assert_close("8X 3600 rf+mip median", row["median_block_delta_pct"], -2.957130)
    row = stat_row("rf+mip vs mip", 3600, "10X scale subset")
    assert_close("10X 3600 rf+mip median", row["median_block_delta_pct"], 26.296797)

    row = descriptive[
        (descriptive["comparison"] == "rf+fo vs mip")
        & (descriptive["budget_s"] == 600)
        & (descriptive["dataset"] == "10X")
    ].iloc[0]
    assert_close("10X 600 rf+fo median", row["median_delta_pct"], -37.832649)
    assert_equal("10X 600 rf+fo wins", int(row["wins"]), 4)
    row = descriptive[
        (descriptive["comparison"] == "rf+mip vs mip")
        & (descriptive["budget_s"] == 600)
        & (descriptive["dataset"] == "8X")
    ].iloc[0]
    assert_close("8X 600 rf+mip median", row["median_delta_pct"], -5.996700)
    assert_equal("8X 600 rf+mip wins", int(row["wins"]), 3)

    assert_equal("Q5 8X true", bool(q5.loc["8X", "Q5_true"]), True)
    assert_equal("Q5 8X wins", int(q5.loc["8X", "mip10800_wins"]), 4)
    assert_equal("Q5 10X true", bool(q5.loc["10X", "Q5_true"]), True)
    assert_equal("Q5 10X wins", int(q5.loc["10X", "mip10800_wins"]), 3)

    winners = {
        ("8X", 600): ("rf+mip", 3, 1, 1),
        ("8X", 3600): ("rf+mip", 3, 1, 1),
        ("8X", 10800): ("mip", 0, 5, 0),
        ("10X", 600): ("rf+fo", 0, 1, 4),
        ("10X", 3600): ("rf+fo", 1, 1, 3),
        ("10X", 10800): ("mip", 0, 5, 0),
    }
    for (dataset, budget), (winner, rf_mip, mip, rf_fo) in winners.items():
        row = counts[(counts["dataset"] == dataset) & (counts["budget_s"] == budget)].iloc[0]
        assert_equal(f"{dataset} {budget} winner", row["winner"], winner)
        assert_equal(f"{dataset} {budget} rf+mip wins", int(row["rf+mip"]), rf_mip)
        assert_equal(f"{dataset} {budget} mip wins", int(row["mip"]), mip)
        assert_equal(f"{dataset} {budget} rf+fo wins", int(row["rf+fo"]), rf_fo)


def verify_scale_and_q5_values() -> None:
    """Verify selected extreme-scale values quoted in the manuscript."""
    scale = pd.read_csv(OUT / "sprint3_scale_8x10x_canonical_v2.csv").set_index(["dataset", "instance"])
    q5 = pd.read_csv(OUT / "sprint3_q5_cross_budget.csv").set_index(["dataset", "instance"])
    assert_close("IncT10x_4 rf+mip @3600", scale.loc[("10X", "IncT10x_4"), "rf+mip"], 376198.080, tol=0.01)
    assert_close("IncT10x_4 rf+fo @3600", scale.loc[("10X", "IncT10x_4"), "rf+fo"], 172982.609, tol=0.01)
    assert_close("IncT10x_2 Q5 decomp lead", q5.loc[("10X", "IncT10x_2"), "delta_rel_pct"], 14.535243)
    assert_close("IncT10x_6 Q5 decomp lead", q5.loc[("10X", "IncT10x_6"), "delta_rel_pct"], 2.069941)


def main() -> int:
    """Run all checks."""
    checks = [
        verify_bibliography,
        verify_instance_dimensions,
        verify_real_order_book,
        verify_cplex_gap_summary,
        verify_ils_baseline,
        verify_gamma_effect,
        verify_sprint3_statistics,
        verify_scale_and_q5_values,
    ]
    for check in checks:
        check()
        print(f"OK {check.__name__}")
    print("ALL MANUSCRIPT NUMBER CHECKS PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
