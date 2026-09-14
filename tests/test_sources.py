from __future__ import annotations

import json
from pathlib import Path

from skillize.builtin import BUNDLED_REPO, bundled_entries, mutex_groups
from skillize.catalogue import compose_skills
from skillize.policy import Policy, Skill, load_policy, save_policy
from skillize.sources import (
    DEFAULT_SOURCES,
    LOCAL_REPO,
    RemoteSkill,
    entries_from_tree_paths,
    fetch_repo_skills,
    filter_entries,
    names_from_tree_paths,
    refresh_catalogue,
    sources_from_lock,
    sources_to_fetch,
    split_catalogue,
)


def test_default_sources_include_php_packs() -> None:
    assert DEFAULT_SOURCES[:3] == (
        "addyosmani/agent-skills",
        "vercel-labs/agent-skills",
        "obra/superpowers",
    )
    assert "AsyrafHussin/agent-skills" in DEFAULT_SOURCES
    assert "me-shaon/agent-skills" in DEFAULT_SOURCES


def test_bundled_catalogue_includes_php7() -> None:
    entries = bundled_entries()
    assert [entry.name for entry in entries] == ["php7"]
    assert entries[0].repo == BUNDLED_REPO
    assert entries[0].skill_path == "bundled/php7/SKILL.md"
    assert entries[0].conflicts == ("php8",)


def test_mutex_groups_derive_from_conflicts() -> None:
    assert mutex_groups(bundled_entries()) == (("php7", "php8"),)


def test_names_from_skill_markdown_paths() -> None:
    names = names_from_tree_paths(
        [
            "skills/api-and-interface-design/SKILL.md",
            "skills/frontend-design/LICENSE.txt",
            "plugin/skills/use-modern-go/SKILL.md",
            "README.md",
            "skills/Bad-Name/SKILL.md",
        ]
    )
    assert names == ("api-and-interface-design", "use-modern-go")


def test_entries_keep_repo_and_skill_path() -> None:
    entries = entries_from_tree_paths(
        "addyosmani/agent-skills",
        ["skills/code-review-and-quality/SKILL.md", "README.md"],
        branch="main",
    )
    assert entries == (
        RemoteSkill(
            name="code-review-and-quality",
            repo="addyosmani/agent-skills",
            skill_path="skills/code-review-and-quality/SKILL.md",
            branch="main",
        ),
    )


def test_filter_entries_matches_name_repo_and_path() -> None:
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
    assert filter_entries(entries, "FRONT") == (entries[1],)
    assert filter_entries(entries, "addyosmani") == (entries[0],)
    assert filter_entries(entries, "skills/frontend") == (entries[1],)
    assert filter_entries(entries, "anthropics/skills/frontend-design") == (entries[1],)
    assert filter_entries(entries, "") == entries


def test_sources_from_lock_are_unique_and_ordered(tmp_path: Path) -> None:
    (tmp_path / "skills-lock.json").write_text(
        json.dumps(
            {
                "version": 1,
                "skills": {
                    "frontend-design": {
                        "source": "anthropics/skills",
                        "sourceType": "github",
                    },
                    "api-and-interface-design": {
                        "source": "addyosmani/agent-skills",
                        "sourceType": "github",
                    },
                    "frontend-ui-engineering": {
                        "source": "addyosmani/agent-skills",
                        "sourceType": "github",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    assert sources_from_lock(tmp_path) == (
        "anthropics/skills",
        "addyosmani/agent-skills",
    )


def test_yaml_sources_union_lock(tmp_path: Path) -> None:
    (tmp_path / "skills-lock.json").write_text(
        json.dumps(
            {"skills": {"x": {"source": "anthropics/skills", "sourceType": "github"}}}
        ),
        encoding="utf-8",
    )
    policy = Policy(
        path=tmp_path / "skillize.yaml",
        version=1,
        skills=(),
        sources=("addyosmani/agent-skills",),
        sources_declared=True,
    )
    assert sources_to_fetch(tmp_path, policy) == (
        *DEFAULT_SOURCES,
        "anthropics/skills",
    )


def test_compose_includes_remote_names_off(tmp_path: Path) -> None:
    policy = Policy(
        path=tmp_path / "skillize.yaml",
        version=1,
        skills=(Skill(name="frontend-design", enabled=True),),
    )
    composed = compose_skills(
        tmp_path, policy, extra_names=("planning-and-task-breakdown",)
    )
    assert [item.name for item in composed] == [
        "frontend-design",
        "planning-and-task-breakdown",
    ]
    assert composed[1].enabled is False


def test_refresh_uses_injected_fetch_and_writes_cache(tmp_path: Path) -> None:
    policy = Policy(
        path=tmp_path / "skillize.yaml",
        version=1,
        skills=(),
        sources=("addyosmani/agent-skills",),
        sources_declared=True,
    )

    fetched: list[str] = []

    def fake_fetch(repo: str) -> tuple[str, ...]:
        fetched.append(repo)
        if repo == "addyosmani/agent-skills":
            return ("incremental-implementation", "planning-and-task-breakdown")
        return ()

    names, note = refresh_catalogue(tmp_path, policy, fetch=fake_fetch)
    assert {entry.name for entry in names} == {
        "incremental-implementation",
        "php7",
        "planning-and-task-breakdown",
    }
    assert fetched[: len(DEFAULT_SOURCES)] == list(DEFAULT_SOURCES)
    assert "bundled" in note
    cache = json.loads((tmp_path / ".skillize" / "catalogue.json").read_text(encoding="utf-8"))
    assert cache["version"] == 2
    assert cache["repos"]["addyosmani/agent-skills"] == [
        {
            "name": "incremental-implementation",
            "skill_path": "skills/incremental-implementation/SKILL.md",
            "branch": "main",
        },
        {
            "name": "planning-and-task-breakdown",
            "skill_path": "skills/planning-and-task-breakdown/SKILL.md",
            "branch": "main",
        },
    ]


def test_refresh_offline_reads_cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SKILLIZE_OFFLINE", "1")
    (tmp_path / ".skillize").mkdir()
    (tmp_path / ".skillize" / "catalogue.json").write_text(
        json.dumps({"repos": {"addyosmani/agent-skills": ["git-workflow-and-versioning"]}}),
        encoding="utf-8",
    )
    policy = Policy(
        path=tmp_path / "skillize.yaml",
        version=1,
        skills=(),
        sources=("addyosmani/agent-skills",),
        sources_declared=True,
    )

    def boom(_repo: str) -> tuple[str, ...]:
        raise AssertionError("must not hit the network offline")

    names, note = refresh_catalogue(tmp_path, policy, fetch=boom)
    assert {entry.name for entry in names} == {"git-workflow-and-versioning", "php7"}
    assert "offline" in note


def test_fetch_repo_skills_reads_the_git_tree() -> None:
    calls: list[str] = []

    def get_json(url: str) -> dict:
        calls.append(url)
        if url.endswith("/repos/addyosmani/agent-skills"):
            return {"default_branch": "main"}
        return {
            "truncated": False,
            "tree": [
                {"path": "skills/code-review-and-quality/SKILL.md", "type": "blob"},
                {"path": "README.md", "type": "blob"},
            ],
        }

    names = fetch_repo_skills("addyosmani/agent-skills", get_json=get_json)
    assert names == ("code-review-and-quality",)
    assert len(calls) == 2


def test_policy_sources_roundtrip(tmp_path: Path) -> None:
    original = Policy(
        path=tmp_path / "skillize.yaml",
        version=1,
        skills=(),
        sources=("addyosmani/agent-skills",),
        sources_declared=True,
    )
    save_policy(original)
    loaded = load_policy(tmp_path)
    assert loaded.sources == ("addyosmani/agent-skills",)
    assert loaded.sources_declared is True


def test_split_catalogue_installed_versus_available(tmp_path: Path) -> None:
    skill = tmp_path / ".agents" / "skills" / "frontend-design"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# frontend-design\n", encoding="utf-8")
    vendored = tmp_path / ".agents" / "skills" / "house-only"
    vendored.mkdir(parents=True)
    (vendored / "SKILL.md").write_text("# house\n", encoding="utf-8")
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
    installed, available = split_catalogue(tmp_path, entries)
    assert [entry.name for entry in installed] == ["frontend-design", "house-only"]
    assert installed[1].repo == LOCAL_REPO
    assert [entry.name for entry in available] == ["planning-and-task-breakdown"]
