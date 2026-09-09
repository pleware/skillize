"""Copy a GitHub skill directory into `.agents/skills/<name>/`."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from urllib.error import HTTPError, URLError

from .catalogue import SKILL_FILE, skill_dir
from .errors import InstallError
from .sources import (
    API,
    LOCK_NAME,
    RemoteSkill,
    github_get_bytes,
    github_get_json,
)
from .store_tree import ensure_data_dir

MAX_FILES = 80
MAX_BYTES = 1_048_576
LOCK_VERSION = 1

JsonGet = Callable[[str], object]
BytesGet = Callable[[str], bytes]


def install_skill(
    project_root: Path,
    entry: RemoteSkill,
    *,
    get_json: JsonGet = github_get_json,
    get_bytes: BytesGet = github_get_bytes,
) -> Path:
    """Download `entry` into `.agents/skills/<name>/` and upsert `skills-lock.json`."""
    files = _list_skill_files(entry, get_json)
    if not files:
        raise InstallError(f"{entry.name}: GitHub listed no files")
    if not any(rel == SKILL_FILE for rel, _url in files):
        raise InstallError(f"{entry.name}: SKILL.md missing from {entry.repo}")

    staging_root = ensure_data_dir(project_root)
    staging = Path(tempfile.mkdtemp(prefix="install-", dir=staging_root))
    dest = skill_dir(project_root, entry.name)
    moved = False
    try:
        total = 0
        for rel, url in files:
            payload = _download(url, get_bytes)
            total += len(payload)
            if total > MAX_BYTES:
                raise InstallError(f"{entry.name}: skill exceeds {MAX_BYTES} bytes")
            target = staging / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        skill_md = staging / SKILL_FILE
        digest = hashlib.sha256(skill_md.read_bytes()).hexdigest()
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_dir():
            shutil.rmtree(dest)
        elif dest.exists():
            dest.unlink()
        shutil.move(str(staging), str(dest))
        moved = True
        _upsert_lock(project_root, entry, digest)
        return dest
    finally:
        if not moved and staging.is_dir():
            shutil.rmtree(staging)


def _download(url: str, get_bytes: BytesGet) -> bytes:
    try:
        return get_bytes(url)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise InstallError(f"download failed: {exc}") from exc


def _list_skill_files(entry: RemoteSkill, get_json: JsonGet) -> list[tuple[str, str]]:
    skill_root = entry.skill_path.replace("\\", "/").strip("/")
    if Path(skill_root).name == SKILL_FILE:
        skill_root = str(Path(skill_root).parent).replace("\\", "/")
    if not skill_root or skill_root in (".",):
        raise InstallError(f"{entry.name}: invalid skill path {entry.skill_path}")

    files: list[tuple[str, str]] = []

    def walk(api_path: str) -> None:
        url = f"{API}/repos/{entry.repo}/contents/{api_path}?ref={entry.branch}"
        try:
            listing = get_json(url)
        except (HTTPError, URLError, TimeoutError, OSError, KeyError, TypeError) as exc:
            raise InstallError(f"{entry.repo}: {exc}") from exc
        items = listing if isinstance(listing, list) else [listing]
        for item in items:
            if not isinstance(item, dict):
                continue
            item_path = str(item.get("path") or "")
            rel = _relative_under(skill_root, item_path)
            kind = item.get("type")
            if kind == "dir":
                walk(item_path)
            elif kind in ("file", "symlink"):
                download = item.get("download_url")
                if not isinstance(download, str) or not download:
                    raise InstallError(f"{entry.name}: no download URL for {item_path}")
                files.append((rel, download))
                if len(files) > MAX_FILES:
                    raise InstallError(f"{entry.name}: more than {MAX_FILES} files")

    walk(skill_root)
    return files


def _relative_under(root: str, path: str) -> str:
    root_n = root.replace("\\", "/").strip("/")
    path_n = path.replace("\\", "/").strip("/")
    prefix = root_n + "/"
    if path_n == root_n:
        raise InstallError(f"refusing to write the skill directory itself: {path}")
    if not path_n.startswith(prefix):
        raise InstallError(f"path escaped skill dir: {path}")
    rel = path_n[len(prefix) :]
    _assert_safe_rel(rel)
    return rel


def _assert_safe_rel(rel: str) -> None:
    if not rel or rel.startswith("/") or rel.startswith("\\"):
        raise InstallError(f"unsafe skill path: {rel}")
    path = Path(rel)
    if path.is_absolute() or path.drive:
        raise InstallError(f"unsafe skill path: {rel}")
    if any(part in ("..", "") for part in path.parts):
        raise InstallError(f"unsafe skill path: {rel}")


def _upsert_lock(project_root: Path, entry: RemoteSkill, digest: str) -> None:
    path = project_root / LOCK_NAME
    raw: dict = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        if isinstance(loaded, dict):
            raw = loaded
    skills = raw.get("skills")
    if not isinstance(skills, dict):
        skills = {}
    existing = skills.get(entry.name)
    if not isinstance(existing, dict):
        existing = {}
    existing["source"] = entry.repo
    existing["sourceType"] = "github"
    existing["skillPath"] = entry.skill_path
    existing["computedHash"] = digest
    skills[entry.name] = existing
    raw["version"] = raw.get("version", LOCK_VERSION)
    raw["skills"] = skills
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8", newline="\n")
