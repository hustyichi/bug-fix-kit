from __future__ import annotations

import importlib.util
import json
import re
import shlex
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class BfkError(RuntimeError):
    pass


class RunnerExecutionError(BfkError):
    pass


@dataclass(frozen=True)
class ParsedRequestSample:
    raw: str
    method: str
    url: str
    path: str
    headers: dict[str, str]
    body: Any
    inner_json_path: list[str | int]
    inner_payload: dict[str, Any] | None


@dataclass(frozen=True)
class ParameterMapping:
    name: str
    locations: list[str]
    required: bool
    default: str
    source: str = "sample"


@dataclass(frozen=True)
class ProjectConfig:
    base_url: str
    log_files: list[str]
    headers: dict[str, str]
    endpoint_method: str
    endpoint_path: str
    after_request_wait_seconds: float
    request_sample: ParsedRequestSample | None
    parameter_mappings: list[ParameterMapping]


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
    request_sample: str = "",
    request_name: str = "default",
    endpoint: str = "",
    timeout_seconds: int | float = 120,
    after_request_wait_seconds: int | float = 2,
    repository_evidence: list[str] | None = None,
) -> Path:
    path = bfk_root(root) / "PROJECT.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    parsed_sample: ParsedRequestSample | None = None
    validation_notes: list[str] = []
    try:
        parsed_sample = parse_request_sample(request_sample) if request_sample.strip() else None
    except BfkError as exc:
        validation_notes.append(f"Request sample parse warning: {exc}")

    sample_headers = parsed_sample.headers if parsed_sample else {}
    headers = sample_headers or {"Content-Type": "application/json"}
    if default_headers:
        headers.update(default_headers)

    endpoint_method, endpoint_path = _resolve_endpoint(endpoint, parsed_sample)
    lines = [
        "# Bug Fix Kit Project Knowledge",
        "",
        "## Local Service",
        f"- Base URL: {base_url}",
        f"- Endpoint: {endpoint_method} {endpoint_path}",
        f"- Timeout seconds: {_format_number(timeout_seconds)}",
        f"- After request wait seconds: {_format_number(after_request_wait_seconds)}",
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
    if request_sample.strip():
        lines += [
            "",
            f"## Request Sample: {request_name or 'default'}",
            "",
            "```bash",
            request_sample.strip(),
            "```",
        ]
    path.write_text("\n".join(lines) + "\n")
    return path


def _section_body(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\n(?P<body>.*?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    return match.group("body") if match else ""


def _format_number(value: int | float) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else str(number)


def _parse_float(value: str | None, *, default: float) -> float:
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _project_bullet_value(text: str, key: str) -> str:
    match = re.search(rf"^-\s+{re.escape(key)}:\s*(.+?)\s*$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


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


def _shell_tokens(raw: str) -> list[str]:
    try:
        return shlex.split(raw.replace("\\\n", " "), comments=False, posix=True)
    except ValueError as exc:
        raise BfkError(f"failed to parse curl sample: {exc}") from exc


def _header_from_text(item: str) -> tuple[str, str]:
    if ":" not in item:
        raise BfkError(f"header must be 'Key: Value': {item}")
    key, value = item.split(":", 1)
    return key.strip(), value.strip()


def _parse_curl_sample(raw: str) -> tuple[str, str, dict[str, str], str]:
    tokens = _shell_tokens(raw)
    if not tokens or tokens[0] != "curl":
        raise BfkError("request sample must be a curl command")
    method = ""
    url = ""
    headers: dict[str, str] = {}
    body = ""
    index = 1
    while index < len(tokens):
        token = tokens[index]
        next_value = tokens[index + 1] if index + 1 < len(tokens) else ""
        if token in {"--location", "-L", "--compressed", "--silent", "-s"}:
            index += 1
            continue
        if token in {"--request", "-X"}:
            method = next_value.upper()
            index += 2
            continue
        if token.startswith("--request="):
            method = token.split("=", 1)[1].upper()
            index += 1
            continue
        if token.startswith("-X") and len(token) > 2:
            method = token[2:].upper()
            index += 1
            continue
        if token in {"--header", "-H"}:
            key, value = _header_from_text(next_value)
            headers[key] = value
            index += 2
            continue
        if token.startswith("--header="):
            key, value = _header_from_text(token.split("=", 1)[1])
            headers[key] = value
            index += 1
            continue
        if token in {"--data", "--data-raw", "--data-binary", "-d"}:
            body = next_value
            method = method or "POST"
            index += 2
            continue
        if token.startswith("--data-raw=") or token.startswith("--data=") or token.startswith("--data-binary="):
            body = token.split("=", 1)[1]
            method = method or "POST"
            index += 1
            continue
        if token.startswith("http://") or token.startswith("https://"):
            url = token
        index += 1
    if not url:
        raise BfkError("curl sample is missing URL")
    return method or "GET", url, headers, body


def _find_inner_json_string(value: Any, path: list[str | int] | None = None) -> tuple[list[str | int], dict[str, Any] | None]:
    path = path or []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [], None
        if isinstance(parsed, dict) and ("action" in parsed or "params" in parsed):
            return path, parsed
        return [], None
    if isinstance(value, dict):
        for key, item in value.items():
            found_path, found = _find_inner_json_string(item, [*path, key])
            if found is not None:
                return found_path, found
    if isinstance(value, list):
        for index, item in enumerate(value):
            found_path, found = _find_inner_json_string(item, [*path, index])
            if found is not None:
                return found_path, found
    return [], None


def parse_request_sample(raw: str) -> ParsedRequestSample:
    method, url, headers, raw_body = _parse_curl_sample(raw)
    parsed_url = urlparse(url)
    path = parsed_url.path or "/"
    if parsed_url.query:
        path = f"{path}?{parsed_url.query}"
    body: Any = None
    if raw_body:
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise BfkError(f"request sample body is not valid JSON: {exc}") from exc
    inner_path, inner_payload = _find_inner_json_string(body)
    return ParsedRequestSample(
        raw=raw.strip(),
        method=method,
        url=url,
        path=path,
        headers=headers,
        body=body,
        inner_json_path=inner_path,
        inner_payload=inner_payload,
    )


def _path_display(path: list[str | int]) -> str:
    result = "body"
    for part in path:
        if isinstance(part, int):
            result += f"[{part}]"
        else:
            result += f".{part}"
    return result


def _request_contract_lines(sample: ParsedRequestSample, method: str, path: str) -> list[str]:
    lines = [
        f"- Transport: HTTP JSON",
        f"- Method: {method}",
        f"- Path: {path}",
    ]
    if isinstance(sample.body, dict) and sample.body.get("model") is not None:
        lines.append(f"- Model: {sample.body['model']}")
    if sample.inner_json_path:
        lines += [
            f"- User payload path: {_path_display(sample.inner_json_path)}",
            "- User payload encoding: JSON string",
        ]
    if sample.inner_payload:
        action = sample.inner_payload.get("action")
        params = sample.inner_payload.get("params") if isinstance(sample.inner_payload.get("params"), dict) else {}
        if action is not None:
            lines.append(f"- Action: {action}")
        if isinstance(params, dict) and params.get("merge_type") is not None:
            lines.append(f"- Merge type: {params['merge_type']}")
    return lines


def _flatten_dict(value: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    flattened: list[tuple[str, Any]] = []
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            flattened.extend(_flatten_dict(item, path))
        else:
            flattened.append((path, item))
    return flattened


def _mapping_default(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text in {"file", "project", "true", "false"}:
        return text
    return "sample"


def _is_optional_mapping(name: str) -> bool:
    return name in {"eval", "stream", "model", "merge_preference", "merge_strategy", "resume", "answers"}


def _param_name_for_path(path: str) -> str:
    parts = path.split(".")
    if len(parts) == 1:
        return parts[0]
    if parts[0] in {"source", "target", "base"}:
        return f"{parts[0]}_{'_'.join(parts[1:])}"
    return "_".join(parts)


def _append_mapping(
    mappings: list[ParameterMapping],
    seen: set[str],
    *,
    name: str,
    locations: list[str],
    value: Any,
    source: str = "sample",
) -> None:
    if name in seen:
        return
    seen.add(name)
    mappings.append(
        ParameterMapping(
            name=name,
            locations=locations,
            required=not _is_optional_mapping(name),
            default=_mapping_default(value),
            source=source,
        )
    )


def _parameter_mappings_from_sample(sample: ParsedRequestSample | None) -> list[ParameterMapping]:
    if sample is None:
        return []
    mappings: list[ParameterMapping] = []
    seen: set[str] = set()
    if isinstance(sample.body, dict):
        if "model" in sample.body:
            _append_mapping(mappings, seen, name="model", locations=["body.model"], value=sample.body.get("model"))
        if "stream" in sample.body:
            _append_mapping(mappings, seen, name="stream", locations=["body.stream"], value=sample.body.get("stream"))
    inner = sample.inner_payload or {}
    if "eval" in inner:
        _append_mapping(mappings, seen, name="eval", locations=["text.eval"], value=inner.get("eval"), source="sample+code")
    params = inner.get("params")
    if not isinstance(params, dict):
        return mappings

    for shared_name in ("code", "biz_type", "project_code", "tenant_code", "project_sub_type"):
        source = params.get("source")
        target = params.get("target")
        if isinstance(source, dict) and isinstance(target, dict) and source.get(shared_name) == target.get(shared_name):
            _append_mapping(
                mappings,
                seen,
                name=shared_name,
                locations=[f"text.params.source.{shared_name}", f"text.params.target.{shared_name}"],
                value=source.get(shared_name),
            )

    for path, value in _flatten_dict(params):
        _append_mapping(
            mappings,
            seen,
            name=_param_name_for_path(path),
            locations=[f"text.params.{path}"],
            value=value,
            source="sample+code" if path in {"task_id", "merge_code", "merge_type"} else "sample",
        )
    return mappings


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _mapping_table_row(mapping: ParameterMapping) -> str:
    return (
        f"| {_escape_table_cell(mapping.name)} "
        f"| {_escape_table_cell(', '.join(mapping.locations))} "
        f"| {'yes' if mapping.required else 'no'} "
        f"| {_escape_table_cell(mapping.default)} "
        f"| {_escape_table_cell(mapping.source)} |"
    )


def _read_request_sample_from_project(text: str) -> str:
    match = re.search(
        r"^## Request Sample:[^\n]*\n+```(?:bash|sh)?\n(?P<body>.*?)\n```",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group("body").strip() if match else ""


def _read_parameter_mappings(text: str) -> list[ParameterMapping]:
    body = _section_body(text, "Parameter Contract")
    mappings: list[ParameterMapping] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped or "Name" in stripped:
            continue
        cells = [cell.strip().replace("\\|", "|") for cell in stripped.strip("|").split("|")]
        if len(cells) < 5:
            continue
        name, location, required, default, source = cells[:5]
        mappings.append(
            ParameterMapping(
                name=name,
                locations=[item.strip() for item in location.split(",") if item.strip()],
                required=required.lower() == "yes",
                default=default,
                source=source,
            )
        )
    return mappings


def _iter_evidence_files(root: Path) -> list[Path]:
    ignored_dirs = {".git", ".bfk", ".venv", "venv", "__pycache__", "node_modules", "dist", "build"}
    allowed_suffixes = {".py", ".md", ".sh", ".json", ".yaml", ".yml", ".toml", ".txt"}
    files: list[Path] = []
    for path in root.rglob("*"):
        if any(part in ignored_dirs for part in path.parts):
            continue
        if path.is_file() and (path.suffix in allowed_suffixes or path.name in {"AGENTS.md", "README"}):
            files.append(path)
    return files


def _infer_repository_evidence(
    root: Path,
    sample: ParsedRequestSample | None,
    mappings: list[ParameterMapping],
    *,
    limit: int = 8,
) -> list[str]:
    if sample is None:
        return []
    targets: list[tuple[str, str]] = []
    if sample.path:
        targets.append(("endpoint", sample.path))
    if isinstance(sample.body, dict) and sample.body.get("model"):
        targets.append(("model", str(sample.body["model"])))
    if sample.inner_payload and sample.inner_payload.get("action"):
        targets.append(("action", str(sample.inner_payload["action"])))
    for name in ("task_id", "merge_code", "merge_type"):
        if any(mapping.name == name for mapping in mappings):
            targets.append(("field", name))
    targets += [("request model", "CreateResponseRequest"), ("inner parsing", "json.loads")]

    evidence: list[str] = []
    seen: set[tuple[str, str]] = set()
    for file in _iter_evidence_files(root):
        try:
            lines = file.read_text(errors="ignore").splitlines()
        except OSError:
            continue
        rel = file.relative_to(root)
        for line_number, line in enumerate(lines, start=1):
            for label, target in targets:
                if target and target in line:
                    key = (label, target)
                    if key in seen:
                        continue
                    seen.add(key)
                    evidence.append(f"{label}: {rel}:{line_number} contains `{target}`")
                    if len(evidence) >= limit:
                        return evidence
    return evidence


def _read_project_config(root: Path) -> ProjectConfig:
    project = bfk_root(root) / "PROJECT.md"
    if not project.exists():
        raise BfkError("Missing .bfk/PROJECT.md. Run $bfk-capture with project/request context first.")
    text = project.read_text()
    base_match = re.search(r"Base URL:\s*(\S+)", text)
    if not base_match:
        raise BfkError(".bfk/PROJECT.md is missing Base URL. Run $bfk-capture with service context again.")

    logs = re.findall(r"^-\s+(.+\.log)\s*$", _section_body(text, "Logs"), flags=re.MULTILINE)
    header_lines = re.findall(r"^-\s+([^:]+):\s*(.*)\s*$", _section_body(text, "Request Defaults"), flags=re.MULTILINE)
    headers = {key.strip(): value.strip() for key, value in header_lines}
    endpoint = _project_bullet_value(text, "Endpoint") or _project_bullet_value(text, "Primary endpoint")
    method, endpoint_path = _parse_endpoint_text(endpoint)
    wait = _parse_float(_project_bullet_value(text, "After request wait seconds"), default=2)

    request_sample = _read_request_sample_from_project(text)
    parsed_sample = None
    if request_sample:
        parsed_sample = parse_request_sample(request_sample)
        if endpoint_path == "/":
            method, endpoint_path = _resolve_endpoint("", parsed_sample)

    mappings = _read_parameter_mappings(text)
    if parsed_sample and not mappings:
        mappings = _parameter_mappings_from_sample(parsed_sample)

    return ProjectConfig(
        base_url=base_match.group(1),
        log_files=logs or ["logs/app.log"],
        headers=headers or {"Content-Type": "application/json"},
        endpoint_method=method,
        endpoint_path=endpoint_path,
        after_request_wait_seconds=wait,
        request_sample=parsed_sample,
        parameter_mappings=mappings,
    )


def _read_project_defaults(root: Path) -> tuple[str, list[str], dict[str, str]]:
    config = _read_project_config(root)
    return config.base_url, config.log_files, config.headers


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
    config = _read_project_config(root)
    issue_dir = bfk_root(root)
    issue_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "issue.md",
        "runner.py",
        "request.json",
        "response.json",
        "output.log",
        "capture.md",
        "root-cause.md",
        "fix.md",
    ):
        (issue_dir / name).unlink(missing_ok=True)

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
                "Capture evidence, locate root cause, and fix minimally.",
            ]
        )
        + "\n"
    )
    if config.request_sample:
        runner = _request_contract_runner_template(issue_name, params, config)
    else:
        runner = _runner_template(issue_name, params, config)
    (issue_dir / "runner.py").write_text(runner)
    return issue_dir


def _runner_template(
    issue_name: str,
    params: dict[str, str],
    config: ProjectConfig,
) -> str:
    base_url = config.base_url
    log_files = config.log_files
    headers = config.headers
    method = config.endpoint_method or "POST"
    endpoint_path = config.endpoint_path or "/"
    return f'''# Bug Fix Kit Issue Runner

import json

ISSUE_NAME = {issue_name!r}
PARAMS = {json.dumps(params, ensure_ascii=False, indent=2)}
BASE_URL = {base_url!r}
REQUEST_METHOD = {method!r}
REQUEST_PATH = {endpoint_path!r}
LOG_FILES = {json.dumps(log_files, ensure_ascii=False, indent=2)}
DEFAULT_HEADERS = {json.dumps(headers, ensure_ascii=False, indent=2)}
AFTER_REQUEST_WAIT_SECONDS = {config.after_request_wait_seconds!r}


def build_request(params: dict) -> dict:
    headers = dict(DEFAULT_HEADERS)
    headers["X-BugFix-Issue"] = ISSUE_NAME
    return {{
        "method": REQUEST_METHOD,
        "url": f"{{BASE_URL.rstrip('/')}}{{REQUEST_PATH}}",
        "headers": headers,
        "json": params,
    }}


if __name__ == "__main__":
    print(json.dumps(build_request(PARAMS), ensure_ascii=False, indent=2))
'''


def _request_contract_runner_template(issue_name: str, params: dict[str, str], config: ProjectConfig) -> str:
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
    return f'''# Bug Fix Kit Issue Runner

import copy
import json
import os
import re

ISSUE_NAME = {issue_name!r}
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
    headers["X-BugFix-Issue"] = ISSUE_NAME
    return {{
        "method": template.get("method", "POST"),
        "url": f"{{BASE_URL.rstrip('/')}}{{template.get('path', '/')}}",
        "headers": headers,
        "json": body,
    }}


if __name__ == "__main__":
    print(json.dumps(build_request(PARAMS), ensure_ascii=False, indent=2))
'''


def latest_issue(root: Path) -> Path:
    path = bfk_root(root)
    if not (path / "issue.md").exists() and not (path / "runner.py").exists():
        raise BfkError("No bfk capture found. Run $bfk-capture first.")
    return path


def next_iteration_dir(issue_dir: Path) -> Path:
    issue_dir.mkdir(parents=True, exist_ok=True)
    return issue_dir


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
