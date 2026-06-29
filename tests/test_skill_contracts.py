from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from bug_fix_kit.contract import REQUIRED_SKILLS

SKILLS = list(REQUIRED_SKILLS)


def skill_text(name: str) -> str:
    return (ROOT / "skills" / name / "SKILL.md").read_text()


def test_all_bfk_skills_exist_with_front_matter():
    for name in SKILLS:
        path = ROOT / "skills" / name / "SKILL.md"
        assert path.exists(), name
        text = path.read_text()
        assert f"name: {name}" in text
        assert "description:" in text


def test_capture_locate_fix_boundaries_are_explicit():
    capture = skill_text("bfk-capture").lower()
    assert "one-stop capture" in capture
    assert "request context" in capture
    assert "active capture" in capture
    assert "archive" in capture
    assert "yyyy-mm-dd_hh-mm-ss" in capture
    assert "replays the existing" in capture
    assert "runner" in capture
    assert "request.json" in capture
    assert "response.json" in capture
    assert "output.log" in capture
    assert "fix_output.log" in capture
    assert "does not analyze root cause" in capture
    assert "does not modify" in capture or "does not edit" in capture

    locate = skill_text("bfk-locate").lower()
    assert "root-cause.md" in locate
    assert "direct chain" in locate
    assert "log" in locate
    assert "code" in locate
    assert "unknown" in locate
    assert "blocked" in locate
    assert "do not guess" in locate
    assert "does not modify" in locate or "does not edit" in locate

    fix = skill_text("bfk-fix").lower()
    assert "root-cause.md" in fix
    assert "confirmed root cause" in fix
    assert "fix.md" in fix
    assert "fix_output.log" in fix
    assert "changed_unverified" in fix
    assert "fixed_verified" in fix
    assert "unknown" in fix
    assert "blocked" in fix
    assert "does not guess" in fix


def test_bfk_skills_default_to_chinese_output_unless_user_specifies_language():
    for name in SKILLS:
        text = skill_text(name).lower()
        assert "default to chinese" in text
        assert "explicitly asks for another language" in text
        assert "quoted logs/errors" in text


def test_old_skill_directories_are_removed():
    assert not (ROOT / "skills" / ("bfk-" + "init")).exists()
    assert not (ROOT / "skills" / ("bfk-" + "new")).exists()
    assert not (ROOT / "skills" / ("bfk-" + "run")).exists()
    assert not (ROOT / "skills" / ("bfk-" + "diagnose")).exists()
