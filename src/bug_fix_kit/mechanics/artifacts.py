from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import BfkError

CAPTURE_ARTIFACT_NAMES = (
    "runner.py",
    "request.json",
    "response.json",
    "output.log",
    "root-cause.md",
    "fix.md",
    "fix_output.log",
)


def bfk_root(root: Path) -> Path:
    return root / ".bfk"


def _next_archive_dir(archive_root: Path) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    candidate = archive_root / stamp
    suffix = 2
    while candidate.exists():
        candidate = archive_root / f"{stamp}-{suffix}"
        suffix += 1
    return candidate


def archive_current_capture(capture_dir: Path) -> Path | None:
    artifacts: list[Path] = []
    for name in CAPTURE_ARTIFACT_NAMES:
        artifact = capture_dir / name
        if not artifact.exists():
            continue
        if not artifact.is_file():
            raise BfkError(f"Cannot archive non-file bfk artifact: {artifact}")
        artifacts.append(artifact)

    if not artifacts:
        return None

    archive_dir = _next_archive_dir(capture_dir / "archive")
    archive_dir.mkdir(parents=True, exist_ok=False)
    for artifact in artifacts:
        shutil.copy2(artifact, archive_dir / artifact.name)
    return archive_dir


def write_run_artifacts(
    capture_dir: Path,
    request: dict[str, Any],
    response: dict[str, Any],
    logs: str,
    *,
    output_log_name: str = "output.log",
) -> None:
    if Path(output_log_name).name != output_log_name:
        raise BfkError("output_log_name must be a file name")
    capture_dir.mkdir(parents=True, exist_ok=True)
    (capture_dir / "request.json").write_text(json.dumps(request, indent=2, ensure_ascii=False, default=str) + "\n")
    (capture_dir / "response.json").write_text(json.dumps(response, indent=2, ensure_ascii=False, default=str) + "\n")
    (capture_dir / output_log_name).write_text(logs)
