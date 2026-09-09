"""One root for everything skillize raises, so callers can catch a single type."""

from __future__ import annotations


class SkillizeError(Exception):
    """Something in the project's setup is wrong. The message is for the user."""


class PolicyError(SkillizeError):
    """skillize.yaml is missing, unreadable, or does not match schema v1."""


class InstallError(SkillizeError):
    """A GitHub skill could not be copied onto disk."""
