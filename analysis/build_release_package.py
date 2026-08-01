"""Build the public PSP benchmark release package."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release"
ZIP_PATH = RELEASE / "treibacher_psp_benchmark_v1.zip"
DATASETS = ["Real", "2X", "3X", "4X", "5X", "8X", "10X"]

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.matheuristics.psp_instance import load_instance


def reset_release() -> None:
    """Create a clean release directory."""
    if RELEASE.exists():
        shutil.rmtree(RELEASE)
    RELEASE.mkdir(parents=True)


def rel(path: Path) -> Path:
    """Return a path relative to the repository root."""
    return path.resolve().relative_to(ROOT)


def copy_file(src: Path, dst: Path) -> None:
    """Copy one file, creating parents."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def write_instances() -> None:
    """Write instance data in open JSON/CSV form and copy GAMSPy scripts."""
    rows_meta = []
    production_rows = []
    demand_rows = []
    for dataset in DATASETS:
        for path in sorted((ROOT / "experiments" / "GAMSPy" / dataset).glob("*.py")):
            inst = load_instance(path)
            copy_file(path, RELEASE / "instances" / "gamspy_py" / dataset / path.name)
            json_data = {
                "name": inst.name,
                "dataset": inst.dataset,
                "T": inst.T,
                "J": inst.J,
                "I": inst.I,
                "products": inst.products,
                "A_records": [
                    {"product": inst.products[i], "process": j + 1, "value": float(inst.A[i, j])}
                    for i in range(inst.I)
                    for j in range(inst.J)
                    if abs(float(inst.A[i, j])) > 0.0
                ],
                "D_records": [
                    {"product": inst.products[i], "period": t + 1, "value": float(inst.D[i, t])}
                    for i in range(inst.I)
                    for t in range(inst.T)
                    if abs(float(inst.D[i, t])) > 0.0
                ],
            }
            out_json = RELEASE / "instances" / "json" / dataset / f"{inst.name}.json"
            out_json.parent.mkdir(parents=True, exist_ok=True)
            out_json.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")
            rows_meta.append(
                {
                    "dataset": inst.dataset,
                    "instance": inst.name,
                    "T": inst.T,
                    "J": inst.J,
                    "I": inst.I,
                    "binary_variables": inst.J * inst.T,
                    "continuous_variables": 2 * inst.I * inst.T + 1,
                    "constraints": inst.I * inst.T + inst.T + 1,
                    "source_py": str(Path("instances/gamspy_py") / dataset / path.name),
                    "source_json": str(Path("instances/json") / dataset / f"{inst.name}.json"),
                }
            )
            for rec in json_data["A_records"]:
                production_rows.append({"dataset": dataset, "instance": inst.name, **rec})
            for rec in json_data["D_records"]:
                demand_rows.append({"dataset": dataset, "instance": inst.name, **rec})

    pd.DataFrame(rows_meta).to_csv(RELEASE / "instances" / "instance_metadata.csv", index=False)
    pd.DataFrame(production_rows).to_csv(RELEASE / "instances" / "production_matrix_long.csv", index=False)
    pd.DataFrame(demand_rows).to_csv(RELEASE / "instances" / "demand_long.csv", index=False)


def load_schedule_from_result(source_path: str) -> list[dict]:
    """Extract a period/process schedule from a result JSON."""
    path = ROOT / source_path
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data.get("scheduling"), list):
        return data["scheduling"]
    if isinstance(data.get("schedule"), list):
        return [
            {"period": period + 1, "process": int(process)}
            for period, process in enumerate(data["schedule"])
            if int(process) > 0
        ]
    return []


def write_solution_and_bound_files() -> None:
    """Write BKS, schedules, and dual-bound files."""
    comp = pd.read_csv(ROOT / "analysis" / "output" / "comparison_table.csv")
    bks_rows = []
    bound_rows = []
    schedules = {}
    for _, row in comp.iterrows():
        source = str(row.get("bks_source", ""))
        source_path = ""
        if " | " in source:
            source_path = source.split(" | ")[-1]
        bks_rows.append(
            {
                "dataset": row["dataset"],
                "instance": row["instance"],
                "BKS": row["BKS"],
                "bks_source": row["bks_source"],
                "source_path": source_path,
            }
        )
        schedules[row["instance"]] = {
            "dataset": row["dataset"],
            "BKS": row["BKS"],
            "source_path": source_path,
            "schedule": load_schedule_from_result(source_path) if source_path else [],
        }
        bound_rows.append(
            {
                "dataset": row["dataset"],
                "instance": row["instance"],
                "cplex_bound": row.get("cplex_bound"),
                "cplex_gap_pct": row.get("cplex_gap_pct"),
                "cplex_mip_10800_bound": row.get("cplex_mip_10800_bound"),
                "cplex_mip_10800_gap_pct": row.get("cplex_mip_10800_gap_pct"),
            }
        )
    sol_dir = RELEASE / "solutions"
    sol_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(bks_rows).to_csv(sol_dir / "best_known_solutions.csv", index=False)
    pd.DataFrame(bound_rows).to_csv(sol_dir / "dual_bounds.csv", index=False)
    (sol_dir / "best_known_schedules.json").write_text(
        json.dumps(schedules, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def copy_analysis_outputs() -> None:
    """Copy analysis CSV/Markdown outputs."""
    out_dir = RELEASE / "analysis_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted((ROOT / "analysis" / "output").glob("*")):
        if path.is_file() and path.suffix.lower() in {".csv", ".md"}:
            copy_file(path, out_dir / path.name)


def copy_gamma_variant() -> None:
    """Copy gamma=0 scripts and result files."""
    src = ROOT / "experiments" / "GAMSPy" / "variant_gamma0"
    dst = RELEASE / "gamma0_variant"
    if src.exists():
        shutil.copytree(src, dst)


def copy_trajectories() -> None:
    """Copy per-run trajectory JSON files for heuristic and matheuristic methods."""
    traj_dir = RELEASE / "trajectories"
    for rel_glob in [
        "experiments/GRASP/results_ils_v2/*.json",
        "experiments/GRASP/results_ils/*.json",
        "experiments/matheuristics/results_pilot/*.json",
        "experiments/matheuristics/results_tuning/*.json",
        "experiments/matheuristics/results_short_budget/*.json",
        "experiments/matheuristics/results_short_budget_v2/*.json",
        "experiments/matheuristics/results_scale_8x10x/*.json",
        "experiments/matheuristics/results_scale_8x10x_v2/*.json",
        "experiments/matheuristics/results_scale_8x10x_mip10800/*.json",
        "experiments/matheuristics/results_production/b600/*.json",
        "experiments/matheuristics/results_production/a3600/*.json",
        "experiments/matheuristics/results_production/c_seeds/*.json",
    ]:
        for path in sorted(ROOT.glob(rel_glob)):
            copy_file(path, traj_dir / rel(path))


def copy_window_logs() -> None:
    """Copy matheuristic per-window logs."""
    dst_root = RELEASE / "window_logs"
    for directory in (ROOT / "experiments" / "matheuristics").rglob("window_logs"):
        for path in sorted(directory.glob("*")):
            if path.is_file() and path.suffix.lower() in {".parquet", ".csv"}:
                copy_file(path, dst_root / rel(path))


def write_license() -> None:
    """Write the release license notice."""
    text = """# License

Data files in this release are provided under the Creative Commons Attribution 4.0
International License (CC BY 4.0).

Code files included for reproducibility are provided under the MIT License.

This release contains anonymized benchmark instances derived from randomized demand
profiles. It does not reproduce the plant's real order book.
"""
    (RELEASE / "LICENSE").write_text(text, encoding="utf-8")


def write_readme() -> None:
    """Write the release README."""
    text = """# PSP Electrofused-Grains Benchmark Release v1

This package accompanies the PSP computational study. It contains the 60 benchmark
instances, best-known solutions, dual bounds, run trajectories, window logs, analysis
outputs, and the controlled `gamma=0` variant.

## Contents

- `instances/gamspy_py/`: original GAMSPy instance scripts.
- `instances/json/`: open JSON representation of each instance.
- `instances/instance_metadata.csv`: dimensions and source paths.
- `instances/production_matrix_long.csv`: nonzero production coefficients `(instance, product, process, value)`.
- `instances/demand_long.csv`: nonzero demand records `(instance, product, period, value)`.
- `solutions/best_known_solutions.csv`: BKS value and source.
- `solutions/best_known_schedules.json`: schedule associated with each BKS source when available.
- `solutions/dual_bounds.csv`: available CPLEX dual bounds and gaps.
- `trajectories/`: per-run JSON outputs for ILS and matheuristic experiments.
- `window_logs/`: per-window matheuristic instrumentation logs.
- `analysis_output/`: CSV and Markdown outputs used to build manuscript tables and figures.
- `gamma0_variant/`: scripts and results for the controlled `gamma=0` experiment.

## Reproducing Tables and Figures

From the repository root, rebuild the master analysis with:

```bash
python analysis/build_master_dataset.py
python analysis/compute_gaps.py
python analysis/gamma_effect.py
python analysis/make_paper_tables.py
```

Sprint 3 figures and frontier tables are generated by the Sprint 3 analysis pipeline
included in `analysis/`.

## Software and Hardware Provenance

Run JSON files include solver version, thread settings, hardware fields, random seeds,
wall-clock budgets, and source paths where available. The production campaign used CPLEX
22.1.2 through GAMSPy with explicit `threads=0`.

## Anonymization

The instances are derived from randomized and horizon-replicated demand profiles. No
released instance reproduces the real commercial order book. Product names are technical
item labels retained to preserve benchmark structure.

## Licensing

Data are CC BY 4.0; code is MIT. See `LICENSE`.
"""
    (RELEASE / "README.md").write_text(text, encoding="utf-8")


def write_checksums() -> None:
    """Write SHA-256 checksums for all release files except the final zip."""
    rows = []
    for path in sorted(RELEASE.rglob("*")):
        if not path.is_file() or path == ZIP_PATH:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append((digest, path.relative_to(RELEASE).as_posix()))
    with (RELEASE / "checksums.sha256").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=" ")
        for digest, name in rows:
            writer.writerow([digest, name])


def sanitize_release_texts() -> None:
    """Remove local paths and legacy company/model identifiers from text files."""
    replacements = {
        str(ROOT): "<REPO_ROOT>",
        str(ROOT).replace("\\", "\\\\"): "<REPO_ROOT>",
        "D:\\\\GitHub\\\\Treibacher": "<REPO_ROOT>",
        "D:\\GitHub\\Treibacher": "<REPO_ROOT>",
        "ALCOA": "PSP_MODEL",
    }
    text_suffixes = {".py", ".json", ".csv", ".md", ".txt", ".log", ".sha256", ".bib", ".tex", ".yml", ".yaml"}
    for path in RELEASE.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in text_suffixes:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new_text = text
        for old, new in replacements.items():
            new_text = new_text.replace(old, new)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")


def create_zip() -> None:
    """Create the final release zip."""
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(RELEASE.rglob("*")):
            if path.is_file() and path != ZIP_PATH:
                zf.write(path, path.relative_to(RELEASE).as_posix())


def main() -> int:
    """Build the full release package."""
    reset_release()
    write_instances()
    write_solution_and_bound_files()
    copy_analysis_outputs()
    copy_gamma_variant()
    copy_trajectories()
    copy_window_logs()
    write_license()
    write_readme()
    sanitize_release_texts()
    write_checksums()
    create_zip()
    print(f"Release written to {RELEASE}")
    print(f"Zip written to {ZIP_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
