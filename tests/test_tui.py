from __future__ import annotations

from pathlib import Path

from skillize.catalogue import compose_skills
from skillize.policy import load_policy, load_policy_or_empty
from skillize.tui import ConfigureApp

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
