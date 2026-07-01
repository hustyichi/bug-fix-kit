from __future__ import annotations

from pathlib import Path

from .capture import CaptureRunResult, _execute_capture, latest_capture
from .http import DEFAULT_REQUEST_TIMEOUT_SECONDS


def run_fix_verification(root: Path, *, timeout: int | float = DEFAULT_REQUEST_TIMEOUT_SECONDS) -> CaptureRunResult:
    """Re-run the current capture to verify a fix without touching ``output.log``.

    Reuses the existing ``.bfk/runner.py`` and writes the regression log to
    ``.bfk/fix_output.log``. Requires a reproducible capture to exist.
    """
    capture_dir = latest_capture(root)
    return _execute_capture(
        capture_dir,
        timeout=timeout,
        replayed=True,
        output_log_name="fix_output.log",
    )
