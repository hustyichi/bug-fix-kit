from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from .errors import BfkError, RunnerExecutionError


def load_runner_module(runner_path: Path) -> ModuleType:
    if not runner_path.exists():
        raise BfkError(f"runner.py missing: {runner_path}")
    spec = importlib.util.spec_from_file_location("bfk_capture_runner", runner_path)
    if spec is None or spec.loader is None:
        raise BfkError(f"Cannot load runner: {runner_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # user-owned runner code can fail at import time
        raise BfkError(f"failed to load runner.py: {exc}") from exc
    if not hasattr(module, "build_request") or not hasattr(module, "PARAMS"):
        raise BfkError("runner.py must define PARAMS and build_request(params)")
    return module


def build_request_from_module(module: ModuleType) -> dict[str, Any]:
    try:
        request = module.build_request(module.PARAMS)
    except Exception as exc:  # build_request failures become durable run artifacts
        raise RunnerExecutionError(str(exc)) from exc
    if not isinstance(request, dict) or not request.get("method") or not request.get("url"):
        raise BfkError("build_request(params) must return a request dict with method and url")
    return request


def load_runner_request(runner_path: Path) -> dict[str, Any]:
    return build_request_from_module(load_runner_module(runner_path))


def runner_log_files(module: ModuleType) -> list[str]:
    return [str(name) for name in (getattr(module, "LOG_FILES", []) or [])]


def runner_wait_seconds(module: ModuleType) -> float:
    return float(getattr(module, "AFTER_REQUEST_WAIT_SECONDS", 0) or 0)
