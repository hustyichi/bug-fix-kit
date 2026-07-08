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
    assert "fix-plan.md" in capture
    assert "fix_output.log" in capture
    assert "does not analyze root cause" in capture
    assert "does not modify" in capture or "does not edit" in capture
    assert "probe residue" in capture
    assert "$bfk-probe --revert" in capture

    locate = skill_text("bfk-locate").lower()
    assert "root-cause.md" in locate
    assert "direct chain" in locate
    assert "log-import" in locate
    assert "log" in locate
    assert "code" in locate
    assert "unknown" in locate
    assert "blocked" in locate
    assert "do not guess" in locate
    assert "expected result" in locate
    assert "correctness criteria" in locate
    assert "do not write `.bfk/root-cause.md`" in locate
    assert "does not modify" in locate or "does not edit" in locate
    assert "probe evidence" in locate
    assert "recommend `$bfk-probe`" in locate
    assert "$bfk-probe --revert" in locate
    assert "do not revert them yourself" in locate

    fix_plan = skill_text("bfk-fix-plan").lower()
    assert "root-cause.md" in fix_plan
    assert "fix-plan.md" in fix_plan
    assert "latest repair plan" in fix_plan
    assert "does not modify application code" in fix_plan
    assert "does not write `.bfk/fix.md`" in fix_plan
    assert "does not run `bfk fix-verify`" in fix_plan
    assert "does not maintain approval state" in fix_plan
    assert "revision history" in fix_plan

    fix = skill_text("bfk-fix").lower()
    assert "root-cause.md" in fix
    assert "fix-plan.md" in fix
    assert "primary repair instructions" in fix
    assert "does not silently ignore `.bfk/fix-plan.md`" in fix
    assert "confirmed root cause" in fix
    assert "fix.md" in fix
    assert "fix_output.log" in fix
    assert "changed_unverified" in fix
    assert "fixed_verified" in fix
    assert "unknown" in fix
    assert "blocked" in fix
    assert "does not guess" in fix
    assert "probe_session.residue_files" in fix
    assert "bfk-probe --revert" in fix

    probe = skill_text("bfk-probe").lower()
    assert "bfk-probe" in probe
    assert "probe-run" in probe
    assert "probe-revert" in probe
    assert "bfk-probe --revert" in probe
    assert "probe.json" in probe
    assert "output.log" in probe
    assert "sentinel" in probe
    assert "sentinel_seen" in probe
    assert "residue" in probe
    assert "at most 2 probe rounds" in probe
    assert "never logs secrets" in probe
    assert "does not analyze root cause" in probe
    assert "does not change any application logic" in probe
    assert "blocked" in probe


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
