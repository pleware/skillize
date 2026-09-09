from __future__ import annotations

import threading
from pathlib import Path

from textual.widgets import Input, OptionList, Static

from skillize.catalogue import compose_skills
from skillize.policy import Policy, Skill, load_policy, load_policy_or_empty, save_policy
from skillize.sources import RemoteSkill
from skillize.tui import ConfigureApp, InstalledScreen, InstallScreen, SkillizeApp

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "skillize.yaml"


async def _wait_until(pilot, predicate, *, frames: int = 80) -> None:
    for _ in range(frames):
        await pilot.pause()
        if predicate():
            return
    raise AssertionError("timed out waiting for the TUI")


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


async def test_home_menu_opens_installed_and_install_new(tmp_path: Path) -> None:
    already = tmp_path / ".agents" / "skills" / "frontend-design"
    already.mkdir(parents=True)
    (already / "SKILL.md").write_text("# on disk\n", encoding="utf-8")
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
        menu = app.query_one("#menu", OptionList)
        assert menu.option_count == 2
        assert "Installed" in str(menu.get_option_at_index(0).prompt)
        assert "Install New" in str(menu.get_option_at_index(1).prompt)
        await pilot.click("#menu")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, InstalledScreen)
        listing = app.screen.query_one("#browse", OptionList)
        assert listing.option_count == 1
        assert "anthropics/skills/frontend-design" in str(listing.get_option_at_index(0).prompt)
        await pilot.press("escape")
        await pilot.pause()
        await pilot.click("#menu")
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, InstallScreen)
        add_list = app.screen.query_one("#browse", OptionList)
        assert add_list.option_count == 1
        assert "addyosmani/agent-skills/planning-and-task-breakdown" in str(
            add_list.get_option_at_index(0).prompt
        )
        await pilot.click("#browse")
        await pilot.press("i")
        await _wait_until(pilot, lambda: installed == ["planning-and-task-breakdown"])
    assert (tmp_path / ".agents" / "skills" / "planning-and-task-breakdown" / "SKILL.md").is_file()


async def test_installed_toggle_enables_highlighted_skill(tmp_path: Path) -> None:
    already = tmp_path / ".agents" / "skills" / "php7"
    already.mkdir(parents=True)
    (already / "SKILL.md").write_text("# php7\n", encoding="utf-8")
    entries = (
        RemoteSkill("php7", "pleware/skillize", "bundled/php7/SKILL.md"),
    )
    policy = Policy(path=tmp_path / "skillize.yaml", version=1, skills=())
    app = SkillizeApp(tmp_path, policy, entries, "1 skill")
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#menu")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, InstalledScreen)
        listing = app.screen.query_one("#browse", OptionList)
        assert listing.has_focus
        assert str(listing.get_option_at_index(0).prompt).startswith("off")
        await pilot.press("c")
        await _wait_until(
            pilot,
            lambda: "php7" in load_policy(tmp_path).enabled_names(),
        )
        assert isinstance(app.screen, InstalledScreen)
        assert str(listing.get_option_at_index(0).prompt).startswith("on")
        await pilot.press("space")
        await _wait_until(pilot, lambda: load_policy(tmp_path).enabled_names() == ())
        assert str(listing.get_option_at_index(0).prompt).startswith("off")


async def test_installed_u_uninstalls_highlighted_skill(tmp_path: Path) -> None:
    already = tmp_path / ".agents" / "skills" / "php7"
    already.mkdir(parents=True)
    (already / "SKILL.md").write_text("# php7\n", encoding="utf-8")
    (tmp_path / "skills-lock.json").write_text(
        '{"version": 1, "skills": {"php7": {"source": "pleware/skillize",'
        ' "sourceType": "bundled"}}}\n',
        encoding="utf-8",
    )
    entries = (
        RemoteSkill("php7", "pleware/skillize", "bundled/php7/SKILL.md"),
        RemoteSkill(
            "php-best-practices",
            "AsyrafHussin/agent-skills",
            "skills/php-best-practices/SKILL.md",
        ),
    )
    save_policy(
        Policy(
            path=tmp_path / "skillize.yaml",
            version=1,
            skills=(Skill(name="php7", enabled=True),),
        )
    )
    policy = load_policy(tmp_path)
    app = SkillizeApp(tmp_path, policy, entries, "2 skills")
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#menu")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, InstalledScreen)
        listing = app.screen.query_one("#browse", OptionList)
        assert listing.option_count == 1
        await pilot.press("u")
        await _wait_until(pilot, lambda: not already.exists())
        assert listing.option_count == 0
        assert "php7" not in load_policy(tmp_path).enabled_names()
        assert all(skill.name != "php7" for skill in load_policy(tmp_path).skills)
        lock = (tmp_path / "skills-lock.json").read_text(encoding="utf-8")
        assert "php7" not in lock
        await pilot.press("escape")
        await pilot.pause()
        menu = app.query_one("#menu", OptionList)
        assert str(menu.get_option_at_index(0).prompt) == "Installed (0)"
        assert str(menu.get_option_at_index(1).prompt) == "Install New (2)"


async def test_home_menu_counts_refresh_after_install(tmp_path: Path) -> None:
    entries = (
        RemoteSkill(
            "planning-and-task-breakdown",
            "addyosmani/agent-skills",
            "skills/planning-and-task-breakdown/SKILL.md",
        ),
    )

    def fake_install(root: Path, entry: RemoteSkill, **_kwargs) -> Path:
        dest = root / ".agents" / "skills" / entry.name
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text("# ok\n", encoding="utf-8")
        return dest

    policy = Policy(path=tmp_path / "skillize.yaml", version=1, skills=())
    app = SkillizeApp(tmp_path, policy, entries, "1 skill", install=fake_install)
    async with app.run_test() as pilot:
        await pilot.pause()
        menu = app.query_one("#menu", OptionList)
        assert str(menu.get_option_at_index(0).prompt) == "Installed (0)"
        assert str(menu.get_option_at_index(1).prompt) == "Install New (1)"
        await pilot.click("#menu")
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, InstallScreen)
        await pilot.click("#browse")
        await pilot.press("i")
        dest = tmp_path / ".agents" / "skills" / "planning-and-task-breakdown" / "SKILL.md"
        await _wait_until(pilot, dest.is_file)
        await pilot.press("escape")
        await pilot.pause()
        menu = app.query_one("#menu", OptionList)
        assert str(menu.get_option_at_index(0).prompt) == "Installed (1)"
        assert str(menu.get_option_at_index(1).prompt) == "Install New (0)"


async def test_install_search_filters_the_list(tmp_path: Path) -> None:
    entries = (
        RemoteSkill(
            "php-best-practices",
            "AsyrafHussin/agent-skills",
            "skills/php-best-practices/SKILL.md",
        ),
        RemoteSkill(
            "laravel-queues",
            "AsyrafHussin/agent-skills",
            "skills/laravel-queues/SKILL.md",
        ),
        RemoteSkill(
            "php7",
            "pleware/skillize",
            "bundled/php7/SKILL.md",
        ),
    )
    policy = Policy(path=tmp_path / "skillize.yaml", version=1, skills=())
    screen = InstallScreen(tmp_path, policy, entries, "3 skills")
    app = SkillizeApp(tmp_path, policy, entries, "3 skills")
    async with app.run_test() as pilot:
        await app.push_screen(screen)
        await pilot.pause()
        listing = screen.query_one("#browse", OptionList)
        assert listing.option_count == 3
        assert listing.has_focus
        await pilot.press("slash")
        await pilot.pause()
        assert screen.query_one("#search", Input).has_focus
        await pilot.press("p", "h", "p")
        await pilot.pause()
        assert screen.query_one("#search", Input).value == "php"
        prompts = [
            str(listing.get_option_at_index(index).prompt)
            for index in range(listing.option_count)
        ]
    assert prompts == [
        "AsyrafHussin/agent-skills/php-best-practices",
        "pleware/skillize/php7",
    ]


def _hint_text(screen: InstallScreen) -> str:
    return str(screen.query_one("#hint", Static).content)


async def test_install_shows_progress_while_downloading(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()
    entries = (
        RemoteSkill(
            "planning-and-task-breakdown",
            "addyosmani/agent-skills",
            "skills/planning-and-task-breakdown/SKILL.md",
        ),
    )

    def fake_install(root: Path, entry: RemoteSkill, **_kwargs) -> Path:
        started.set()
        assert release.wait(timeout=5)
        dest = root / ".agents" / "skills" / entry.name
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text("# ok\n", encoding="utf-8")
        return dest

    policy = Policy(path=tmp_path / "skillize.yaml", version=1, skills=())
    app = SkillizeApp(tmp_path, policy, entries, "1 skill", install=fake_install)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#menu")
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, InstallScreen)
        screen = app.screen
        await pilot.click("#browse")
        await pilot.press("i")
        await _wait_until(
            pilot,
            lambda: started.is_set() and "Installing" in _hint_text(screen),
        )
        assert screen.query_one("#browse", OptionList).disabled is True
        release.set()
        dest = tmp_path / ".agents" / "skills" / "planning-and-task-breakdown" / "SKILL.md"
        await _wait_until(pilot, lambda: dest.is_file() and not screen._busy)
        assert screen.query_one("#browse", OptionList).option_count == 0
        assert screen.query_one("#browse", OptionList).disabled is False
