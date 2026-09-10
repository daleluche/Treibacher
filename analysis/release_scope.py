"""Public-release scope and identifier canonicalization helpers."""
from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

PUBLIC_DATASETS = {"S", "2X", "3X", "4X", "5X", "8X", "10X"}
ALE_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_])Ale_(\d+)(?![A-Za-z0-9_])")
ALE1_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_])Ale_1(?!\d)")
PUBLIC_ALE_RE = re.compile(r"(?<![A-Za-z0-9_])Ale_(10|[2-9])(?=$|[^0-9])")
ABSOLUTE_PATH_RE = re.compile(
    r"(?i)(^[A-Za-z]:[\\/]|\\\\[^\\/]+[\\/][^\\/]+|^file://|^/home/|^/Users/|^/workspace/|^/tmp/)"
)
WINDOW_LOG_SEGMENT_RE = re.compile(r".*[\\/]window_logs[\\/](.+)$")


def canonical_instance_name(value: str) -> str:
    """Return the public instance label for a legacy or canonical label."""
    match = ALE_TOKEN_RE.fullmatch(value)
    if not match:
        return value
    index = int(match.group(1))
    if index == 1:
        return value
    if 2 <= index <= 10:
        return f"S_{index}"
    return value


def canonicalize_public_text(value: str) -> str:
    """Canonicalize public text without exposing private labels."""
    def repl(match: re.Match[str]) -> str:
        index = int(match.group(1))
        return f"S_{index}" if 2 <= index <= 10 else match.group(0)

    text = PUBLIC_ALE_RE.sub(lambda match: f"S_{int(match.group(1))}", value)
    text = ALE_TOKEN_RE.sub(repl, text)
    text = text.replace("experiments/GAMSPy/Real/results_3horas/S_", "experiments/GAMSPy/S/results_3horas/S_")
    text = text.replace("experiments/GAMSPy/Real/results/S_", "experiments/GAMSPy/S/results/S_")
    text = text.replace("experiments/GRASP/Real/results/S_", "experiments/GRASP/S/results/S_")
    text = text.replace("experiments\\GAMSPy\\Real\\results_3horas\\S_", "experiments\\GAMSPy\\S\\results_3horas\\S_")
    text = text.replace("experiments\\GAMSPy\\Real\\results\\S_", "experiments\\GAMSPy\\S\\results\\S_")
    text = text.replace("experiments\\GRASP\\Real\\results\\S_", "experiments\\GRASP\\S\\results\\S_")
    text = text.replace("Real order book", "Private real order book excluded")
    text = text.replace("dataset=Real", "dataset=PrivateRealExcluded")
    text = text.replace("DATASET    = 'Real'", "DATASET    = 'S'")
    text = text.replace('DATASET    = "Real"', 'DATASET    = "S"')
    text = text.replace("ALCOA", "PSP_MODEL")
    text = text.replace("Treibacher", "PSP")
    text = re.sub(r"(?i)[A-Za-z]:[\\/](?:GitHub|Users[\\/]betoD[\\/]Downloads)[\\/]PSP[\\/]", "", text)
    text = re.sub(r"(?i)[A-Za-z]:[\\/]GitHub[\\/]Treibacher[\\/]", "", text)
    text = re.sub(r"(?i)[A-Za-z]:[\\/]Users[\\/]betoD[\\/]", "", text)
    text = text.replace("anonymization", "identifier coding")
    text = text.replace("anonymized", "coded")
    text = text.replace("Anonymization", "Identifier coding")
    return text


def canonicalize_relative_path(path: Path) -> Path:
    """Canonicalize a repository-relative public path."""
    parts = [canonicalize_public_text(part) for part in path.parts]
    for index, part in enumerate(parts):
        if (
            part == "Real"
            and index > 0
            and parts[index - 1] in {"GAMSPy", "GRASP"}
            and any(re.fullmatch(r"S_(?:[2-9]|10)(?:\..*)?", item) for item in parts[index + 1 :])
        ):
            parts[index] = "S"
    return Path(*parts)


def is_private_instance_label(value: object) -> bool:
    """Return whether a value identifies a nonpublic real or legacy case."""
    text = str(value)
    return bool(ALE1_TOKEN_RE.search(text) or "REAL_1" in text or text == "Real order book" or text == "Real")


def is_private_path(value: object) -> bool:
    """Return whether a string refers to an excluded private path."""
    text = str(value).replace("\\", "/")
    if re.search(r"experiments/(?:GAMSPy|GRASP)/Real/(?:results(?:_3horas)?/)?Ale_(?:[2-9]|10)(?:\.|_)", text):
        return False
    private_markers = [
        "results_production/real",
        "experiments/GAMSPy/Real/Ale_1",
        "experiments/GAMSPy/Real/results/Ale_1",
        "experiments/GAMSPy/Real/results_3horas/Ale_1",
        "REAL_1.py",
        "add_real_order_book.py",
        "analysis/private_release",
        "analysis/code_identifiers.py",
        "verify_manuscript_numbers.py",
        "rebuild_s1.py",
    ]
    return any(marker in text for marker in private_markers)


def is_public_record(record: dict[str, Any]) -> bool:
    """Return whether a structured record is in public release scope."""
    for key in ("dataset", "instance", "name", "run_id"):
        if key in record and is_private_instance_label(record[key]):
            return False
    for key in ("source_path", "window_log_path", "path", "file", "source_file"):
        if key in record and is_private_path(record[key]):
            return False
    return True


def canonicalize_json_value(value: Any) -> Any:
    """Canonicalize public JSON values recursively."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if key == "window_log_path":
                result[key] = relative_window_log_path(item)
                result["window_log_included"] = result[key] is not None
            elif key in {"dataset"} and str(item) == "Real":
                result[key] = "S"
            else:
                result[key] = canonicalize_json_value(item)
        return result
    if isinstance(value, list):
        return [canonicalize_json_value(item) for item in value]
    if isinstance(value, str):
        return canonicalize_public_text(scrub_absolute_path(value))
    return value


def scrub_absolute_path(value: str) -> str:
    """Remove absolute local path text from a public string value."""
    if not ABSOLUTE_PATH_RE.search(value):
        return value
    log_path = relative_window_log_path(value)
    return log_path if log_path is not None else "<local_path_removed>"


def relative_window_log_path(value: object) -> str | None:
    """Return a package-relative window-log path when a path points to a log."""
    if not isinstance(value, str) or not value:
        return None
    match = WINDOW_LOG_SEGMENT_RE.match(value)
    if not match:
        return None
    name = canonicalize_public_text(match.group(1).replace("\\", "/"))
    return PurePosixPath("results", "window_logs", name).as_posix()


def has_absolute_path(value: object) -> bool:
    """Return whether a string is an absolute local path or URI."""
    return isinstance(value, str) and bool(ABSOLUTE_PATH_RE.search(value))
