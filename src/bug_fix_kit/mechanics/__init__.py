"""Deterministic Bug Fix Kit mechanics.

Shared primitives live in :mod:`errors`, :mod:`artifacts`, :mod:`logs`,
:mod:`http`, and :mod:`runner`. Capture input parsing lives in :mod:`curl`
and :mod:`parameters`. Deterministic command-backed orchestration lives in
:mod:`capture` (``$bfk-capture``), :mod:`fix` (``$bfk-fix``), and
:mod:`locate` (``$bfk-locate``); ``$bfk-fix-plan`` is skill-only.

This package re-exports the stable surface used by tests and callers so
``import bug_fix_kit.mechanics`` keeps working after the split.
"""

from __future__ import annotations

from .artifacts import (CAPTURE_ARTIFACT_NAMES, archive_current_capture,
                        bfk_root, write_run_artifacts)
from .capture import (CaptureContext, CaptureRunResult, create_capture,
                      latest_capture, run_capture_session)
from .curl import ParsedRequestSample, parse_request_sample
from .errors import BfkError, RunnerExecutionError
from .fix import run_fix_verification
from .http import DEFAULT_REQUEST_TIMEOUT_SECONDS, execute_request
from .locate import import_external_logs, load_capture_evidence
from .logs import capture_offsets, read_since_offsets
from .parameters import (ParameterMapping, parameter_mappings_from_sample,
                         parse_params)
from .runner import (build_request_from_module, load_runner_module,
                     load_runner_request, runner_log_files,
                     runner_wait_seconds)

__all__ = [
    "BfkError",
    "RunnerExecutionError",
    "CAPTURE_ARTIFACT_NAMES",
    "CaptureContext",
    "CaptureRunResult",
    "DEFAULT_REQUEST_TIMEOUT_SECONDS",
    "ParameterMapping",
    "ParsedRequestSample",
    "archive_current_capture",
    "bfk_root",
    "build_request_from_module",
    "capture_offsets",
    "create_capture",
    "execute_request",
    "import_external_logs",
    "latest_capture",
    "load_capture_evidence",
    "load_runner_module",
    "load_runner_request",
    "parameter_mappings_from_sample",
    "parse_params",
    "parse_request_sample",
    "read_since_offsets",
    "run_capture_session",
    "run_fix_verification",
    "runner_log_files",
    "runner_wait_seconds",
    "write_run_artifacts",
]
