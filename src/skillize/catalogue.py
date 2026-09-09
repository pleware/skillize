"""Skill names this tree can enable: lock dirs plus anything already in policy."""

from __future__ import annotations

from pathlib import Path

from .policy import Policy, Skill

SKILLS_DIR = Path(".agents") / "skills"
SKILL_FILE = "SKILL.md"


def discover_names(project_root: Path) -> tuple[str, ...]:
    base = project_root / SKILLS_DIR
    if not base.is_dir():
        return ()
    names: list[str] = []
    for child in sorted(base.iterdir()):
        if child.is_dir() and (child / SKILL_FILE).is_file():
            names.append(child.name)
    return tuple(names)


def compose_skills(
    project_root: Path,
    policy: Policy,
    extra_names: tuple[str, ...] = (),
) -> tuple[Skill, ...]:
    """Policy entries first, then local dirs and remote names not yet listed (off)."""
    by_name = {skill.name: skill for skill in policy.skills}
    ordered = [skill.name for skill in policy.skills]
    for name in (*discover_names(project_root), *extra_names):
        if name in by_name:
            continue
        ordered.append(name)
        by_name[name] = Skill(name=name, enabled=False)
    return tuple(by_name[name] for name in ordered)
