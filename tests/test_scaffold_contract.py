from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_package_plugin_shell_contract():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert pyproject["project"]["name"] == "bug-fix-kit"
    assert pyproject["project"]["requires-python"] == ">=3.10"
    assert pyproject["project"].get("dependencies", []) == []
    assert pyproject["project"]["scripts"]["bfk"] == "bug_fix_kit.cli:main"

    init_text = (ROOT / "src" / "bug_fix_kit" / "__init__.py").read_text()
    assert "__version__" in init_text
    assert (ROOT / "src" / "bug_fix_kit" / "__main__.py").exists()
    assert (ROOT / "src" / "bug_fix_kit" / "cli.py").exists()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-m", "bug_fix_kit", "--help"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Bug Fix Kit" in result.stdout


def test_plugin_manifest_shell_contract():
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
    assert manifest["name"] == "bug-fix-kit"
    assert re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"])
    assert manifest["skills"] == "./skills/"
    assert "hooks" not in manifest
    assert "apps" not in manifest
    assert "mcpServers" not in manifest

    interface = manifest["interface"]
    assert interface["displayName"] == "Bug Fix Kit"
    assert interface["category"] == "Coding"
    assert interface["capabilities"] == ["Interactive", "Read", "Write"]
    assert 1 <= len(interface["defaultPrompt"]) <= 3
    assert all(prompt.strip() for prompt in interface["defaultPrompt"])


def test_readme_has_initial_install_section():
    readme = (ROOT / "README.md").read_text()
    readme_en = (ROOT / "README.en.md").read_text()
    assert "语言：简体中文 | [English](README.en.md)" in readme
    assert "Language: [简体中文](README.md) | English" in readme_en
    assert "## 安装" in readme
    assert "## Install" in readme_en
    assert "pip install bug-fix-kit" in readme
    assert "pip install bug-fix-kit" in readme_en
    assert "plugin_payload" in readme
    assert "plugin_payload" in readme_en
