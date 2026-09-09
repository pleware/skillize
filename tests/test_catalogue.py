from __future__ import annotations

from pathlib import Path

from skillize.catalogue import compose_skills, discover_names, skill_is_installed
from skillize.policy import Policy, Skill, load_policy, load_policy_or_empty, save_policy


def test_discover_skill_markdown(tmp_path: Path) -> None:
    skill = tmp_path / ".agents" / "skills" / "frontend-design"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# frontend-design\n", encoding="utf-8")
    (tmp_path / ".agents" / "skills" / "ignore-me").mkdir()
    assert discover_names(tmp_path) == ("frontend-design",)
    assert skill_is_installed(tmp_path, "frontend-design") is True
    assert skill_is_installed(tmp_path, "missing") is False


def test_compose_adds_discovered_off(tmp_path: Path) -> None:
    skill = tmp_path / ".agents" / "skills" / "frontend-design"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# frontend-design\n", encoding="utf-8")
    policy = Policy(
        path=tmp_path / "skillize.yaml",
        version=1,
        skills=(Skill(name="api-and-interface-design", enabled=True, when="contracts"),),
    )
    names = [item.name for item in compose_skills(tmp_path, policy)]
    assert names == ["api-and-interface-design", "frontend-design"]
    extra = compose_skills(tmp_path, policy)[1]
    assert extra.enabled is False


def test_save_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "skillize.yaml"
    original = Policy(
        path=path,
        version=1,
        skills=(
            Skill(name="api-and-interface-design", enabled=True, when="contracts"),
            Skill(name="frontend-design", enabled=False),
        ),
    )
    save_policy(original)
    loaded = load_policy(tmp_path)
    assert loaded.enabled_names() == ("api-and-interface-design",)
    assert loaded.skills[0].when == "contracts"
    assert "$schema" in path.read_text(encoding="utf-8")


def test_load_or_empty_missing(tmp_path: Path) -> None:
    policy = load_policy_or_empty(tmp_path)
    assert policy.skills == ()
    assert policy.path == tmp_path / "skillize.yaml"
