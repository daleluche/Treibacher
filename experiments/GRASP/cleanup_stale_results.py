"""
Delete all GRASP result JSONs so the full campaign starts from scratch.
Run this once before launching run_grasp_all.py for the paper results.
"""
from pathlib import Path
HERE = Path(__file__).parent
deleted = 0
for f in HERE.rglob("*_run??.json"):
    f.unlink()
    print(f"  deleted {f.relative_to(HERE)}")
    deleted += 1
for f in HERE.rglob("*_summary.json"):
    f.unlink()
    print(f"  deleted {f.relative_to(HERE)}")
    deleted += 1
csv = HERE / "results_summary.csv"
if csv.exists():
    csv.unlink()
    print("  deleted results_summary.csv")
    deleted += 1
print(f"\nTotal: {deleted} files removed. Ready for a fresh run.")
