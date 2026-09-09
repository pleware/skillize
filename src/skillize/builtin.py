"""Skills shipped inside the skillize wheel. Not fetched from GitHub."""

from __future__ import annotations

from importlib.resources import files

from .sources import SKILL_NAME, RemoteSkill

BUNDLED_REPO = "pleware/skillize"
BUNDLED_PACKAGE = "skillize.bundled"


def is_bundled(entry: RemoteSkill) -> bool:
    return entry.repo == BUNDLED_REPO


def bundled_entries() -> tuple[RemoteSkill, ...]:
    root = files(BUNDLED_PACKAGE)
    found: list[RemoteSkill] = []
    for child in root.iterdir():
        name = child.name
        if not SKILL_NAME.fullmatch(name):
            continue
        if not child.is_dir() or not (child / "SKILL.md").is_file():
            continue
        found.append(
            RemoteSkill(
                name=name,
                repo=BUNDLED_REPO,
                skill_path=f"bundled/{name}/SKILL.md",
                branch="",
            )
        )
    return tuple(sorted(found, key=lambda entry: entry.name))
