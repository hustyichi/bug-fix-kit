from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_REQUEST_TIMEOUT_SECONDS = 600.0
DEFAULT_MAX_RESPONSE_BYTES = 10 * 1024 * 1024
MAX_STREAM_EVENTS = 1000


def _body_payload(data: bytes, content_type: str) -> tuple[Any, str | None, bool]:
    if not data:
        return None, None, True
    text = data.decode("utf-8", errors="replace")
    if "json" in content_type.lower():
        try:
            return json.loads(text), None, False
        except json.JSONDecodeError:
            return None, text, False
    return None, text, False


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _response_result(
    status_code: int,
    headers: Any,
    data: bytes,
    started: float,
    *,
    stream: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parsed, text, empty = _body_payload(data, headers.get("Content-Type", ""))
    return {
        "status_code": status_code,
        "headers": dict(headers.items()),
        "body": parsed,
        "body_text": text,
        "empty_body": empty,
        "elapsed_ms": _elapsed_ms(started),
        "transport_error": None,
        "stream": stream or {"detected": False},
    }


def _transport_error_result(exc: BaseException, started: float) -> dict[str, Any]:
    return {
        "status_code": None,
        "headers": {},
        "body": None,
        "body_text": None,
        "empty_body": False,
        "elapsed_ms": _elapsed_ms(started),
        "transport_error": {"type": "transport_error", "message": str(exc)},
        "stream": {"detected": False},
    }


def _request_wants_stream(request: dict[str, Any]) -> bool:
    if bool(request.get("capture_stream")):
        return True
    payload = request.get("json")
    return isinstance(payload, dict) and payload.get("stream") is True


def _header_value(headers: Any, name: str) -> str:
    try:
        return str(headers.get(name, ""))
    except AttributeError:
        return ""


def _is_streaming_response(request: dict[str, Any], headers: Any) -> bool:
    content_type = _header_value(headers, "Content-Type").lower()
    transfer_encoding = _header_value(headers, "Transfer-Encoding").lower()
    return (
        _request_wants_stream(request)
        or "text/event-stream" in content_type
        or "application/x-ndjson" in content_type
        or "ndjson" in content_type
        or "chunked" in transfer_encoding
    )


def _append_capped(chunks: list[bytes], chunk: bytes, total: int, max_bytes: int) -> tuple[int, bool]:
    remaining = max_bytes - total
    if remaining <= 0:
        return total, True
    chunks.append(chunk[:remaining])
    total += min(len(chunk), remaining)
    return total, len(chunk) > remaining


def _stream_event_from_line(line: str) -> dict[str, str] | None:
    stripped = line.rstrip("\r\n")
    if not stripped:
        return None
    if stripped.startswith("data:"):
        return {"type": "sse_data", "data": stripped[5:].strip()}
    return {"type": "line", "data": stripped}


def _read_stream_body(response: Any, *, max_bytes: int) -> tuple[bytes, dict[str, Any]]:
    chunks: list[bytes] = []
    events: list[dict[str, str]] = []
    total = 0
    event_count = 0
    truncated = False
    events_truncated = False
    complete = False
    error: dict[str, str] | None = None

    try:
        while True:
            chunk = response.readline()
            if not chunk:
                complete = True
                break
            if not isinstance(chunk, bytes):
                chunk = str(chunk).encode()
            total, chunk_truncated = _append_capped(chunks, chunk, total, max_bytes)
            truncated = truncated or chunk_truncated

            line = chunk.decode("utf-8", errors="replace")
            event = _stream_event_from_line(line)
            if event is not None:
                event_count += 1
                if len(events) < MAX_STREAM_EVENTS:
                    events.append(event)
                else:
                    events_truncated = True
                if event["type"] == "sse_data" and event["data"] == "[DONE]":
                    complete = True
                    break

            if truncated:
                break
    except OSError as exc:
        error = {"type": exc.__class__.__name__, "message": str(exc)}

    stream = {
        "detected": True,
        "complete": complete,
        "truncated": truncated,
        "bytes_captured": total,
        "event_count": event_count,
        "events_truncated": events_truncated,
        "events": events,
        "error": error,
    }
    return b"".join(chunks), stream


def execute_request(
    request: dict[str, Any],
    timeout: int | float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    *,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> dict[str, Any]:
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
            if _is_streaming_response(request, response.headers):
                data, stream = _read_stream_body(response, max_bytes=max_response_bytes)
                return _response_result(response.status, response.headers, data, started, stream=stream)
            return _response_result(response.status, response.headers, response.read(), started)
    except HTTPError as exc:
        return _response_result(exc.code, exc.headers, exc.read(), started)
    except (OSError, URLError, ValueError, TypeError) as exc:
        return _transport_error_result(exc, started)
