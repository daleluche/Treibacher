"""Regression tests for public-release scoping and scanners."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis import build_release_package
from analysis.release_scope import canonical_instance_name, is_private_instance_label


def test_ale1_scope_does_not_exclude_ale10() -> None:
    """The legacy Ale_1 case is excluded without catching Ale_10."""
    assert is_private_instance_label("Ale_1")
    assert is_private_instance_label("Ale_1_run01")
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
