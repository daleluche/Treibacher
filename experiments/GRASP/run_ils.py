"""
run_ils.py — Launcher for run_all_ils batch runner.

Usage:
    python run_ils.py [options]

This thin wrapper imports run_all_ils and calls main(), bypassing any
stale .pyc files that might suppress the __main__ block.

Examples:
    # Full production run (50 instances x 10 runs x 30 min)
    python run_ils.py

    # Quick test on a single dataset
    python run_ils.py --datasets 2X --n_runs 2 --time 60

    # Resume an interrupted run
    python run_ils.py --resume

    # Run only specific instances
    python run_ils.py --instances Ale_1 Ale_2 IncT2X_6
"""
import sys
import os

# Ensure the GRASP directory is on the path so run_all_ils and
# grasp_ils_psp can be found regardless of the working directory.
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from run_all_ils import main

if __name__ == "__main__":
    main()
