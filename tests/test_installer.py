from __future__ import annotations

import json
from pathlib import Path

import pytest

from bug_fix_kit.contract import REQUIRED_SKILLS
from bug_fix_kit.installer import InstallError, install_plugin


def make_plugin_source(root: Path) -> Path:
    (root / ".codex-plugin").mkdir(parents=True)
    (root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "bug-fix-kit", "version": "0.1.0", "skills": "./skills/"})
    )
    for skill in REQUIRED_SKILLS:
        skill_dir = root / "skills" / skill
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"---\nname: {skill}\n---\n")
    (root / "bug_fix_kit").mkdir()
    (root / "bug_fix_kit" / "__init__.py").write_text("__version__='0.1.0'\n")
    (root / ".git").mkdir()
    (root / ".git" / "ignored").write_text("x")
    (root / ".omx").mkdir()
    (root / ".omx" / "ignored").write_text("x")
    (root / ".bfk").mkdir()
    (root / ".bfk" / "ignored").write_text("x")
    (root / "keep.txt").write_text("keep")
    return root


def test_install_plugin_copies_only_payload_and_bootstraps_personal_marketplace(tmp_path: Path):
    source = make_plugin_source(tmp_path / "source")
    home = tmp_path / "home"

    result = install_plugin(source_root=source, home=home, yes=False)

    target = home / "plugins" / "bug-fix-kit"
    marketplace = home / ".agents" / "plugins" / "marketplace.json"
    assert result.plugin_dir == target
    assert result.marketplace_path == marketplace
    assert (target / ".codex-plugin" / "plugin.json").exists()
    assert (target / "skills" / "bfk-capture" / "SKILL.md").exists()
    assert (target / "skills" / "bfk-locate" / "SKILL.md").exists()
    assert (target / "skills" / "bfk-fix" / "SKILL.md").exists()
    assert not (target / "keep.txt").exists()
    assert not (target / "bug_fix_kit").exists()
    assert not (target / ".git").exists()
    assert not (target / ".omx").exists()
    assert not (target / ".bfk").exists()

    data = json.loads(marketplace.read_text())
    assert data["name"] == "personal"
    assert data["interface"]["displayName"] == "Personal"
    assert data["plugins"] == [
        {
            "name": "bug-fix-kit",
            "source": {"source": "local", "path": "./plugins/bug-fix-kit"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Coding",
        }
    ]
    assert "codex plugin add bug-fix-kit@personal" in result.next_steps


def test_install_plugin_refuses_existing_target_without_yes(tmp_path: Path):
    source = make_plugin_source(tmp_path / "source")
    home = tmp_path / "home"
    install_plugin(source_root=source, home=home, yes=False)

    with pytest.raises(InstallError, match="already exists"):
        install_plugin(source_root=source, home=home, yes=False)


def test_install_plugin_replaces_existing_target_with_yes(tmp_path: Path):
    source = make_plugin_source(tmp_path / "source")
    home = tmp_path / "home"
    install_plugin(source_root=source, home=home, yes=False)
    (home / "plugins" / "bug-fix-kit" / "stale.txt").write_text("stale")

    install_plugin(source_root=source, home=home, yes=True)

    assert not (home / "plugins" / "bug-fix-kit" / "stale.txt").exists()


def test_install_plugin_validates_manifest_and_skills(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()

    with pytest.raises(InstallError, match="plugin.json"):
        install_plugin(source_root=source, home=tmp_path / "home")

    (source / ".codex-plugin").mkdir()
    (source / ".codex-plugin" / "plugin.json").write_text(json.dumps({"name": "bug-fix-kit"}))

    with pytest.raises(InstallError, match="missing skill"):
        install_plugin(source_root=source, home=tmp_path / "home")


def test_install_plugin_excludes_caches_venv_and_build_outputs(tmp_path: Path):
    source = make_plugin_source(tmp_path / "source")
    for name in [".venv", ".pytest_cache", "build", "dist", "bug_fix_kit.egg-info"]:
        path = source / name
        path.mkdir()
        (path / "ignored").write_text("x")
    home = tmp_path / "home"

    install_plugin(source_root=source, home=home, yes=False)

    target = home / "plugins" / "bug-fix-kit"
    for name in [".venv", ".pytest_cache", "build", "dist", "bug_fix_kit.egg-info"]:
        assert not (target / name).exists()


def test_install_plugin_accepts_explicit_marketplace_path(tmp_path: Path):
    source = make_plugin_source(tmp_path / "source")
    home = tmp_path / "home"
    marketplace = home / ".agents" / "plugins" / "marketplace.json"

    result = install_plugin(source_root=source, marketplace_path=marketplace, yes=False)

    assert result.marketplace_path == marketplace
    assert result.plugin_dir == home / "plugins" / "bug-fix-kit"
    assert marketplace.exists()
