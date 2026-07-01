from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .artifacts import archive_current_capture, bfk_root, write_run_artifacts
from .curl import ParsedRequestSample, parse_request_sample
from .errors import BfkError
from .http import DEFAULT_REQUEST_TIMEOUT_SECONDS, execute_request
from .logs import capture_offsets, read_since_offsets
from .parameters import (ParameterMapping, parameter_mappings_from_sample,
                         parse_params)
from .runner import (build_request_from_module, load_runner_module,
                     runner_log_files, runner_wait_seconds)

CAPTURE_ARTIFACT_NAMES = (
    "runner.py",
    "request.json",
    "response.json",
    "output.log",
    "root-cause.md",
    "fix.md",
    "fix_output.log",
)


@dataclass(frozen=True)
class CaptureContext:
    base_url: str
    log_files: list[str]
    headers: dict[str, str]
    endpoint_method: str
    endpoint_path: str
    after_request_wait_seconds: float
    request_sample: ParsedRequestSample | None
    parameter_mappings: list[ParameterMapping]


@dataclass(frozen=True)
class CaptureRunResult:
    capture_dir: Path
    request: dict[str, Any]
    response: dict[str, Any]
    log_files: list[str]
    missing_log_files: list[str]
    output_log_bytes: int
    replayed: bool
    output_log_name: str

    def to_summary(self) -> dict[str, Any]:
        return {
            "capture_dir": str(self.capture_dir),
            "replayed": self.replayed,
            "request": {
                "method": self.request.get("method"),
                "url": self.request.get("url"),
            },
            "response_status": self.response.get("status_code"),
            "transport_error": self.response.get("transport_error"),
            "log_files": self.log_files,
            "missing_log_files": self.missing_log_files,
            "output_log_name": self.output_log_name,
            "output_log_bytes": self.output_log_bytes,
            "artifacts": {
                "runner": str(self.capture_dir / "runner.py"),
                "request": str(self.capture_dir / "request.json"),
                "response": str(self.capture_dir / "response.json"),
                "output_log": str(self.capture_dir / self.output_log_name),
            },
        }


def _origin_from_sample(sample: ParsedRequestSample | None) -> str:
    if sample is None:
        return ""
    parsed = urlparse(sample.url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def _parse_endpoint_text(endpoint: str) -> tuple[str, str]:
    if not endpoint:
        return "POST", "/"
    parts = endpoint.strip().split(maxsplit=1)
    if len(parts) == 2:
        return parts[0].upper(), _normalize_path(parts[1])
    return "POST", _normalize_path(parts[0])


def _normalize_path(path: str) -> str:
    if not path:
        return "/"
    parsed = urlparse(path)
    resolved = parsed.path if parsed.scheme or parsed.netloc else path
    if parsed.query:
        resolved = f"{resolved}?{parsed.query}"
    return resolved if resolved.startswith("/") else f"/{resolved}"


def _resolve_endpoint(endpoint: str, parsed_sample: ParsedRequestSample | None) -> tuple[str, str]:
    method, path = _parse_endpoint_text(endpoint)
    if endpoint:
        return method, path
    if parsed_sample:
        return parsed_sample.method, parsed_sample.path
    return method, path


def _capture_context_from_input(
    *,
    base_url: str = "",
    log_files: list[str] | None = None,
    default_headers: dict[str, str] | None = None,
    request_sample: str = "",
    endpoint: str = "",
    after_request_wait_seconds: int | float = 2,
) -> CaptureContext:
    parsed_sample: ParsedRequestSample | None = None
    if request_sample.strip():
        parsed_sample = parse_request_sample(request_sample)

    resolved_base_url = base_url or _origin_from_sample(parsed_sample)
    if not resolved_base_url:
        raise BfkError("Missing request context: provide a curl sample or base URL.")
    if not log_files:
        raise BfkError("Missing request context: provide at least one local log file.")

    sample_headers = parsed_sample.headers if parsed_sample else {}
    headers = sample_headers or {"Content-Type": "application/json"}
    if default_headers:
        headers.update(default_headers)

    endpoint_method, endpoint_path = _resolve_endpoint(endpoint, parsed_sample)
    mappings = parameter_mappings_from_sample(parsed_sample)
    return CaptureContext(
        base_url=resolved_base_url,
        log_files=log_files,
        headers=headers,
        endpoint_method=endpoint_method,
        endpoint_path=endpoint_path,
        after_request_wait_seconds=float(after_request_wait_seconds),
        request_sample=parsed_sample,
        parameter_mappings=mappings,
    )


def _has_capture_context(
    *,
    base_url: str,
    log_files: list[str] | None,
    default_headers: dict[str, str] | None,
    request_sample: str,
    endpoint: str,
) -> bool:
    return bool(base_url or log_files or default_headers or request_sample.strip() or endpoint)


def latest_capture(root: Path) -> Path:
    path = bfk_root(root)
    if not (path / "runner.py").exists():
        raise BfkError("No bfk capture found. Run $bfk-capture first.")
    return path


def create_capture(
    root: Path,
    raw_params: list[str] | None = None,
    *,
    base_url: str = "",
    log_files: list[str] | None = None,
    default_headers: dict[str, str] | None = None,
    request_sample: str = "",
    endpoint: str = "",
    after_request_wait_seconds: int | float = 2,
) -> Path:
    raw_params = raw_params or []
    has_context = _has_capture_context(
        base_url=base_url,
        log_files=log_files,
        default_headers=default_headers,
        request_sample=request_sample,
        endpoint=endpoint,
    )
    if not has_context:
        if raw_params:
            raise BfkError("Missing request context: provide a curl sample or base URL, endpoint, headers/body, and log file.")
        return latest_capture(root)

    params = parse_params(raw_params)
    config = _capture_context_from_input(
        base_url=base_url,
        log_files=log_files,
        default_headers=default_headers,
        request_sample=request_sample,
        endpoint=endpoint,
        after_request_wait_seconds=after_request_wait_seconds,
    )
    capture_dir = bfk_root(root)
    capture_dir.mkdir(parents=True, exist_ok=True)
    archive_current_capture(capture_dir)
    for name in CAPTURE_ARTIFACT_NAMES:
        (capture_dir / name).unlink(missing_ok=True)

    if config.request_sample:
        runner = _request_contract_runner_template(params, config)
    else:
        runner = _runner_template(params, config)
    (capture_dir / "runner.py").write_text(runner)
    return capture_dir


def run_capture_session(
    root: Path,
    raw_params: list[str] | None = None,
    *,
    base_url: str = "",
    log_files: list[str] | None = None,
    default_headers: dict[str, str] | None = None,
    request_sample: str = "",
    endpoint: str = "",
    after_request_wait_seconds: int | float = 2,
    timeout: int | float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
) -> CaptureRunResult:
    """Deterministically create-or-replay a capture and write its run artifacts.

    This is the orchestration entry point used by the internal ``capture-run``
    command so the create -> offset -> execute -> read-log -> write order is
    fixed in code instead of being re-derived by the skill on each run.
    """
    has_context = _has_capture_context(
        base_url=base_url,
        log_files=log_files,
        default_headers=default_headers,
        request_sample=request_sample,
        endpoint=endpoint,
    )
    capture_dir = create_capture(
        root,
        raw_params,
        base_url=base_url,
        log_files=log_files,
        default_headers=default_headers,
        request_sample=request_sample,
        endpoint=endpoint,
        after_request_wait_seconds=after_request_wait_seconds,
    )
    return _execute_capture(capture_dir, timeout=timeout, replayed=not has_context, output_log_name="output.log")


def _execute_capture(
    capture_dir: Path,
    *,
    timeout: int | float,
    replayed: bool,
    output_log_name: str,
) -> CaptureRunResult:
    module = load_runner_module(capture_dir / "runner.py")
    request = build_request_from_module(module)
    log_paths = [Path(name) for name in runner_log_files(module)]

    offsets = capture_offsets(log_paths)
    response = execute_request(request, timeout=timeout)
    wait = runner_wait_seconds(module)
    if wait > 0:
        time.sleep(wait)
    logs = read_since_offsets(offsets)
    write_run_artifacts(capture_dir, request, response, logs, output_log_name=output_log_name)

    return CaptureRunResult(
        capture_dir=capture_dir,
        request=request,
        response=response,
        log_files=[str(path) for path in log_paths],
        missing_log_files=[str(path) for path in log_paths if not path.exists()],
        output_log_bytes=len(logs.encode("utf-8")),
        replayed=replayed,
        output_log_name=output_log_name,
    )


def _runner_template(
    params: dict[str, str],
    config: CaptureContext,
) -> str:
    base_url = config.base_url
    log_files = config.log_files
    headers = config.headers
    method = config.endpoint_method or "POST"
    endpoint_path = config.endpoint_path or "/"
    return f'''# Bug Fix Kit Capture Runner

import json

PARAMS = {json.dumps(params, ensure_ascii=False, indent=2)}
BASE_URL = {base_url!r}
REQUEST_METHOD = {method!r}
REQUEST_PATH = {endpoint_path!r}
LOG_FILES = {json.dumps(log_files, ensure_ascii=False, indent=2)}
DEFAULT_HEADERS = {json.dumps(headers, ensure_ascii=False, indent=2)}
AFTER_REQUEST_WAIT_SECONDS = {config.after_request_wait_seconds!r}


def build_request(params: dict) -> dict:
    headers = dict(DEFAULT_HEADERS)
    return {{
        "method": REQUEST_METHOD,
        "url": f"{{BASE_URL.rstrip('/')}}{{REQUEST_PATH}}",
        "headers": headers,
        "json": params,
    }}


if __name__ == "__main__":
    print(json.dumps(build_request(PARAMS), ensure_ascii=False, indent=2))
'''


def _request_contract_runner_template(params: dict[str, str], config: CaptureContext) -> str:
    assert config.request_sample is not None
    sample = config.request_sample
    request_template = {
        "method": config.endpoint_method or sample.method,
        "path": config.endpoint_path or sample.path,
        "headers": config.headers or sample.headers,
        "json": sample.body,
    }
    mappings = {
        mapping.name: mapping.locations
        for mapping in config.parameter_mappings
        if mapping.locations
    }
    return f'''# Bug Fix Kit Capture Runner

import copy
import json
import os
import re

PARAMS = {json.dumps(params, ensure_ascii=False, indent=2)}
BASE_URL = {config.base_url!r}
LOG_FILES = {json.dumps(config.log_files, ensure_ascii=False, indent=2)}
AFTER_REQUEST_WAIT_SECONDS = {config.after_request_wait_seconds!r}
REQUEST_TEMPLATE = {request_template!r}
INNER_JSON_STRING_PATH = {sample.inner_json_path!r}
PARAMETER_LOCATIONS = {mappings!r}


def _expand_env_placeholders(value: str) -> str:
    return re.sub(r"\\$\\{{([A-Za-z_][A-Za-z0-9_]*)\\}}", lambda match: os.environ.get(match.group(1), match.group(0)), value)


def _expand_headers(headers: dict) -> dict:
    return {{key: _expand_env_placeholders(str(value)) for key, value in headers.items()}}


def _get_path(root, path):
    current = root
    for part in path:
        current = current[part]
    return current


def _set_path(root, path, value):
    current = root
    for part in path[:-1]:
        current = current[part]
    current[path[-1]] = value


def _parse_location(location: str) -> tuple[str, list[str]]:
    prefix, _, remainder = location.partition(".")
    if not prefix or not remainder:
        raise ValueError(f"invalid parameter location: {{location}}")
    return prefix, remainder.split(".")


def _get_location(body: dict, inner: dict | None, location: str):
    prefix, path = _parse_location(location)
    target = body if prefix == "body" else inner
    if target is None:
        return None
    current = target
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_location(body: dict, inner: dict | None, location: str, value):
    prefix, path = _parse_location(location)
    target = body if prefix == "body" else inner
    if target is None:
        raise ValueError(f"cannot set inner location without inner payload: {{location}}")
    current = target
    for part in path[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {{}}
        current = current[part]
    current[path[-1]] = value


def _coerce_value(existing, value: str):
    if isinstance(existing, bool):
        return value.lower() in {{"1", "true", "yes", "on"}}
    if isinstance(existing, int) and not isinstance(existing, bool):
        try:
            return int(value)
        except ValueError:
            return value
    if isinstance(existing, float):
        try:
            return float(value)
        except ValueError:
            return value
    if existing is None or isinstance(existing, (dict, list)):
        stripped = value.strip()
        if stripped in {{"true", "false", "null"}} or stripped.startswith(("[", "{{", '"')):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return value
    return value


def _apply_parameter_locations(body: dict, params: dict) -> dict:
    inner = None
    if INNER_JSON_STRING_PATH:
        raw_inner = _get_path(body, INNER_JSON_STRING_PATH)
        inner = json.loads(raw_inner) if isinstance(raw_inner, str) else raw_inner
    for name, locations in PARAMETER_LOCATIONS.items():
        if name not in params:
            continue
        for location in locations:
            existing = _get_location(body, inner, location)
            _set_location(body, inner, location, _coerce_value(existing, str(params[name])))
    if INNER_JSON_STRING_PATH and inner is not None:
        _set_path(body, INNER_JSON_STRING_PATH, json.dumps(inner, ensure_ascii=False))
    return body


def build_request(params: dict) -> dict:
    template = copy.deepcopy(REQUEST_TEMPLATE)
    body = _apply_parameter_locations(template.get("json") or {{}}, params)
    headers = _expand_headers(template.get("headers") or {{}})
    return {{
        "method": template.get("method", "POST"),
        "url": f"{{BASE_URL.rstrip('/')}}{{template.get('path', '/')}}",
        "headers": headers,
        "json": body,
    }}


if __name__ == "__main__":
    print(json.dumps(build_request(PARAMS), ensure_ascii=False, indent=2))
'''
