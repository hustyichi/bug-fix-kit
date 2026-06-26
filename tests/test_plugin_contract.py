from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ["bfk-init", "bfk-new", "bfk-run", "bfk-diagnose", "bfk-fix"]


def test_pyproject_has_no_runtime_dependencies_and_no_release_scripts():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert pyproject["project"].get("dependencies", []) == []
    assert pyproject["project"]["scripts"] == {"bfk": "bug_fix_kit.cli:main"}
    assert "release" not in pyproject.get("project", {}).get("optional-dependencies", {})


def test_plugin_manifest_contract_and_skill_dirs():
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
    assert manifest["name"] == "bug-fix-kit"
    assert re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"])
    assert manifest["skills"] == "./skills/"
    assert "hooks" not in manifest
    assert "apps" not in manifest
    assert "mcpServers" not in manifest

    interface = manifest["interface"]
    for field in ["displayName", "shortDescription", "longDescription", "developerName", "category", "capabilities"]:
        assert interface[field]
    prompts = interface.get("defaultPrompt") or interface.get("default_prompt")
    assert isinstance(prompts, list)
    assert 1 <= len(prompts) <= 3
    assert all(isinstance(prompt, str) and prompt.strip() for prompt in prompts)

    for skill in SKILLS:
        assert (ROOT / "skills" / skill / "SKILL.md").exists()


def test_no_demo_app_or_release_automation_files():
    forbidden = ["demo", "examples/demo", "scripts/publish-release.py", "scripts/check-release.py"]
    for path in forbidden:
        assert not (ROOT / path).exists()
