# Changelog

## Unreleased

- Split configure into Installed then Install screens.
- List browse rows as `owner/repo/skill-name` and fetch both `sources:` and lock repos.
- Browse GitHub packs with search and install `SKILL.md` into `.agents/skills/` (`skillize configure`, `skillize install`).
- Refresh the configure catalogue from GitHub packs (`sources:` or `skills-lock.json`) at TUI start.
- Add a Textual checkbox TUI (`skillize configure`) to toggle skills and edit `when`.
- Add a Python 3.11+ package (`skillize check` validates schema v1).
- Publish `skillize.yaml` JSON Schema v1 (`schema/v1.json`).
- Plant the public kit face (README, LICENSE).
