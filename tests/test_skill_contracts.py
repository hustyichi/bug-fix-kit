from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ["bfk-init", "bfk-new", "bfk-run", "bfk-diagnose", "bfk-fix"]


def skill_text(name: str) -> str:
    return (ROOT / "skills" / name / "SKILL.md").read_text()


def test_all_bfk_skills_exist_with_front_matter():
    for name in SKILLS:
        path = ROOT / "skills" / name / "SKILL.md"
        assert path.exists(), name
        text = path.read_text()
        assert f"name: {name}" in text
        assert "description:" in text


def test_run_diagnose_fix_boundaries_are_explicit():
    run = skill_text("bfk-run").lower()
    assert "does not diagnose" in run
    assert "does not modify" in run or "does not edit" in run
    assert "do not invoke `bfk run`" in run

    diagnose = skill_text("bfk-diagnose").lower()
    assert "does not modify" in diagnose or "does not edit" in diagnose
    assert "diagnosis.md" in diagnose
    assert "problem status: blocked" in diagnose
    assert "transport_error" in diagnose

    fix = skill_text("bfk-fix").lower()
    assert "does not run" in fix
    assert "fix.md" in fix
    assert "problem status" in fix
    assert "blocked" in fix


def test_init_and_new_boundaries_point_to_helpers():
    init = skill_text("bfk-init").lower()
    assert ".bfk/project.md" in init
    assert "do not invoke `bfk init-project`" in init
    assert "does not create issue" in init
    assert "does not run" in init

    new = skill_text("bfk-new").lower()
    assert "do not invoke `bfk new`" in new
    assert "runner.py" in new
    assert "does not run" in new
