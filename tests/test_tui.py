from __future__ import annotations

from pathlib import Path

from textual.widgets import Input, OptionList

from skillize.catalogue import compose_skills
from skillize.policy import Policy, load_policy, load_policy_or_empty
from skillize.sources import RemoteSkill
from skillize.tui import ConfigureApp, SkillizeApp

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "skillize.yaml"


async def test_configure_toggles_and_saves(tmp_path: Path) -> None:
    (tmp_path / "skillize.yaml").write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    policy = load_policy_or_empty(tmp_path)
    skills = compose_skills(tmp_path, policy)
    app = ConfigureApp(tmp_path, policy, skills)
    async with app.run_test() as pilot:
        await pilot.press("space")
        await pilot.press("s")
        await pilot.pause()
    policy = load_policy(tmp_path)
    assert "api-and-interface-design" not in policy.enabled_names()
    assert "frontend-design" not in policy.enabled_names()


async def test_browse_filters_and_installs(tmp_path: Path) -> None:
    entries = (
        RemoteSkill(
            "planning-and-task-breakdown",
            "addyosmani/agent-skills",
            "skills/planning-and-task-breakdown/SKILL.md",
        ),
        RemoteSkill(
            "frontend-design",
            "anthropics/skills",
            "skills/frontend-design/SKILL.md",
        ),
    )
    installed: list[str] = []

    def fake_install(root: Path, entry: RemoteSkill, **_kwargs) -> Path:
        dest = root / ".agents" / "skills" / entry.name
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text("# ok\n", encoding="utf-8")
        installed.append(entry.name)
        return dest

    policy = Policy(path=tmp_path / "skillize.yaml", version=1, skills=())
    app = SkillizeApp(tmp_path, policy, entries, "2 skills", install=fake_install)
    async with app.run_test() as pilot:
        await pilot.pause()
        listing = app.query_one("#browse", OptionList)
        assert listing.option_count == 2
        search = app.query_one("#search", Input)
        search.value = "front"
        search.post_message(Input.Changed(search, search.value))
        await pilot.pause()
        assert [entry.name for entry in app._visible] == ["frontend-design"]
        await pilot.click("#browse")
        await pilot.press("i")
        await pilot.pause()
    assert installed == ["frontend-design"]
    assert (tmp_path / ".agents" / "skills" / "frontend-design" / "SKILL.md").is_file()
