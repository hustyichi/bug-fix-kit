from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_bfk(cwd: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged["PYTHONPATH"] = str(ROOT) + os.pathsep + merged.get("PYTHONPATH", "")
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, "-m", "bug_fix_kit", *args],
        cwd=cwd,
        env=merged,
        text=True,
        capture_output=True,
    )


def test_cli_exposes_expected_commands_and_not_diagnose_fix(tmp_path: Path):
    help_result = run_bfk(tmp_path, "--help")
    assert help_result.returncode == 0
    for command in ["install", "init-project", "new", "run", "doctor"]:
        assert command in help_result.stdout
    assert "diagnose" not in help_result.stdout
    assert " fix" not in help_result.stdout

    bad = run_bfk(tmp_path, "diagnose")
    assert bad.returncode != 0


def test_init_project_and_new_create_bfk_artifacts(tmp_path: Path):
    init = run_bfk(
        tmp_path,
        "init-project",
        "--base-url",
        "http://localhost:8000",
        "--log-file",
        "logs/app.log",
        "--header",
        "Content-Type=application/json",
        "--auth-note",
        "LOCAL_AUTH_TOKEN",
    )
    assert init.returncode == 0, init.stderr
    assert (tmp_path / ".bfk" / "PROJECT.md").exists()

    new = run_bfk(tmp_path, "new", "login failed", "account=13900000000")
    assert new.returncode == 0, new.stderr
    issue_dirs = list((tmp_path / ".bfk" / "issues").iterdir())
    assert len(issue_dirs) == 1
    assert (issue_dirs[0] / "runner.py").exists()
    assert "Created issue" in new.stdout


def test_run_command_creates_iteration_with_transport_error(tmp_path: Path):
    run_bfk(tmp_path, "init-project", "--base-url", "http://127.0.0.1:1", "--log-file", "missing.log")
    run_bfk(tmp_path, "new", "login", "account=13900000000")

    result = run_bfk(tmp_path, "run", "--timeout", "0.1")

    assert result.returncode == 0, result.stderr
    iteration = next((tmp_path / ".bfk" / "issues").iterdir()) / "iterations" / "001"
    assert (iteration / "request.json").exists()
    response = json.loads((iteration / "response.json").read_text())
    assert response["status_code"] is None
    assert response["transport_error"]
    assert (iteration / "output.log").exists()


def test_doctor_reports_plugin_shell(tmp_path: Path):
    result = run_bfk(tmp_path, "doctor")
    assert result.returncode == 0
    assert "plugin manifest" in result.stdout


def test_install_accepts_public_plugin_root_and_marketplace_flags(tmp_path: Path):
    marketplace = tmp_path / "home" / ".agents" / "plugins" / "marketplace.json"

    result = run_bfk(
        tmp_path,
        "install",
        "--plugin-root",
        str(ROOT),
        "--marketplace",
        str(marketplace),
        "--yes",
    )

    assert result.returncode == 0, result.stderr
    assert marketplace.exists()
    assert (tmp_path / "home" / "plugins" / "bug-fix-kit" / ".codex-plugin" / "plugin.json").exists()


def test_cli_non_goals_are_not_commands(tmp_path: Path):
    for command in ["status", "verify", "auto", "fix"]:
        result = run_bfk(tmp_path, command)
        assert result.returncode != 0


def test_module_entrypoint_preserves_handled_error_exit_code(tmp_path: Path):
    result = run_bfk(tmp_path, "run")
    assert result.returncode == 1
    assert "No bfk issues" in result.stderr


def test_new_requires_project_initialization(tmp_path: Path):
    result = run_bfk(tmp_path, "new", "login", "account=1")
    assert result.returncode == 1
    assert "$bfk-init" in result.stderr
    assert not (tmp_path / ".bfk" / "issues").exists()


def test_run_invalid_issue_id_returns_concise_error(tmp_path: Path):
    run_bfk(tmp_path, "init-project", "--base-url", "http://127.0.0.1:1", "--log-file", "missing.log")
    result = run_bfk(tmp_path, "run", "missing_issue")
    assert result.returncode == 1
    assert "issue not found" in result.stderr
    assert "Traceback" not in result.stderr


def test_run_runner_exception_writes_transport_error_iteration(tmp_path: Path):
    run_bfk(tmp_path, "init-project", "--base-url", "http://127.0.0.1:1", "--log-file", "missing.log")
    run_bfk(tmp_path, "new", "broken", "account=1")
    issue = next((tmp_path / ".bfk" / "issues").iterdir())
    (issue / "runner.py").write_text(
        "PARAMS = {}\nLOG_FILES = ['missing.log']\nAFTER_REQUEST_WAIT_SECONDS = 0\ndef build_request(params):\n    raise RuntimeError('boom')\n"
    )

    result = run_bfk(tmp_path, "run")

    assert result.returncode == 0, result.stderr
    iteration = issue / "iterations" / "001"
    response = json.loads((iteration / "response.json").read_text())
    assert response["status_code"] is None
    assert response["transport_error"]["type"] == "runner_error"
    assert "boom" in response["transport_error"]["message"]
    assert json.loads((iteration / "request.json").read_text())["runner_error"] == "boom"


def test_run_bad_url_writes_transport_error_without_traceback(tmp_path: Path):
    run_bfk(tmp_path, "init-project", "--base-url", "not-a-url", "--log-file", "missing.log")
    run_bfk(tmp_path, "new", "bad-url", "account=1")
    issue = next((tmp_path / ".bfk" / "issues").iterdir())

    result = run_bfk(tmp_path, "run")

    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    response = json.loads((issue / "iterations" / "001" / "response.json").read_text())
    assert response["status_code"] is None
    assert response["transport_error"]["type"] == "transport_error"


def test_run_runner_import_error_writes_iteration(tmp_path: Path):
    run_bfk(tmp_path, "init-project", "--base-url", "http://127.0.0.1:1", "--log-file", "missing.log")
    run_bfk(tmp_path, "new", "import-boom", "account=1")
    issue = next((tmp_path / ".bfk" / "issues").iterdir())
    (issue / "runner.py").write_text("raise RuntimeError('import boom')\n")

    result = run_bfk(tmp_path, "run")

    assert result.returncode == 0, result.stderr
    response = json.loads((issue / "iterations" / "001" / "response.json").read_text())
    assert response["transport_error"]["type"] == "runner_error"
    assert "import boom" in response["transport_error"]["message"]


def test_run_runner_config_error_writes_iteration(tmp_path: Path):
    run_bfk(tmp_path, "init-project", "--base-url", "http://127.0.0.1:1", "--log-file", "missing.log")
    run_bfk(tmp_path, "new", "bad-config", "account=1")
    issue = next((tmp_path / ".bfk" / "issues").iterdir())
    (issue / "runner.py").write_text(
        "PARAMS = {}\nLOG_FILES = ['missing.log']\nAFTER_REQUEST_WAIT_SECONDS = 'abc'\ndef build_request(params):\n    return {'method': 'GET', 'url': 'http://127.0.0.1:1'}\n"
    )

    result = run_bfk(tmp_path, "run")

    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    response = json.loads((issue / "iterations" / "001" / "response.json").read_text())
    assert response["transport_error"]["type"] == "runner_error"
    assert "AFTER_REQUEST_WAIT_SECONDS" in response["transport_error"]["message"]


def test_run_malformed_headers_writes_transport_error_iteration(tmp_path: Path):
    run_bfk(tmp_path, "init-project", "--base-url", "http://127.0.0.1:1", "--log-file", "missing.log")
    run_bfk(tmp_path, "new", "bad-headers", "account=1")
    issue = next((tmp_path / ".bfk" / "issues").iterdir())
    (issue / "runner.py").write_text(
        "PARAMS = {}\nLOG_FILES = ['missing.log']\nAFTER_REQUEST_WAIT_SECONDS = 0\ndef build_request(params):\n    return {'method': 'GET', 'url': 'http://127.0.0.1:1', 'headers': [('Bad',)]}\n"
    )

    result = run_bfk(tmp_path, "run")

    assert result.returncode == 0, result.stderr
    response = json.loads((issue / "iterations" / "001" / "response.json").read_text())
    assert response["transport_error"]["type"] == "transport_error"


def test_run_non_json_serializable_request_is_artifacted(tmp_path: Path):
    run_bfk(tmp_path, "init-project", "--base-url", "http://127.0.0.1:1", "--log-file", "missing.log")
    run_bfk(tmp_path, "new", "bad-json", "account=1")
    issue = next((tmp_path / ".bfk" / "issues").iterdir())
    (issue / "runner.py").write_text(
        "PARAMS = {}\nLOG_FILES = ['missing.log']\nAFTER_REQUEST_WAIT_SECONDS = 0\ndef build_request(params):\n    return {'method': 'POST', 'url': 'http://127.0.0.1:1', 'json': {'bad': {1, 2}}}\n"
    )

    result = run_bfk(tmp_path, "run")

    assert result.returncode == 0, result.stderr
    request = json.loads((issue / "iterations" / "001" / "request.json").read_text())
    response = json.loads((issue / "iterations" / "001" / "response.json").read_text())
    assert request["json"]["bad"] == "{1, 2}"
    assert response["transport_error"]["type"] == "transport_error"
