"""Regression tests for public-release scoping and scanners."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from analysis import build_release_package
from analysis.release_scope import canonical_instance_name, is_private_instance_label, is_public_record

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "release_public"))
import verify_release  # noqa: E402


def test_ale1_scope_does_not_exclude_ale10() -> None:
    """The legacy Ale_1 case is excluded without catching Ale_10."""
    assert is_private_instance_label("Ale_1")
    assert is_private_instance_label("Ale_1_run01")
    assert is_private_instance_label("foo/Ale_1/bar")
    assert not is_private_instance_label("Ale_10")
    assert canonical_instance_name("Ale_10") == "S_10"


def test_scanner_detects_json_escaped_absolute_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON-escaped Windows paths must be rejected by the release scanner."""
    monkeypatch.setattr(build_release_package, "DIST", tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps({"window_log_path": r"D:\GitHub\Treibacher\window_logs\a.parquet"}),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError):
        build_release_package.scan_dist_content()

    bad.write_text(
        json.dumps({"window_log_path": "results/window_logs/a.parquet"}),
        encoding="utf-8",
    )
    build_release_package.scan_dist_content()


def test_public_record_rejects_unknown_dataset() -> None:
    """Structured records may only declare authorized public datasets."""
    assert is_public_record({"dataset": "S", "instance": "S_1"})
    assert not is_public_record({"dataset": "Synthetic", "instance": "synthetic_tiny"})
    assert not is_public_record({"dataset": "Unexpected", "instance": "X_1"})


def test_window_log_metadata_validation_cases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Window-log metadata must be equivalent to an existing package-relative file."""
    monkeypatch.setattr(build_release_package, "DIST", tmp_path)
    log = tmp_path / "results" / "experiments" / "matheuristics" / "window_logs" / "ok.parquet"
    log.parent.mkdir(parents=True)
    log.write_bytes(b"not a real parquet for metadata-only validation")
    result = tmp_path / "results" / "good.json"
    result.parent.mkdir(parents=True, exist_ok=True)
    result.write_text(
        json.dumps({"window_log_path": "results/experiments/matheuristics/window_logs/ok.parquet", "window_log_included": True}),
        encoding="utf-8",
    )
    assert build_release_package.validate_window_log_metadata()["included"] == 1

    result.write_text(json.dumps({"window_log_path": None, "window_log_included": False}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Unreferenced"):
        build_release_package.validate_window_log_metadata()

    log.unlink()
    assert build_release_package.validate_window_log_metadata()["missing"] == 1

    result.write_text(json.dumps({"window_log_path": None, "window_log_included": True}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Invalid included"):
        build_release_package.validate_window_log_metadata()

    result.write_text(json.dumps({"window_log_path": "results/missing.parquet", "window_log_included": False}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="keeps a path"):
        build_release_package.validate_window_log_metadata()

    result.write_text(json.dumps({"window_log_path": "../window_logs/ok.parquet", "window_log_included": True}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Invalid included"):
        build_release_package.validate_window_log_metadata()


def test_verify_release_rejects_parquet_private_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Textual parquet columns are scanned for private tokens and invalid datasets."""
    parquet = tmp_path / "bad.parquet"
    pd.DataFrame({"dataset": ["S"], "note": ["EK8 leaked"]}).to_parquet(parquet)
    monkeypatch.setattr(verify_release, "ROOT", tmp_path)
    with pytest.raises(AssertionError, match="Forbidden parquet content"):
        verify_release.scan_parquet_content()


def test_verify_release_rejects_synthetic_dataset_in_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Unauthorized datasets in analytic CSVs are rejected."""
    out = tmp_path / "analysis_output"
    out.mkdir()
    (tmp_path / "instances" / "instance_metadata.csv").parent.mkdir(parents=True)
    pd.DataFrame({"dataset": ["Synthetic"], "instance": ["synthetic_tiny"]}).to_csv(out / "master_instances.csv", index=False)
    monkeypatch.setattr(verify_release, "ROOT", tmp_path)
    offenders: list[str] = []
    verify_release.validate_frame_scope(pd.read_csv(out / "master_instances.csv"), "analysis_output/master_instances.csv", offenders)
    assert offenders
