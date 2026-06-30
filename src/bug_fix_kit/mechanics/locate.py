from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifacts import bfk_root


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def load_capture_evidence(root: Path) -> dict[str, Any]:
    """Load deterministic capture evidence for root-cause analysis.

    Read-only loader used by the internal ``locate-load`` command. It surfaces
    which evidence artifacts exist and their parsed content so the skill can
    reason without re-deriving file locations.
    """
    capture_dir = bfk_root(root)
    request_path = capture_dir / "request.json"
    response_path = capture_dir / "response.json"
    output_log_path = capture_dir / "output.log"

    output_log = output_log_path.read_text(errors="replace") if output_log_path.exists() else None
    missing = [
        name
        for name, path in (
            ("request.json", request_path),
            ("response.json", response_path),
            ("output.log", output_log_path),
        )
        if not path.exists()
    ]

    return {
        "capture_dir": str(capture_dir),
        "has_request": request_path.exists(),
        "has_response": response_path.exists(),
        "has_output_log": output_log_path.exists(),
        "request": _read_json(request_path) if request_path.exists() else None,
        "response": _read_json(response_path) if response_path.exists() else None,
        "output_log": output_log,
        "output_log_bytes": len(output_log.encode("utf-8")) if output_log is not None else 0,
        "root_cause_exists": (capture_dir / "root-cause.md").exists(),
        "missing_evidence": missing,
    }
