from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ["bfk-init", "bfk-new", "bfk-run", "bfk-diagnose", "bfk-fix"]


def test_pyproject_has_hatch_release_ready_metadata_without_runtime_dependencies():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project = pyproject["project"]
    assert pyproject["build-system"]["build-backend"] == "hatchling.build"
    assert "hatchling>=1.26" in pyproject["build-system"]["requires"]
    assert project["name"] == "bug-fix-kit"
    assert project.get("dependencies", []) == []
    assert project["scripts"] == {"bfk": "bug_fix_kit.cli:main"}
    assert project["optional-dependencies"]["release"] == [
        "build>=1.2",
        "hatchling>=1.26",
        "twine>=5",
        "wheel>=0.42",
    ]
    assert project["urls"]["Repository"] == "https://github.com/hustyichi/bug-fix-kit"

    wheel = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel["packages"] == ["src/bug_fix_kit"]
    assert wheel["force-include"] == {
        ".codex-plugin": "bug_fix_kit/plugin_payload/bug-fix-kit/.codex-plugin",
        "skills": "bug_fix_kit/plugin_payload/bug-fix-kit/skills",
    }


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


def test_source_layout_has_single_maintained_plugin_shell():
    assert (ROOT / "src" / "bug_fix_kit" / "__init__.py").exists()
    assert (ROOT / "src" / "bug_fix_kit" / "__main__.py").exists()
    assert (ROOT / "src" / "bug_fix_kit" / "cli.py").exists()
    assert not (ROOT / "bug_fix_kit").exists()
    assert not (ROOT / "bug_fix_kit.egg-info").exists()
    assert not (ROOT / "src" / "bug_fix_kit" / "plugin").exists()


def test_release_scripts_have_full_hatch_payload_safety_gates():
    check_release = (ROOT / "scripts" / "check-release.py").read_text()
    publish_release = (ROOT / "scripts" / "publish-release.py").read_text()
    assert "--no-isolation" not in check_release
    assert "--no-isolation" not in publish_release
    assert '"src/bug_fix_kit", "scripts", "tests"' in check_release
    assert "plugin_payload/bug-fix-kit" in check_release
    for skill in SKILLS:
        assert skill in check_release
    assert "--require-unclaimed-name" in publish_release
    assert "args.publish and args.allow_dirty" in publish_release
    assert "--allow-dirty is dry-run only" in publish_release


def test_no_demo_app_or_unsupported_plugin_surfaces():
    forbidden = ["demo", "examples/demo"]
    for path in forbidden:
        assert not (ROOT / path).exists()
