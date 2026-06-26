from __future__ import annotations

import importlib.util
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class BfkError(RuntimeError):
    pass


class RunnerExecutionError(BfkError):
    pass


def slugify_issue_name(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    return slug or "issue"


def bfk_root(root: Path) -> Path:
    return root / ".bfk"


def write_project(
    root: Path,
    *,
    base_url: str,
    log_files: list[str],
    default_headers: dict[str, str] | None = None,
    auth_note: str = "",
) -> Path:
    path = bfk_root(root) / "PROJECT.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = default_headers or {"Content-Type": "application/json"}
    lines = [
        "# Bug Fix Kit Project Knowledge",
        "",
        "## Local Service",
        f"- Base URL: {base_url}",
        "- Service should be started manually before running bfk.",
        "",
        "## Logs",
        *[f"- {log_file}" for log_file in log_files],
        "",
        "## Log Capture",
        "Default strategy: file offset",
        "",
        "## Request Defaults",
        *[f"- {key}: {value}" for key, value in headers.items()],
    ]
    if auth_note:
        lines += ["", "## Auth", f"- {auth_note}"]
    lines += [
        "",
        "## Fix Principles",
        "- Diagnose before fixing.",
        "- Prefer minimal code changes.",
        "- Do not refactor unrelated code.",
    ]
    path.write_text("\n".join(lines) + "\n")
    return path


def _section_body(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\n(?P<body>.*?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    return match.group("body") if match else ""


def _read_project_defaults(root: Path) -> tuple[str, list[str], dict[str, str]]:
    project = bfk_root(root) / "PROJECT.md"
    if not project.exists():
        raise BfkError("Missing .bfk/PROJECT.md. Run $bfk-init first.")
    text = project.read_text()
    base_match = re.search(r"Base URL:\s*(\S+)", text)
    if not base_match:
        raise BfkError(".bfk/PROJECT.md is missing Base URL. Run $bfk-init again.")

    logs = re.findall(r"^-\s+(.+\.log)\s*$", _section_body(text, "Logs"), flags=re.MULTILINE)
    header_lines = re.findall(r"^-\s+([^:]+):\s*(.*)\s*$", _section_body(text, "Request Defaults"), flags=re.MULTILINE)
    headers = {key.strip(): value.strip() for key, value in header_lines}
    return base_match.group(1), logs or ["logs/app.log"], headers or {"Content-Type": "application/json"}


def _parse_params(raw_params: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    positional: list[str] = []
    for item in raw_params:
        if "=" in item:
            key, value = item.split("=", 1)
            params[key] = value
        else:
            positional.append(item)
    if positional and "value" not in params:
        params["value"] = " ".join(positional)
    return params


def create_issue(root: Path, issue_name: str, raw_params: list[str] | None = None) -> Path:
    raw_params = raw_params or []
    params = _parse_params(raw_params)
    base_url, log_files, headers = _read_project_defaults(root)
    issue_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{slugify_issue_name(issue_name)}"
    issue_dir = bfk_root(root) / "issues" / issue_id
    (issue_dir / "iterations").mkdir(parents=True, exist_ok=False)

    (issue_dir / "issue.md").write_text(
        "\n".join(
            [
                f"# Issue: {issue_name}",
                "",
                "## User Input",
                " ".join(raw_params),
                "",
                "## Parsed Parameters",
                *[f"- {key}: {value}" for key, value in params.items()],
                "",
                "## Expected Goal",
                "Reproduce the local bug, diagnose from logs, and fix minimally.",
            ]
        )
        + "\n"
    )
    (issue_dir / "runner.py").write_text(_runner_template(issue_name, params, base_url, log_files, headers))
    return issue_dir


def _runner_template(
    issue_name: str,
    params: dict[str, str],
    base_url: str,
    log_files: list[str],
    headers: dict[str, str],
) -> str:
    return f'''# Bug Fix Kit Issue Runner

import json

ISSUE_NAME = {issue_name!r}
PARAMS = {json.dumps(params, ensure_ascii=False, indent=2)}
BASE_URL = {base_url!r}
LOG_FILES = {json.dumps(log_files, ensure_ascii=False, indent=2)}
DEFAULT_HEADERS = {json.dumps(headers, ensure_ascii=False, indent=2)}
AFTER_REQUEST_WAIT_SECONDS = 2


def build_request(params: dict) -> dict:
    headers = dict(DEFAULT_HEADERS)
    headers["X-BugFix-Issue"] = ISSUE_NAME
    return {{
        "method": "POST",
        "url": f"{{BASE_URL}}/",
        "headers": headers,
        "json": params,
    }}


if __name__ == "__main__":
    print(json.dumps(build_request(PARAMS), ensure_ascii=False, indent=2))
'''


def latest_issue(root: Path) -> Path:
    issues = sorted((bfk_root(root) / "issues").glob("*"))
    issues = [path for path in issues if path.is_dir()]
    if not issues:
        raise BfkError("No bfk issues found. Run $bfk-new first.")
    return issues[-1]


def next_iteration_dir(issue_dir: Path) -> Path:
    iterations = issue_dir / "iterations"
    iterations.mkdir(parents=True, exist_ok=True)
    nums = [int(path.name) for path in iterations.iterdir() if path.is_dir() and path.name.isdigit()]
    path = iterations / f"{(max(nums) if nums else 0) + 1:03d}"
    path.mkdir(exist_ok=False)
    return path


def load_runner_request(runner_path: Path) -> dict[str, Any]:
    if not runner_path.exists():
        raise BfkError(f"runner.py missing: {runner_path}")
    spec = importlib.util.spec_from_file_location("bfk_issue_runner", runner_path)
    if spec is None or spec.loader is None:
        raise BfkError(f"Cannot load runner: {runner_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # user-owned runner code can fail at import time
        raise BfkError(f"failed to load runner.py: {exc}") from exc
    if not hasattr(module, "build_request") or not hasattr(module, "PARAMS"):
        raise BfkError("runner.py must define PARAMS and build_request(params)")
    try:
        request = module.build_request(module.PARAMS)
    except Exception as exc:  # build_request failures become durable run artifacts
        raise RunnerExecutionError(str(exc)) from exc
    if not isinstance(request, dict) or not request.get("method") or not request.get("url"):
        raise BfkError("build_request(params) must return a request dict with method and url")
    return request


def capture_offsets(log_files: list[Path]) -> dict[str, int]:
    return {str(path): path.stat().st_size if path.exists() else 0 for path in log_files}


def read_since_offsets(offsets: dict[str, int]) -> str:
    chunks: list[str] = []
    for name, offset in offsets.items():
        path = Path(name)
        if not path.exists():
            chunks.append(f"[bfk] missing log file: {name}\n")
            continue
        size = path.stat().st_size
        start = offset if size >= offset else 0
        if size < offset:
            chunks.append(f"[bfk] log file truncated, reading from start: {name}\n")
        with path.open("r", errors="replace") as fh:
            fh.seek(start)
            chunks.append(fh.read())
    return "".join(chunks)


def _body_payload(data: bytes, content_type: str) -> tuple[Any, str | None, bool]:
    if not data:
        return None, None, True
    text = data.decode("utf-8", errors="replace")
    if "json" in content_type.lower():
        try:
            return json.loads(text), None, False
        except json.JSONDecodeError:
            pass
    return None, text, False


def execute_request(request: dict[str, Any], timeout: int | float = 30) -> dict[str, Any]:
    started = time.monotonic()
    try:
        method = str(request.get("method", "GET")).upper()
        headers = dict(request.get("headers") or {})
        body = None
        if "json" in request:
            body = json.dumps(request["json"], ensure_ascii=False).encode()
            headers.setdefault("Content-Type", "application/json")
        elif request.get("body") is not None:
            body = str(request["body"]).encode()
        req = Request(str(request["url"]), data=body, headers=headers, method=method)
        with urlopen(req, timeout=timeout) as response:
            data = response.read()
            parsed, text, empty = _body_payload(data, response.headers.get("Content-Type", ""))
            return {
                "status_code": response.status,
                "headers": dict(response.headers.items()),
                "body": parsed,
                "body_text": text,
                "empty_body": empty,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "transport_error": None,
            }
    except HTTPError as exc:
        data = exc.read()
        parsed, text, empty = _body_payload(data, exc.headers.get("Content-Type", ""))
        return {
            "status_code": exc.code,
            "headers": dict(exc.headers.items()),
            "body": parsed,
            "body_text": text,
            "empty_body": empty,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "transport_error": None,
        }
    except (OSError, URLError, ValueError, TypeError) as exc:
        return {
            "status_code": None,
            "headers": {},
            "body": None,
            "body_text": None,
            "empty_body": False,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "transport_error": {"type": "transport_error", "message": str(exc)},
        }


def write_run_artifacts(iteration_dir: Path, request: dict[str, Any], response: dict[str, Any], logs: str) -> None:
    iteration_dir.mkdir(parents=True, exist_ok=True)
    (iteration_dir / "request.json").write_text(json.dumps(request, indent=2, ensure_ascii=False, default=str) + "\n")
    (iteration_dir / "response.json").write_text(json.dumps(response, indent=2, ensure_ascii=False, default=str) + "\n")
    (iteration_dir / "output.log").write_text(logs)
