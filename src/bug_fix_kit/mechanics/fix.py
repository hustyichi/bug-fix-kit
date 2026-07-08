from __future__ import annotations

from pathlib import Path

from .artifacts import probe_residue_files
from .capture import CaptureRunResult, _execute_capture, latest_capture
from .errors import BfkError
from .http import DEFAULT_REQUEST_TIMEOUT_SECONDS


def run_fix_verification(root: Path, *, timeout: int | float = DEFAULT_REQUEST_TIMEOUT_SECONDS) -> CaptureRunResult:
    """Re-run the current capture to verify a fix without touching ``output.log``.

    Reuses the existing ``.bfk/runner.py`` and writes the regression log to
    ``.bfk/fix_output.log``. Requires a reproducible capture to exist.
    """
    residue = probe_residue_files(root)
    if residue:
        raise BfkError(
            "Probe residue detected in: " + ", ".join(residue)
            + ". Run $bfk-probe --revert before fix verification."
        )
    capture_dir = latest_capture(root)
    return _execute_capture(
        capture_dir,
        timeout=timeout,
        replayed=True,
        output_log_name="fix_output.log",
    )
