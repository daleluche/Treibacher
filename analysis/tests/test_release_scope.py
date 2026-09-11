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


def test_verify_release_rejects_unknown_instance_pair() -> None:
    """Dataset-instance values must match the public instance registry exactly."""
    authorized = {("S", "S_1"), ("2X", "IncT2X_1")}
    offenders: list[str] = []
    verify_release.validate_frame_scope(
        pd.DataFrame({"dataset": ["S"], "instance": ["bad_instance"]}),
        "analysis_output/master_instances.csv",
        offenders,
        authorized,
    )
    assert offenders == ["analysis_output/master_instances.csv:pair=('S', 'bad_instance')"]


def test_verify_release_rejects_crossed_instance_pair() -> None:
    """An instance name authorized for one family is not valid in another family."""
    authorized = {("S", "S_1"), ("2X", "IncT2X_1")}
    offenders: list[str] = []
    verify_release.validate_frame_scope(
        pd.DataFrame({"dataset": ["S"], "instance": ["IncT2X_1"]}),
        "analysis_output/master_instances.csv",
        offenders,
        authorized,
    )
    assert offenders == ["analysis_output/master_instances.csv:pair=('S', 'IncT2X_1')"]


def test_verify_release_rejects_dataset_mismatch_with_path() -> None:
    """When a path declares a dataset, row metadata must agree with it."""
    offenders: list[str] = []
    verify_release.validate_frame_scope(
        pd.DataFrame({"dataset": ["S"], "instance": ["S_1"]}),
        "instances/gamspy_py/2X/IncT2X_1.csv",
        offenders,
        {("S", "S_1"), ("2X", "IncT2X_1")},
    )
    assert offenders == ["instances/gamspy_py/2X/IncT2X_1.csv:path_dataset=2X, declared=['S']"]


def test_verify_release_allows_only_declared_aggregate_exceptions() -> None:
    """Aggregate labels are allowlisted by exact file and exact value."""
    offenders: list[str] = []
    verify_release.validate_frame_scope(
        pd.DataFrame({"dataset": ["8X/10X heterogeneous family aggregate pooled"]}),
        "analysis_output/sprint3_descriptive_by_scale.csv",
        offenders,
        {("S", "S_1")},
    )
    assert not offenders

    verify_release.validate_frame_scope(
        pd.DataFrame({"dataset": ["8X/10X heterogeneous family aggregate pooled"]}),
        "analysis_output/master_instances.csv",
        offenders,
        {("S", "S_1")},
    )
    assert offenders == ["analysis_output/master_instances.csv:dataset=['8X/10X heterogeneous family aggregate pooled']"]


def test_verify_release_allows_only_declared_gamma_instance_exceptions() -> None:
    """MEDIAN and AGGREGATE pseudo-instances are valid only in the gamma table."""
    offenders: list[str] = []
    verify_release.validate_frame_scope(
        pd.DataFrame({"dataset": ["2X", "2X"], "instance": ["MEDIAN", "AGGREGATE"]}),
        "analysis_output/gamma_tradeoff_2x.csv",
        offenders,
        {("2X", "IncT2X_1")},
    )
    assert not offenders

    verify_release.validate_frame_scope(
        pd.DataFrame({"dataset": ["2X"], "instance": ["MEDIAN"]}),
        "analysis_output/comparison_table.csv",
        offenders,
        {("2X", "IncT2X_1")},
    )
    assert offenders == ["analysis_output/comparison_table.csv:pair=('2X', 'MEDIAN')"]


def test_verify_release_rejects_unknown_json_pair() -> None:
    """JSON instance metadata must use an exact public pair."""
    offenders: list[str] = []
    verify_release.validate_json_scope(
        {"dataset": "S", "instance": "bad_instance"},
        "results/bad.json",
        offenders,
        {("S", "S_1")},
    )
    assert offenders == ["results/bad.json:pair=('S', 'bad_instance')"]


def test_verify_release_rejects_unknown_parquet_pair() -> None:
    """Parquet metadata receives the same exact scope validation as CSVs."""
    offenders: list[str] = []
    verify_release.validate_frame_scope(
        pd.DataFrame({"dataset": ["Synthetic"], "instance": ["synthetic_tiny"]}),
        "results/window_logs/bad.parquet",
        offenders,
        {("S", "S_1")},
    )
    assert offenders


def test_verify_release_rejects_crlf_text_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Public text files are normalized to LF for byte-stable package builds."""
    monkeypatch.setattr(verify_release, "ROOT", tmp_path)
    (tmp_path / "README.md").write_bytes(b"one\r\ntwo\r\n")
    with pytest.raises(AssertionError, match="Non-LF"):
        verify_release.verify_lf_line_endings()
