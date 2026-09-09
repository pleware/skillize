"""GitHub skill packs: list SKILL.md names without cloning the tree."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .errors import SkillizeError
from .policy import Policy
from .store_tree import catalogue_path, ensure_data_dir

LOCK_NAME = "skills-lock.json"
API = "https://api.github.com"
USER_AGENT = "pleware-skillize (https://github.com/pleware/skillize)"
SKILL_NAME = re.compile(r"^[a-z][a-z0-9._-]*$")
REPO_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
CACHE_VERSION = 2
LOCAL_REPO = "local"

JsonGet = Callable[[str], Any]
BytesGet = Callable[[str], bytes]
RepoFetch = Callable[[str], tuple["RemoteSkill", ...] | tuple[str, ...]]


class CatalogueError(SkillizeError):
    """A GitHub pack could not be listed. Configure still opens on cache or disk."""


@dataclass(frozen=True)
class RemoteSkill:
    name: str
    repo: str
    skill_path: str
    branch: str = "main"


def names_from_tree_paths(paths: Iterable[str]) -> tuple[str, ...]:
    return tuple(entry.name for entry in entries_from_tree_paths("owner/repo", paths))


def entries_from_tree_paths(
    repo: str,
    paths: Iterable[str],
    branch: str = "main",
) -> tuple[RemoteSkill, ...]:
    found: dict[str, RemoteSkill] = {}
    for raw in paths:
        path = raw.replace("\\", "/").strip("/")
        if Path(path).name != "SKILL.md":
            continue
        parent = Path(path).parent.name
        if parent and SKILL_NAME.fullmatch(parent) and parent not in found:
            found[parent] = RemoteSkill(
                name=parent,
                repo=repo,
                skill_path=path,
                branch=branch,
            )
    return tuple(sorted(found.values(), key=lambda entry: entry.name))


def names_of(entries: Iterable[RemoteSkill]) -> tuple[str, ...]:
    return tuple(sorted({entry.name for entry in entries}))


def skill_slug(entry: RemoteSkill) -> str:
    """Stable browse id: owner/repo/skill-name."""
    return f"{entry.repo}/{entry.name}"


def filter_entries(entries: Iterable[RemoteSkill], query: str) -> tuple[RemoteSkill, ...]:
    needle = query.strip().lower()
    ordered = tuple(entries)
    if not needle:
        return ordered
    return tuple(
        entry
        for entry in ordered
        if needle in skill_slug(entry).lower() or needle in entry.skill_path.lower()
    )


def split_catalogue(
    project_root: Path,
    entries: Iterable[RemoteSkill],
) -> tuple[tuple[RemoteSkill, ...], tuple[RemoteSkill, ...]]:
    """Installed on disk first, remaining GitHub pack rows second."""
    from .catalogue import discover_names, skill_is_installed

    ordered = tuple(sorted(entries, key=lambda entry: (entry.repo, entry.name)))
    installed_remote = tuple(
        entry for entry in ordered if skill_is_installed(project_root, entry.name)
    )
    available = tuple(
        entry for entry in ordered if not skill_is_installed(project_root, entry.name)
    )
    remote_names = {entry.name for entry in ordered}
    local_only = tuple(
        RemoteSkill(
            name=name,
            repo=LOCAL_REPO,
            skill_path=f".agents/skills/{name}/SKILL.md",
            branch="",
        )
        for name in discover_names(project_root)
        if name not in remote_names
    )
    installed = tuple(
        sorted((*installed_remote, *local_only), key=lambda entry: (entry.repo, entry.name))
    )
    return installed, available


def github_get_json(url: str) -> Any:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def github_get_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=20) as response:
        return response.read()


def fetch_repo_entries(
    repo: str, *, get_json: JsonGet = github_get_json
) -> tuple[RemoteSkill, ...]:
    if not REPO_NAME.fullmatch(repo):
        raise CatalogueError(f"not a GitHub owner/repo: {repo}")
    meta = get_json(f"{API}/repos/{repo}")
    branch = meta.get("default_branch") or "main"
    tree = get_json(f"{API}/repos/{repo}/git/trees/{branch}?recursive=1")
    blobs = [item["path"] for item in tree.get("tree", []) if item.get("type") == "blob"]
    entries = entries_from_tree_paths(repo, blobs, branch)
    if tree.get("truncated") and not entries:
        listing = get_json(f"{API}/repos/{repo}/contents/skills")
        if isinstance(listing, list):
            extra = [
                RemoteSkill(
                    name=item["name"],
                    repo=repo,
                    skill_path=f"skills/{item['name']}/SKILL.md",
                    branch=branch,
                )
                for item in listing
                if item.get("type") == "dir" and SKILL_NAME.fullmatch(item.get("name", ""))
            ]
            entries = tuple(sorted(extra, key=lambda entry: entry.name))
    return entries


def fetch_repo_skills(repo: str, *, get_json: JsonGet = github_get_json) -> tuple[str, ...]:
    return tuple(entry.name for entry in fetch_repo_entries(repo, get_json=get_json))


def sources_from_lock(project_root: Path) -> tuple[str, ...]:
    path = project_root / LOCK_NAME
    if not path.is_file():
        return ()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    skills = raw.get("skills")
    if not isinstance(skills, dict):
        return ()
    seen: list[str] = []
    for body in skills.values():
        if not isinstance(body, dict):
            continue
        if body.get("sourceType") not in (None, "github"):
            continue
        source = body.get("source")
        if isinstance(source, str) and REPO_NAME.fullmatch(source) and source not in seen:
            seen.append(source)
    return tuple(seen)


def sources_to_fetch(project_root: Path, policy: Policy) -> tuple[str, ...]:
    """Yaml `sources:` first, then any extra GitHub repos from the lock."""
    seen: list[str] = []
    for repo in (*policy.sources, *sources_from_lock(project_root)):
        if repo not in seen:
            seen.append(repo)
    return tuple(seen)


def _entry_from_cache(repo: str, item: Any) -> RemoteSkill | None:
    if isinstance(item, str):
        if SKILL_NAME.fullmatch(item):
            return RemoteSkill(name=item, repo=repo, skill_path=f"skills/{item}/SKILL.md")
        return None
    if not isinstance(item, dict):
        return None
    name = item.get("name")
    if not isinstance(name, str) or not SKILL_NAME.fullmatch(name):
        return None
    skill_path = item.get("skill_path")
    if not isinstance(skill_path, str) or not skill_path:
        skill_path = f"skills/{name}/SKILL.md"
    branch = item.get("branch")
    if not isinstance(branch, str) or not branch:
        branch = "main"
    return RemoteSkill(name=name, repo=repo, skill_path=skill_path, branch=branch)


def _read_cache(project_root: Path) -> dict[str, list[RemoteSkill]]:
    path = catalogue_path(project_root)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    repos = raw.get("repos")
    if not isinstance(repos, dict):
        return {}
    out: dict[str, list[RemoteSkill]] = {}
    for repo, items in repos.items():
        if not isinstance(repo, str) or not isinstance(items, list):
            continue
        entries = [entry for item in items if (entry := _entry_from_cache(repo, item)) is not None]
        if entries:
            out[repo] = entries
    return out


def _write_cache(project_root: Path, repos: dict[str, tuple[RemoteSkill, ...]]) -> None:
    ensure_data_dir(project_root)
    payload = {
        "version": CACHE_VERSION,
        "repos": {
            repo: [
                {"name": entry.name, "skill_path": entry.skill_path, "branch": entry.branch}
                for entry in entries
            ]
            for repo, entries in sorted(repos.items())
        },
    }
    catalogue_path(project_root).write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _offline() -> bool:
    return bool(os.environ.get("SKILLIZE_OFFLINE"))


def _coerce_entries(
    repo: str, payload: tuple[RemoteSkill, ...] | tuple[str, ...]
) -> tuple[RemoteSkill, ...]:
    if not payload:
        return ()
    first = payload[0]
    if isinstance(first, RemoteSkill):
        return payload
    return tuple(
        RemoteSkill(name=name, repo=repo, skill_path=f"skills/{name}/SKILL.md") for name in payload
    )


def _sorted_entries(groups: Iterable[Iterable[RemoteSkill]]) -> tuple[RemoteSkill, ...]:
    return tuple(
        sorted((entry for group in groups for entry in group), key=lambda e: (e.name, e.repo))
    )


def refresh_catalogue(
    project_root: Path,
    policy: Policy,
    *,
    fetch: RepoFetch = fetch_repo_entries,
) -> tuple[tuple[RemoteSkill, ...], str]:
    """Return remote skill rows and a one-line status for the user."""
    repos = sources_to_fetch(project_root, policy)
    if not repos:
        return (), "no GitHub sources in skillize.yaml or skills-lock.json"

    cached = _read_cache(project_root)
    if _offline():
        entries = _sorted_entries(cached.get(repo, []) for repo in repos)
        return entries, f"offline · {len(entries)} cached from {len(repos)} repo(s)"

    collected: dict[str, tuple[RemoteSkill, ...]] = {}
    errors: list[str] = []
    for repo in repos:
        try:
            collected[repo] = _coerce_entries(repo, fetch(repo))
        except (
            CatalogueError,
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
            KeyError,
            TypeError,
        ) as exc:
            errors.append(f"{repo}: {exc}")
            if repo in cached:
                collected[repo] = tuple(cached[repo])

    if collected:
        _write_cache(project_root, collected)
    entries = _sorted_entries(collected.values())
    if errors and entries:
        return entries, f"{len(entries)} skills · {len(errors)} repo error(s)"
    if errors:
        return (), f"GitHub list failed ({errors[0]})"
    return entries, f"{len(entries)} skills from {len(repos)} repo(s)"
