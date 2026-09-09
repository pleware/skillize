"""Load and validate `skillize.yaml` against schema v1."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .errors import PolicyError
from .store_tree import config_path

SUPPORTED_VERSION = 1
SCHEMA_RESOURCE = "v1.json"
SCHEMA_URL = "https://raw.githubusercontent.com/pleware/skillize/main/schema/v1.json"


@dataclass(frozen=True)
class Skill:
    name: str
    enabled: bool
    when: str | None = None


@dataclass(frozen=True)
class Policy:
    path: Path
    version: int
    skills: tuple[Skill, ...]
    sources: tuple[str, ...] = ()
    sources_declared: bool = False

    def enabled_names(self) -> tuple[str, ...]:
        return tuple(skill.name for skill in self.skills if skill.enabled)


MUTEX_GROUPS = (("php7", "php8"),)


def _upsert_skill(policy: Policy, skill: Skill) -> Policy:
    rows = {item.name: item for item in policy.skills}
    rows[skill.name] = skill
    ordered: list[Skill] = []
    seen: set[str] = set()
    for item in policy.skills:
        ordered.append(rows[item.name])
        seen.add(item.name)
    if skill.name not in seen:
        ordered.append(skill)
    return Policy(
        path=policy.path,
        version=policy.version,
        skills=tuple(ordered),
        sources=policy.sources,
        sources_declared=policy.sources_declared,
    )


def with_skill_enabled(policy: Policy, name: str, enabled: bool) -> Policy:
    """Return a copy with `name` on or off. php7 and php8 cannot both be on."""
    previous = next((item for item in policy.skills if item.name == name), None)
    updated = _upsert_skill(
        policy,
        Skill(name=name, enabled=enabled, when=previous.when if previous else None),
    )
    if not enabled:
        return updated
    for group in MUTEX_GROUPS:
        if name not in group:
            continue
        for other in group:
            if other == name:
                continue
            rival = next((item for item in updated.skills if item.name == other), None)
            if rival is not None:
                updated = _upsert_skill(
                    updated, Skill(name=other, enabled=False, when=rival.when)
                )
    return updated


def with_skill_when(policy: Policy, name: str, when: str | None) -> Policy:
    """Return a copy with project `when` prose for `name`."""
    previous = next((item for item in policy.skills if item.name == name), None)
    return _upsert_skill(
        policy,
        Skill(
            name=name,
            enabled=previous.enabled if previous else False,
            when=when,
        ),
    )


def schema_bytes() -> bytes:
    packaged = files("skillize") / "data" / SCHEMA_RESOURCE
    try:
        return packaged.read_bytes()
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        fallback = Path(__file__).resolve().parents[2] / "schema" / "v1.json"
        if fallback.is_file():
            return fallback.read_bytes()
        raise PolicyError("schema v1 is missing from the skillize install") from None


def schema_document() -> dict[str, Any]:
    return json.loads(schema_bytes().decode("utf-8"))


def load_policy(project_root: Path) -> Policy:
    path = config_path(project_root)
    if not path.is_file():
        raise PolicyError(f"no {path.name} at {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PolicyError(f"cannot read {path}: {exc}") from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise PolicyError(f"{path}: invalid YAML: {exc}") from exc
    if raw is None:
        raise PolicyError(f"{path}: file is empty")
    if not isinstance(raw, dict):
        raise PolicyError(f"{path}: root must be a mapping")
    version = raw.get("version")
    if isinstance(version, float):
        raise PolicyError(f"{path}: version must be integer {SUPPORTED_VERSION}, not {version!r}")
    try:
        Draft202012Validator(schema_document()).validate(raw)
    except ValidationError as exc:
        where = ".".join(str(part) for part in exc.absolute_path) or "root"
        raise PolicyError(f"{path}: {where}: {exc.message}") from exc
    skills = tuple(
        Skill(name=name, enabled=bool(body["enabled"]), when=_optional_when(body.get("when")))
        for name, body in (raw.get("skills") or {}).items()
    )
    sources_declared = "sources" in raw
    sources = tuple(str(item) for item in (raw.get("sources") or ()))
    return Policy(
        path=path,
        version=int(raw["version"]),
        skills=skills,
        sources=sources,
        sources_declared=sources_declared,
    )


def load_policy_or_empty(project_root: Path) -> Policy:
    path = config_path(project_root)
    if not path.is_file():
        return Policy(path=path, version=SUPPORTED_VERSION, skills=())
    return load_policy(project_root)


def policy_to_mapping(policy: Policy) -> dict[str, Any]:
    skills: dict[str, Any] = {}
    for skill in policy.skills:
        body: dict[str, Any] = {"enabled": skill.enabled}
        if skill.when:
            body["when"] = skill.when
        skills[skill.name] = body
    mapping: dict[str, Any] = {
        "$schema": SCHEMA_URL,
        "version": SUPPORTED_VERSION,
        "skills": skills,
    }
    if policy.sources_declared or policy.sources:
        mapping["sources"] = list(policy.sources)
    return mapping


def save_policy(policy: Policy) -> None:
    mapping = policy_to_mapping(policy)
    Draft202012Validator(schema_document()).validate(mapping)
    text = yaml.safe_dump(
        mapping,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    policy.path.write_text(text, encoding="utf-8", newline="\n")


def _optional_when(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
