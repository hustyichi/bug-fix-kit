from __future__ import annotations

import json
from pathlib import Path
from urllib.error import URLError

import pytest

from bug_fix_kit.mechanics import (
    BfkError,
    capture_offsets,
    create_capture,
    execute_request,
    latest_capture,
    load_runner_request,
    next_iteration_dir,
    read_since_offsets,
    write_run_artifacts,
)


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
    assert not (capture / "PROJECT.md").exists()
    assert not (capture / "issue.md").exists()
    runner = capture / "runner.py"
    assert runner.exists()
    assert latest_capture(tmp_path) == capture

    request = load_runner_request(runner)
    assert request["method"] == "POST"
    assert request["url"].startswith("http://localhost:8000")
    assert request["headers"]["Content-Type"] == "application/json"
    assert "X-BugFix-Issue" not in request["headers"]
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
    assert not (capture / "PROJECT.md").exists()
    assert not (capture / "issue.md").exists()


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


def test_create_capture_replaces_current_capture_and_clears_stale_state(tmp_path: Path):
    bfk = tmp_path / ".bfk"
    bfk.mkdir()
    for name in ["PROJECT.md", "issue.md", "runner.py", "request.json", "response.json", "output.log", "fix_output.log", "root-cause.md", "fix.md"]:
        (bfk / name).write_text("stale")

    capture = create_capture(tmp_path, ["account=2"], base_url="http://localhost:8000", log_files=["logs/app.log"])

    assert capture == bfk
    assert not (bfk / "PROJECT.md").exists()
    assert not (bfk / "issue.md").exists()
    assert (bfk / "runner.py").exists()
    assert not (bfk / "request.json").exists()
    assert not (bfk / "response.json").exists()
    assert not (bfk / "output.log").exists()
    assert not (bfk / "fix_output.log").exists()
    assert not (bfk / "root-cause.md").exists()
    assert not (bfk / "fix.md").exists()


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
    iteration = tmp_path / "001"
    response = {"status_code": 200, "headers": {}, "body": {"ok": True}, "body_text": None, "empty_body": False, "elapsed_ms": 1, "transport_error": None}

    write_run_artifacts(iteration, {"method": "GET", "url": "http://x"}, response, "log")

    assert json.loads((iteration / "request.json").read_text())["method"] == "GET"
    assert json.loads((iteration / "response.json").read_text())["body"] == {"ok": True}
    assert (iteration / "output.log").read_text() == "log"


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

    monkeypatch.setattr("bug_fix_kit.mechanics.urlopen", fail)

    response = execute_request({"method": "GET", "url": "http://127.0.0.1:1"}, timeout=1)

    assert response["status_code"] is None
    assert response["body"] is None
    assert response["body_text"] is None
    assert response["transport_error"]["type"] == "transport_error"
    assert "connection refused" in response["transport_error"]["message"]


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


def test_capture_with_params_requires_new_request_context(tmp_path: Path):
    create_capture(tmp_path, ["account=1"], base_url="http://localhost:8000", log_files=["logs/app.log"])

    with pytest.raises(BfkError, match="request context"):
        create_capture(tmp_path, ["account=2"])


def test_next_iteration_dir_is_obsolete_for_single_capture(tmp_path: Path):
    capture = tmp_path / ".bfk"
    capture.mkdir()

    assert next_iteration_dir(capture) == capture


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
    monkeypatch.setattr("bug_fix_kit.mechanics.urlopen", lambda *_args, **_kwargs: next(responses))

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
    assert "X-BugFix-Issue" not in request["headers"]
