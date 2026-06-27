from __future__ import annotations

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


def test_cli_exposes_only_plugin_management_commands(tmp_path: Path):
    help_result = run_bfk(tmp_path, "--help")

    assert help_result.returncode == 0
    assert "install" in help_result.stdout
    assert "doctor" in help_result.stdout
    for command in ["init-project", "new", "run", "diagnose", "fix", "status", "verify", "auto"]:
        assert command not in help_result.stdout


def test_removed_core_workflow_commands_are_not_available(tmp_path: Path):
    for args in [
        ("init-project", "--base-url", "http://localhost:8000"),
        ("new", "login_failed", "account=13900000000"),
        ("run", "--timeout", "3"),
    ]:
        result = run_bfk(tmp_path, *args)
        assert result.returncode != 0
        assert "invalid choice" in result.stderr
        assert "Traceback" not in result.stderr


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
    target = tmp_path / "home" / "plugins" / "bug-fix-kit"
    assert (target / ".codex-plugin" / "plugin.json").exists()
    assert not (target / "pyproject.toml").exists()
    assert not (target / "bug_fix_kit").exists()
