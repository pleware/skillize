"""GitHub skill packs: list SKILL.md names without cloning the tree."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Iterable
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

JsonGet = Callable[[str], Any]


class CatalogueError(SkillizeError):
    """A GitHub pack could not be listed. Configure still opens on cache or disk."""


def names_from_tree_paths(paths: Iterable[str]) -> tuple[str, ...]:
    found: set[str] = set()
    for raw in paths:
        path = raw.replace("\\", "/").strip("/")
        if Path(path).name != "SKILL.md":
            continue
        parent = Path(path).parent.name
        if parent and SKILL_NAME.fullmatch(parent):
            found.add(parent)
    return tuple(sorted(found))


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


def fetch_repo_skills(repo: str, *, get_json: JsonGet = github_get_json) -> tuple[str, ...]:
    if not REPO_NAME.fullmatch(repo):
        raise CatalogueError(f"not a GitHub owner/repo: {repo}")
    meta = get_json(f"{API}/repos/{repo}")
    branch = meta.get("default_branch") or "main"
    tree = get_json(f"{API}/repos/{repo}/git/trees/{branch}?recursive=1")
    blobs = [item["path"] for item in tree.get("tree", []) if item.get("type") == "blob"]
    names = names_from_tree_paths(blobs)
    if tree.get("truncated") and not names:
        listing = get_json(f"{API}/repos/{repo}/contents/skills")
        if isinstance(listing, list):
            extra = [
                item["name"]
                for item in listing
                if item.get("type") == "dir" and SKILL_NAME.fullmatch(item.get("name", ""))
            ]
            names = tuple(sorted(set(extra)))
    return names


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
    if policy.sources_declared:
        return policy.sources
    return sources_from_lock(project_root)


def _read_cache(project_root: Path) -> dict[str, list[str]]:
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
    out: dict[str, list[str]] = {}
    for repo, names in repos.items():
        if isinstance(repo, str) and isinstance(names, list):
            out[repo] = [str(name) for name in names]
    return out


def _write_cache(project_root: Path, repos: dict[str, tuple[str, ...]]) -> None:
    ensure_data_dir(project_root)
    payload = {"repos": {repo: list(names) for repo, names in sorted(repos.items())}}
    catalogue_path(project_root).write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _offline() -> bool:
    return bool(os.environ.get("SKILLIZE_OFFLINE"))


def refresh_catalogue(
    project_root: Path,
    policy: Policy,
    *,
    fetch: Callable[[str], tuple[str, ...]] = fetch_repo_skills,
) -> tuple[tuple[str, ...], str]:
    """Return remote skill names and a one-line status for the user."""
    repos = sources_to_fetch(project_root, policy)
    if not repos:
        return (), "no GitHub sources in skillize.yaml or skills-lock.json"

    cached = _read_cache(project_root)
    if _offline():
        names = tuple(sorted({name for repo in repos for name in cached.get(repo, [])}))
        return names, f"offline · {len(names)} cached from {len(repos)} repo(s)"

    collected: dict[str, tuple[str, ...]] = {}
    errors: list[str] = []
    for repo in repos:
        try:
            collected[repo] = fetch(repo)
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
    names = tuple(sorted({name for group in collected.values() for name in group}))
    if errors and names:
        return names, f"{len(names)} skills · {len(errors)} repo error(s)"
    if errors:
        return (), f"GitHub list failed ({errors[0]})"
    return names, f"{len(names)} skills from {len(repos)} repo(s)"
