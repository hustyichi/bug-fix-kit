from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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
    }


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
            return _response_result(response.status, response.headers, response.read(), started)
    except HTTPError as exc:
        return _response_result(exc.code, exc.headers, exc.read(), started)
    except (OSError, URLError, ValueError, TypeError) as exc:
        return _transport_error_result(exc, started)
