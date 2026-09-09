from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from skillize.errors import PolicyError
from skillize.policy import load_policy, schema_document

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "skillize.yaml"


def test_schema_is_draft_2020_12() -> None:
    assert schema_document()["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_load_example() -> None:
    policy = load_policy(EXAMPLE.parent)
    assert policy.version == 1
    assert policy.enabled_names() == ("api-and-interface-design",)
    names = {skill.name: skill for skill in policy.skills}
    assert names["frontend-design"].enabled is False
    assert names["api-and-interface-design"].when is not None


def test_empty_skills_enables_nothing(tmp_path: Path) -> None:
    (tmp_path / "skillize.yaml").write_text("version: 1\nskills: {}\n", encoding="utf-8")
    policy = load_policy(tmp_path)
    assert policy.skills == ()
    assert policy.enabled_names() == ()


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="no skillize.yaml"):
        load_policy(tmp_path)


def test_version_float_rejected(tmp_path: Path) -> None:
    (tmp_path / "skillize.yaml").write_text("version: 1.0\nskills: {}\n", encoding="utf-8")
    with pytest.raises(PolicyError, match="integer"):
        load_policy(tmp_path)


def test_unknown_key_rejected(tmp_path: Path) -> None:
    payload = {"version": 1, "skills": {}, "lock": {}}
    (tmp_path / "skillize.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(PolicyError, match="lock"):
        load_policy(tmp_path)


def test_enabled_required(tmp_path: Path) -> None:
    payload = {"version": 1, "skills": {"frontend-design": {"when": "UI work"}}}
    (tmp_path / "skillize.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(PolicyError, match="enabled"):
        load_policy(tmp_path)
