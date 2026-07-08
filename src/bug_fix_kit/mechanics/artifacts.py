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
    "fix-plan.md",
    "fix.md",
    "fix_output.log",
    "probe.json",
)

ARCHIVE_TRIGGER_ARTIFACT_NAMES = tuple(name for name in CAPTURE_ARTIFACT_NAMES if name != "runner.py")

# Literal marker required on every temporary probe log line inserted by
# ``$bfk-probe``. Revert and residue detection key off this exact string.
PROBE_MARKER = "BFK-PROBE"


def bfk_root(root: Path) -> Path:
    return root / ".bfk"


def probe_manifest_path(capture_dir: Path) -> Path:
    return capture_dir / "probe.json"


def load_probe_manifest(capture_dir: Path) -> dict[str, Any] | None:
    path = probe_manifest_path(capture_dir)
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def probe_residue_files(root: Path) -> list[str]:
    """List probe-session files that still contain the probe marker."""
    manifest = load_probe_manifest(bfk_root(root))
    if not manifest:
        return []
    residue: list[str] = []
    for name in manifest.get("files", []):
        candidate = Path(name).expanduser()
        path = candidate if candidate.is_absolute() else root / candidate
        if path.exists() and PROBE_MARKER in path.read_text(errors="replace"):
            residue.append(str(name))
    return residue


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
    has_archive_trigger = False
    for name in CAPTURE_ARTIFACT_NAMES:
        artifact = capture_dir / name
        if not artifact.exists():
            continue
        if not artifact.is_file():
            raise BfkError(f"Cannot archive non-file bfk artifact: {artifact}")
        artifacts.append(artifact)
        has_archive_trigger = has_archive_trigger or name in ARCHIVE_TRIGGER_ARTIFACT_NAMES

    if not artifacts or not has_archive_trigger:
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
