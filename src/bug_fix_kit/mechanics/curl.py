from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from .errors import BfkError


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
