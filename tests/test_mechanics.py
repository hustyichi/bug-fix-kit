from __future__ import annotations

import io
import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

import bug_fix_kit.mechanics.artifacts as mechanics_artifacts
from bug_fix_kit.mechanics import (BfkError, archive_current_capture,
                                   capture_offsets, create_capture,
                                   execute_request, latest_capture,
                                   load_runner_request, read_since_offsets,
                                   write_run_artifacts)
from bug_fix_kit.mechanics.http import DEFAULT_REQUEST_TIMEOUT_SECONDS


def responses_project_merge_curl() -> str:
    inner = {
        "action": "project-merge",
        "eval": "1232",
        "params": {
            "merge_type": "file",
            "task_id": "sample-task",
            "source": {
                "code": "LGI-sample",
                "biz_type": "page_logic",
                "iteration_code": "ITE-source",
                "project_code": "PRJ-sample",
                "tenant_code": "TNT-sample",
            },
            "merge_code": "MER-sample",
            "merge_preference": None,
            "target": {
                "code": "LGI-sample",
                "biz_type": "page_logic",
                "iteration_code": "ITE-target",
                "project_code": "PRJ-sample",
                "tenant_code": "TNT-sample",
            },
        },
    }
    body = {
        "model": "agentic-upgrader",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(inner, ensure_ascii=False),
                        "sub_type": None,
                    }
                ],
            }
        ],
        "stream": False,
        "previous_response_id": None,
        "store": None,
        "temperature": None,
        "max_tokens": None,
        "background": None,
    }
    return (
        "curl --location --request POST 'http://127.0.0.1:8000/v1/responses' "
        "--header 'x-litellm-api-key: Bearer sk-secret' "
        "--header 'Content-Type: application/json' "
        f"--data-raw '{json.dumps(body, ensure_ascii=False)}'"
    )


def test_create_capture_scaffolds_current_capture_without_persistent_context(tmp_path: Path):
    capture = create_capture(
        tmp_path,
        ["account=13900000000", "freeform"],
        base_url="http://localhost:8000",
        log_files=["logs/app.log"],
        default_headers={"Content-Type": "application/json"},
    )

    assert capture == tmp_path / ".bfk"
    runner = capture / "runner.py"
    assert runner.exists()
    assert "Bug Fix Kit Capture Runner" in runner.read_text()
    assert ("Bug Fix Kit " + "Issue " + "Runner") not in runner.read_text()
    assert latest_capture(tmp_path) == capture

    request = load_runner_request(runner)
    assert request["method"] == "POST"
    assert request["url"].startswith("http://localhost:8000")
    assert request["headers"]["Content-Type"] == "application/json"
    assert ("X-BugFix-" + "Issue") not in request["headers"]
    assert request["json"]["account"] == "13900000000"


def test_create_capture_preserves_request_contract_with_local_auth(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "api.py").write_text(
        "@router.post('/v1/responses')\nclass CreateResponseRequest: ...\njson.loads(user_text)\n"
    )

    capture = create_capture(
        tmp_path,
        ["task_id=new-task"],
        base_url="http://127.0.0.1:8000",
        log_files=["logs/app.log"],
        request_sample=responses_project_merge_curl(),
    )

    request = load_runner_request(capture / "runner.py")
    assert request["url"] == "http://127.0.0.1:8000/v1/responses"
    assert request["headers"]["x-litellm-api-key"] == "Bearer sk-secret"


def test_request_sample_runner_reconstructs_full_request_with_replacements(tmp_path: Path):
    capture = create_capture(
        tmp_path,
        [
            "task_id=new-task",
            "merge_code=MER-new",
            "source_iteration_code=ITE-source-new",
            "code=LGI-new",
            "stream=true",
        ],
        base_url="http://localhost:8000",
        log_files=["logs/app.log"],
        request_sample=responses_project_merge_curl(),
    )

    request = load_runner_request(capture / "runner.py")
    body = request["json"]
    inner = json.loads(body["input"][0]["content"][0]["text"])

    assert request["method"] == "POST"
    assert request["url"] == "http://localhost:8000/v1/responses"
    assert request["headers"]["x-litellm-api-key"] == "Bearer sk-secret"
    assert body["model"] == "agentic-upgrader"
    assert body["stream"] is True
    assert inner["params"]["task_id"] == "new-task"
    assert inner["params"]["merge_code"] == "MER-new"
    assert inner["params"]["source"]["iteration_code"] == "ITE-source-new"
    assert inner["params"]["target"]["iteration_code"] == "ITE-target"
    assert inner["params"]["source"]["code"] == "LGI-new"
    assert inner["params"]["target"]["code"] == "LGI-new"


def test_create_capture_archives_current_capture_before_replacing_it(tmp_path: Path):
    bfk = tmp_path / ".bfk"
    bfk.mkdir()
    for name in [
        "runner.py",
        "request.json",
        "response.json",
        "output.log",
        "fix_output.log",
        "root-cause.md",
        "fix-plan.md",
        "fix.md",
    ]:
        (bfk / name).write_text("stale")

    capture = create_capture(tmp_path, ["account=2"], base_url="http://localhost:8000", log_files=["logs/app.log"])

    assert capture == bfk
    assert (bfk / "runner.py").exists()
    assert not (bfk / "request.json").exists()
    assert not (bfk / "response.json").exists()
    assert not (bfk / "output.log").exists()
    assert not (bfk / "fix_output.log").exists()
    assert not (bfk / "root-cause.md").exists()
    assert not (bfk / "fix-plan.md").exists()
    assert not (bfk / "fix.md").exists()
    archive_dirs = sorted((bfk / "archive").iterdir())
    assert len(archive_dirs) == 1
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}", archive_dirs[0].name)
    assert {path.name for path in archive_dirs[0].iterdir()} == {
        "runner.py",
        "request.json",
        "response.json",
        "output.log",
        "fix_output.log",
        "root-cause.md",
        "fix-plan.md",
        "fix.md",
    }
    for name in [
        "runner.py",
        "request.json",
        "response.json",
        "output.log",
        "fix_output.log",
        "root-cause.md",
        "fix-plan.md",
        "fix.md",
    ]:
        assert (archive_dirs[0] / name).read_text() == "stale"


def test_create_capture_does_not_archive_runner_only_scaffold(tmp_path: Path):
    bfk = tmp_path / ".bfk"
    bfk.mkdir()
    (bfk / "runner.py").write_text("incomplete first-run scaffold")

    create_capture(tmp_path, ["account=2"], base_url="http://localhost:8000", log_files=["logs/app.log"])

    assert not (bfk / "archive").exists()
    assert "incomplete first-run scaffold" not in (bfk / "runner.py").read_text()


def test_archive_current_capture_uses_readable_timestamp_suffixes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    bfk = tmp_path / ".bfk"
    bfk.mkdir()
    (bfk / "runner.py").write_text("first")
    (bfk / "output.log").write_text("first log")

    class FixedDatetime:
        @classmethod
        def now(cls):
            return cls()

        def strftime(self, _format: str) -> str:
            return "2026-06-29_13-30-12"

    monkeypatch.setattr(mechanics_artifacts, "datetime", FixedDatetime)
    assert archive_current_capture(bfk) == bfk / "archive" / "2026-06-29_13-30-12"

    (bfk / "runner.py").write_text("second")
    (bfk / "output.log").write_text("second log")
    assert archive_current_capture(bfk) == bfk / "archive" / "2026-06-29_13-30-12-2"


def test_log_offsets_read_only_appended_content_and_truncation(tmp_path: Path):
    log = tmp_path / "app.log"
    log.write_text("before\n")
    offsets = capture_offsets([log])
    log.write_text("before\nafter\n")
    assert read_since_offsets(offsets) == "after\n"

    offsets = capture_offsets([log])
    log.write_text("new\n")
    assert "new\n" in read_since_offsets(offsets)


def test_write_run_artifacts(tmp_path: Path):
    capture = tmp_path / ".bfk"
    response = {"status_code": 200, "headers": {}, "body": {"ok": True}, "body_text": None, "empty_body": False, "elapsed_ms": 1, "transport_error": None}

    write_run_artifacts(capture, {"method": "GET", "url": "http://x"}, response, "log")

    assert json.loads((capture / "request.json").read_text())["method"] == "GET"
    assert json.loads((capture / "response.json").read_text())["body"] == {"ok": True}
    assert (capture / "output.log").read_text() == "log"


def test_write_run_artifacts_can_write_fix_output_without_overwriting_capture_log(tmp_path: Path):
    capture = tmp_path / ".bfk"
    response = {"status_code": 200, "headers": {}, "body": {"ok": True}, "body_text": None, "empty_body": False, "elapsed_ms": 1, "transport_error": None}
    capture.mkdir()
    (capture / "output.log").write_text("original failure log")

    write_run_artifacts(
        capture,
        {"method": "GET", "url": "http://x"},
        response,
        "fix verification log",
        output_log_name="fix_output.log",
    )

    assert (capture / "output.log").read_text() == "original failure log"
    assert (capture / "fix_output.log").read_text() == "fix verification log"


def test_execute_request_normalizes_transport_errors(monkeypatch: pytest.MonkeyPatch):
    def fail(*_args, **_kwargs):
        raise URLError("connection refused")

    monkeypatch.setattr("bug_fix_kit.mechanics.http.urlopen", fail)

    response = execute_request({"method": "GET", "url": "http://127.0.0.1:1"}, timeout=1)

    assert response["status_code"] is None
    assert response["body"] is None
    assert response["body_text"] is None
    assert response["transport_error"]["type"] == "transport_error"
    assert "connection refused" in response["transport_error"]["message"]


def test_execute_request_default_timeout_allows_long_running_tasks(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, int | float] = {}

    class Headers:
        def items(self):
            return {}

        def get(self, _key: str, default: str = "") -> str:
            return default

    class FakeResponse:
        status = 200
        headers = Headers()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(_request, *, timeout):
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("bug_fix_kit.mechanics.http.urlopen", fake_urlopen)

    response = execute_request({"method": "GET", "url": "http://example.test"})

    assert response["status_code"] == 200
    assert captured["timeout"] == DEFAULT_REQUEST_TIMEOUT_SECONDS
    assert captured["timeout"] >= 300


def test_execute_request_captures_sse_stream_until_done(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, int | float] = {}

    class Headers(dict):
        def items(self):
            return super().items()

    class FakeResponse:
        status = 200
        headers = Headers({"Content-Type": "text/event-stream"})

        def __init__(self):
            self.lines = iter([
                b'data: {"delta": "hello"}\n',
                b"\n",
                b"data: [DONE]\n",
                b"data: late\n",
            ])

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def readline(self):
            return next(self.lines, b"")

        def read(self):
            raise AssertionError("streaming responses should be read incrementally")

    def fake_urlopen(_request, *, timeout):
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("bug_fix_kit.mechanics.http.urlopen", fake_urlopen)

    response = execute_request({"method": "POST", "url": "http://example.test", "json": {"stream": True}})

    assert response["status_code"] == 200
    assert response["body"] is None
    assert '{"delta": "hello"}' in response["body_text"]
    assert "late" not in response["body_text"]
    assert response["stream"]["detected"] is True
    assert response["stream"]["complete"] is True
    assert response["stream"]["truncated"] is False
    assert response["stream"]["events"] == [
        {"type": "sse_data", "data": '{"delta": "hello"}'},
        {"type": "sse_data", "data": "[DONE]"},
    ]
    assert captured["timeout"] == DEFAULT_REQUEST_TIMEOUT_SECONDS


def test_execute_request_preserves_partial_stream_on_idle_timeout(monkeypatch: pytest.MonkeyPatch):
    class Headers(dict):
        def items(self):
            return super().items()

    class SlowResponse:
        status = 200
        headers = Headers({"Content-Type": "text/event-stream"})

        def __init__(self):
            self.calls = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def readline(self):
            self.calls += 1
            if self.calls == 1:
                return b"data: partial\n"
            raise TimeoutError("idle timeout")

    monkeypatch.setattr("bug_fix_kit.mechanics.http.urlopen", lambda *_args, **_kwargs: SlowResponse())

    response = execute_request({"method": "GET", "url": "http://example.test", "capture_stream": True}, timeout=1)

    assert response["status_code"] == 200
    assert response["body_text"] == "data: partial\n"
    assert response["transport_error"] is None
    assert response["stream"]["detected"] is True
    assert response["stream"]["complete"] is False
    assert response["stream"]["error"]["type"] == "TimeoutError"
    assert "idle timeout" in response["stream"]["error"]["message"]


def test_execute_request_truncates_stream_response(monkeypatch: pytest.MonkeyPatch):
    class Headers(dict):
        def items(self):
            return super().items()

    class LargeResponse:
        status = 200
        headers = Headers({"Content-Type": "application/x-ndjson"})

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def readline(self):
            return b'{"token": "abcdef"}\n'

    monkeypatch.setattr("bug_fix_kit.mechanics.http.urlopen", lambda *_args, **_kwargs: LargeResponse())

    response = execute_request({"method": "GET", "url": "http://example.test"}, max_response_bytes=8)

    assert response["body_text"] == '{"token"'
    assert response["stream"]["detected"] is True
    assert response["stream"]["complete"] is False
    assert response["stream"]["truncated"] is True
    assert response["stream"]["bytes_captured"] == 8


def test_latest_capture_requires_existing_runner(tmp_path: Path):
    with pytest.raises(BfkError, match=r"Run \$bfk-capture first"):
        latest_capture(tmp_path)


def test_generated_runner_runs_directly_and_prints_json(tmp_path: Path):
    import subprocess
    import sys

    capture = create_capture(tmp_path, ["account=13900000000"], base_url="http://localhost:8000", log_files=["logs/app.log"])

    result = subprocess.run(
        [sys.executable, str(capture / "runner.py")],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["json"]["account"] == "13900000000"


def test_latest_capture_uses_current_capture_root(tmp_path: Path):
    create_capture(tmp_path, base_url="http://localhost:8000", log_files=["logs/app.log"])

    assert latest_capture(tmp_path) == tmp_path / ".bfk"


def test_empty_capture_replays_existing_runner_without_new_context(tmp_path: Path):
    first = create_capture(tmp_path, ["account=1"], base_url="http://localhost:8000", log_files=["logs/app.log"])
    before = (first / "runner.py").read_text()

    replay = create_capture(tmp_path)

    assert replay == first
    assert (replay / "runner.py").read_text() == before
    assert not (first / "archive").exists()


def test_capture_with_params_requires_new_request_context(tmp_path: Path):
    create_capture(tmp_path, ["account=1"], base_url="http://localhost:8000", log_files=["logs/app.log"])

    with pytest.raises(BfkError, match="request context"):
        create_capture(tmp_path, ["account=2"])


def test_load_runner_rejects_missing_or_malformed_build_request(tmp_path: Path):
    missing = tmp_path / "missing_build_request.py"
    missing.write_text("PARAMS = {}\n")
    with pytest.raises(BfkError, match="PARAMS and build_request"):
        load_runner_request(missing)

    malformed = tmp_path / "malformed_request.py"
    malformed.write_text("PARAMS = {}\ndef build_request(params):\n    return {'method': 'GET'}\n")
    with pytest.raises(BfkError, match="method and url"):
        load_runner_request(malformed)


def test_execute_request_normalizes_json_text_empty_and_http_error(monkeypatch: pytest.MonkeyPatch):
    class Headers(dict):
        def items(self):
            return super().items()

    class FakeResponse:
        def __init__(self, status: int, data: bytes, content_type: str):
            self.status = status
            self._data = data
            self.headers = Headers({"Content-Type": content_type, "X-Test": "yes"})

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return self._data

    responses = iter([
        FakeResponse(200, b'{"ok": true}', "application/json"),
        FakeResponse(200, b'plain text', "text/plain"),
        FakeResponse(204, b'', "text/plain"),
    ])
    monkeypatch.setattr("bug_fix_kit.mechanics.http.urlopen", lambda *_args, **_kwargs: next(responses))

    json_response = execute_request({"method": "GET", "url": "http://example.test"})
    assert json_response["body"] == {"ok": True}
    assert json_response["body_text"] is None
    assert json_response["headers"]["X-Test"] == "yes"

    text_response = execute_request({"method": "GET", "url": "http://example.test"})
    assert text_response["body"] is None
    assert text_response["body_text"] == "plain text"

    empty_response = execute_request({"method": "GET", "url": "http://example.test"})
    assert empty_response["empty_body"] is True
    assert empty_response["body"] is None
    assert empty_response["body_text"] is None


def test_execute_request_normalizes_http_errors(monkeypatch: pytest.MonkeyPatch):
    def fail(*_args, **_kwargs):
        raise HTTPError(
            "http://example.test",
            422,
            "Unprocessable Entity",
            {"Content-Type": "application/json", "X-Test": "yes"},
            io.BytesIO(b'{"error": "bad"}'),
        )

    monkeypatch.setattr("bug_fix_kit.mechanics.http.urlopen", fail)

    response = execute_request(
        {"method": "POST", "url": "http://example.test", "json": {"id": 1}}
    )

    assert response["status_code"] == 422
    assert response["headers"]["X-Test"] == "yes"
    assert response["body"] == {"error": "bad"}
    assert response["body_text"] is None
    assert response["transport_error"] is None


def test_log_truncation_is_explicit(tmp_path: Path):
    log = tmp_path / "app.log"
    log.write_text("before\nlonger\n")
    offsets = capture_offsets([log])
    log.write_text("new\n")

    output = read_since_offsets(offsets)

    assert "truncated" in output
    assert "new\n" in output


def test_project_headers_are_preserved_in_generated_runner(tmp_path: Path):
    capture = create_capture(
        tmp_path,
        ["account=1"],
        base_url="http://localhost:8000",
        log_files=["logs/app.log"],
        default_headers={"Content-Type": "application/json", "Authorization": "Bearer devtoken"},
    )

    request = load_runner_request(capture / "runner.py")

    assert request["headers"]["Authorization"] == "Bearer devtoken"
    assert request["headers"]["Content-Type"] == "application/json"
    assert ("X-BugFix-" + "Issue") not in request["headers"]
