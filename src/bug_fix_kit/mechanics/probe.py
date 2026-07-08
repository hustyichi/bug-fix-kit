"""Deterministic probe mechanics backing ``$bfk-probe``.

The skill inserts temporary log lines (each containing the literal
``BFK-PROBE`` marker) into application code, then delegates the deterministic
parts to these functions: replaying the capture so the probe evidence lands in
the regular ``output.log``, verifying the sentinel took effect, tracking the
probe session manifest, and reverting every probe line afterwards.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .artifacts import (PROBE_MARKER, bfk_root, load_probe_manifest,
                        probe_manifest_path)
from .capture import _execute_capture, latest_capture
from .errors import BfkError
from .http import DEFAULT_REQUEST_TIMEOUT_SECONDS

MAX_PROBE_ROUNDS = 2


def _resolve_file(root: Path, name: str) -> Path:
    path = Path(name).expanduser()
    return path if path.is_absolute() else root / path


def _write_manifest(capture_dir: Path, manifest: dict[str, Any]) -> None:
    probe_manifest_path(capture_dir).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )


def run_probe_session(
    root: Path,
    files: list[str],
    *,
    timeout: int | float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Replay the current capture after probe lines were inserted.

    Requires ``.bfk/runner.py``. Refreshes the regular ``.bfk/output.log`` (the
    replayed evidence is a superset of the previous run: same request, plus
    probe lines), records the probe session in ``.bfk/probe.json``, and reports
    whether the sentinel probe line appeared in the new logs.
    """
    if not files:
        raise BfkError("Missing probe files: pass one --file per instrumented file.")
    capture_dir = latest_capture(root)

    manifest = load_probe_manifest(capture_dir)
    active = manifest is not None and not manifest.get("reverted")
    previous_round = int(manifest.get("round", 0)) if active else 0
    round_number = previous_round + 1
    if round_number > MAX_PROBE_ROUNDS:
        raise BfkError(
            f"Probe round limit reached ({MAX_PROBE_ROUNDS}). "
            "Run $bfk-probe --revert and continue with the evidence already collected."
        )

    missing = [name for name in files if not _resolve_file(root, name).exists()]
    if missing:
        raise BfkError("Probe file not found: " + ", ".join(missing))
    unmarked = [
        name
        for name in files
        if PROBE_MARKER not in _resolve_file(root, name).read_text(errors="replace")
    ]
    if unmarked:
        raise BfkError(f"No {PROBE_MARKER} line found in: " + ", ".join(unmarked))

    known_files = list(manifest.get("files", [])) if active else []
    all_files = sorted({*known_files, *(str(name) for name in files)})
    created_at = (
        manifest.get("created_at")
        if active and manifest.get("created_at")
        else datetime.now().isoformat(timespec="seconds")
    )
    _write_manifest(
        capture_dir,
        {
            "marker": PROBE_MARKER,
            "created_at": created_at,
            "round": round_number,
            "files": all_files,
            "reverted": False,
        },
    )

    result = _execute_capture(
        capture_dir,
        timeout=timeout,
        replayed=True,
        output_log_name="output.log",
    )
    logs = (capture_dir / "output.log").read_text(errors="replace")
    sentinel_seen = PROBE_MARKER in logs

    summary = result.to_summary()
    summary["probe"] = {
        "marker": PROBE_MARKER,
        "round": round_number,
        "max_rounds": MAX_PROBE_ROUNDS,
        "files": all_files,
        "sentinel_seen": sentinel_seen,
    }
    return summary


def revert_probe_session(root: Path, extra_files: list[str] | None = None) -> dict[str, Any]:
    """Remove every probe line recorded in the probe session.

    Probe lines are standalone lines containing the marker, so deleting every
    marked line restores the pre-probe content exactly. Always verifies zero
    residue afterwards.
    """
    capture_dir = bfk_root(root)
    manifest = load_probe_manifest(capture_dir)
    files: list[str] = list(manifest.get("files", [])) if manifest else []
    for name in extra_files or []:
        if str(name) not in files:
            files.append(str(name))
    if not files:
        raise BfkError(
            "No probe session to revert: .bfk/probe.json is missing and no --file was given."
        )

    reverted: list[dict[str, str]] = []
    residue: list[str] = []
    for name in files:
        path = _resolve_file(root, name)
        if not path.exists():
            reverted.append({"file": name, "method": "missing"})
            continue
        if PROBE_MARKER not in path.read_text(errors="replace"):
            reverted.append({"file": name, "method": "clean"})
            continue
        _strip_marker_lines(path)
        if PROBE_MARKER in path.read_text(errors="replace"):
            residue.append(name)
        reverted.append({"file": name, "method": "strip"})

    if manifest is not None:
        manifest["files"] = files
        manifest["reverted"] = not residue
        _write_manifest(capture_dir, manifest)

    return {
        "capture_dir": str(capture_dir),
        "marker": PROBE_MARKER,
        "reverted_files": reverted,
        "residue_files": residue,
        "clean": not residue,
    }


def _strip_marker_lines(path: Path) -> None:
    lines = path.read_text(errors="replace").splitlines(keepends=True)
    path.write_text("".join(line for line in lines if PROBE_MARKER not in line))
