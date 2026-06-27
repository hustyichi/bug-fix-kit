from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ["bfk-init", "bfk-new", "bfk-run", "bfk-diagnose", "bfk-fix"]


def test_pyproject_has_release_ready_metadata_without_runtime_dependencies():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project = pyproject["project"]
    assert project["name"] == "bug-fix-kit"
    assert project.get("dependencies", []) == []
    assert project["scripts"] == {"bfk": "bug_fix_kit.cli:main"}
    assert project["optional-dependencies"]["release"] == [
        "build>=1.2",
        "setuptools>=68",
        "twine>=5",
        "wheel>=0.42",
    ]
    assert project["urls"]["Repository"] == "https://github.com/hustyichi/bug-fix-kit"

    package_data = pyproject["tool"]["setuptools"]["package-data"]["bug_fix_kit"]
    assert "plugin/.codex-plugin/*" in package_data
    assert "plugin/skills/*/SKILL.md" in package_data


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


def test_release_scripts_and_packaged_plugin_assets_exist():
    assert (ROOT / "scripts" / "check-release.py").exists()
    assert (ROOT / "scripts" / "publish-release.py").exists()
    assert (ROOT / "bug_fix_kit" / "plugin" / ".codex-plugin" / "plugin.json").exists()
    for skill in SKILLS:
        assert (ROOT / "bug_fix_kit" / "plugin" / "skills" / skill / "SKILL.md").exists()


def test_packaged_plugin_bundle_matches_repo_plugin_shell():
    assert (ROOT / "bug_fix_kit" / "plugin" / ".codex-plugin" / "plugin.json").read_text() == (
        ROOT / ".codex-plugin" / "plugin.json"
    ).read_text()
    for skill in SKILLS:
        assert (ROOT / "bug_fix_kit" / "plugin" / "skills" / skill / "SKILL.md").read_text() == (
            ROOT / "skills" / skill / "SKILL.md"
        ).read_text()


def test_release_scripts_have_safety_gates():
    check_release = (ROOT / "scripts" / "check-release.py").read_text()
    publish_release = (ROOT / "scripts" / "publish-release.py").read_text()
    assert "--no-isolation" in check_release
    assert "--no-isolation" in publish_release
    assert '"bug_fix_kit", "scripts", "tests"' in check_release
    assert "--require-unclaimed-name" in publish_release
    assert "args.publish and args.allow_dirty" in publish_release
    assert "--allow-dirty is dry-run only" in publish_release


def test_no_demo_app_or_unsupported_plugin_surfaces():
    forbidden = ["demo", "examples/demo"]
    for path in forbidden:
        assert not (ROOT / path).exists()
