from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from skillize.errors import InstallError
from skillize.install import install_skill
from skillize.sources import RemoteSkill

ENTRY = RemoteSkill(
    name="frontend-design",
    repo="anthropics/skills",
    skill_path="skills/frontend-design/SKILL.md",
    branch="main",
)


def test_install_writes_files_and_lock(tmp_path: Path) -> None:
    listing = [
        {
            "name": "SKILL.md",
            "path": "skills/frontend-design/SKILL.md",
            "type": "file",
            "download_url": "https://raw.example/SKILL.md",
        },
        {
            "name": "LICENSE.txt",
            "path": "skills/frontend-design/LICENSE.txt",
            "type": "file",
            "download_url": "https://raw.example/LICENSE.txt",
        },
    ]
    blobs = {
        "https://raw.example/SKILL.md": b"# frontend-design\n",
        "https://raw.example/LICENSE.txt": b"MIT\n",
    }

    dest = install_skill(
        tmp_path,
        ENTRY,
        get_json=lambda _url: listing,
        get_bytes=blobs.__getitem__,
    )

    assert dest == tmp_path / ".agents" / "skills" / "frontend-design"
    assert (dest / "SKILL.md").read_text(encoding="utf-8") == "# frontend-design\n"
    assert (dest / "LICENSE.txt").read_text(encoding="utf-8") == "MIT\n"
    lock = json.loads((tmp_path / "skills-lock.json").read_text(encoding="utf-8"))
    body = lock["skills"]["frontend-design"]
    assert body["source"] == "anthropics/skills"
    assert body["sourceType"] == "github"
    assert body["skillPath"] == "skills/frontend-design/SKILL.md"
    assert body["computedHash"] == hashlib.sha256(b"# frontend-design\n").hexdigest()


def test_install_rejects_path_escape(tmp_path: Path) -> None:
    listing = [
        {
            "name": "SKILL.md",
            "path": "skills/other/SKILL.md",
            "type": "file",
            "download_url": "https://raw.example/SKILL.md",
        }
    ]
    with pytest.raises(InstallError, match="escaped"):
        install_skill(
            tmp_path,
            ENTRY,
            get_json=lambda _url: listing,
            get_bytes=lambda _url: b"nope",
        )


def test_install_upserts_existing_lock_row(tmp_path: Path) -> None:
    (tmp_path / "skills-lock.json").write_text(
        json.dumps(
            {
                "version": 1,
                "skills": {
                    "keep-me": {"source": "addyosmani/agent-skills", "sourceType": "github"},
                    "frontend-design": {"source": "old/repo", "sourceType": "github"},
                },
            }
        ),
        encoding="utf-8",
    )
    listing = [
        {
            "name": "SKILL.md",
            "path": "skills/frontend-design/SKILL.md",
            "type": "file",
            "download_url": "https://raw.example/SKILL.md",
        }
    ]
    install_skill(
        tmp_path,
        ENTRY,
        get_json=lambda _url: listing,
        get_bytes=lambda _url: b"new\n",
    )
    lock = json.loads((tmp_path / "skills-lock.json").read_text(encoding="utf-8"))
    assert "keep-me" in lock["skills"]
    assert lock["skills"]["frontend-design"]["source"] == "anthropics/skills"
    assert lock["skills"]["frontend-design"]["computedHash"] == hashlib.sha256(b"new\n").hexdigest()


def test_install_bundled_php7(tmp_path: Path) -> None:
    from skillize.builtin import bundled_entries

    def boom(_url: str) -> object:
        raise AssertionError("bundled must not hit GitHub")

    php7 = next(entry for entry in bundled_entries() if entry.name == "php7")
    dest = install_skill(tmp_path, php7, get_json=boom, get_bytes=boom)
    skill_md = dest / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    assert dest == tmp_path / ".agents" / "skills" / "php7"
    assert "name: php7" in text
    assert "str_contains" in text
    lock = json.loads((tmp_path / "skills-lock.json").read_text(encoding="utf-8"))
    body = lock["skills"]["php7"]
    assert body["source"] == "pleware/skillize"
    assert body["sourceType"] == "bundled"
    assert body["skillPath"] == "bundled/php7/SKILL.md"
    assert body["computedHash"] == hashlib.sha256(skill_md.read_bytes()).hexdigest()
