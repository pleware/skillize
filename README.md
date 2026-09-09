# skillize

[![CI](https://github.com/pleware/skillize/actions/workflows/ci.yml/badge.svg)](https://github.com/pleware/skillize/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square)](LICENSE)

Skill policy kit. It records which agent skills are enabled in a tree and
**when** they should fire. It does not plant host files
([agentize](https://github.com/pleware/agentize) mounts) and it does not
install a toolchain ([ignite](https://github.com/pleware/ignite)).

Python 3.11+ on Windows, macOS, and Linux — the same runtime as agentize.

Status: first version — schema v1, `skillize check`, a Textual TUI
(`skillize configure`: Installed or Install New, then enable), trampoline
launchers (`skillize init`), and `skillize install <name>`.

## Consumer layout

Same shape as ignite and agentize: a committed file at the workspace root,
plus a local directory for machine state.

```text
<workspace>/
  skillize.yaml    # policy — commit this
  skillize         # trampoline (also skillize.ps1 / skillize.cmd)
  .skillize/       # machine state — gitignore this
```

Schema: [`schema/v1.json`](schema/v1.json)
([JSON Schema 2020-12](https://json-schema.org/draft/2020-12/schema)).
Example: [`examples/skillize.yaml`](examples/skillize.yaml).

```yaml
$schema: https://raw.githubusercontent.com/pleware/skillize/main/schema/v1.json
version: 1
skills:
  api-and-interface-design:
    enabled: true
    when: >
      Designing or changing a public HTTP or module contract.
```

The kit name is **skillize** (two L's). Empty `skills:` means nothing is
enabled, not everything. Pin hashes stay in `skills-lock.json` — v1 does
not duplicate the lock.

## Launchers

A consumer commits three trampolines next to `skillize.yaml`. They call
`uvx --refresh --from git+https://github.com/pleware/skillize.git`, so a
week-old clone still starts today's kit. In this repository they call
`uv run` instead.

```sh
uv run skillize init
./skillize check
# Windows: .\skillize.ps1 check   or   .\skillize.cmd check
```

`SKILLIZE_OFFLINE=1` skips the GitHub refresh and uses the uv cache.

Deny-by-default `.gitignore` must whitelist them:

```gitignore
!/skillize.yaml
!/skillize
!/skillize.ps1
!/skillize.cmd
```

## Check

From a tree that has `skillize.yaml`:

```sh
uvx --from git+https://github.com/pleware/skillize.git skillize check
# or, in this checkout:
uv run skillize check
```

Windows: the same commands in PowerShell. Pass `-C` / `--directory` for a
path other than the current working directory.

## Configure

Interactive UI ([Textual](https://textual.textualize.io), MIT). The first
screen is a menu: **Installed** (skills already in `.agents/skills/`) and
**Install New** (remaining `SKILL.md` files from the built-in GitHub
packs — addyosmani, vercel-labs, obra/superpowers, AsyrafHussin, me-shaon
— plus `sources:` and extra repos in `skills-lock.json`). Rows are
`owner/repo/skill-name` (type to filter). `i` / Enter copies the
highlighted skill onto disk and upserts `skills-lock.json`. `c` opens the
enable/when checkboxes. Space toggles a skill, `e` edits `when`, `s`
writes `skillize.yaml`, `b` / Escape returns to the menu, `q` quits.

`SKILLIZE_OFFLINE=1` uses `.skillize/catalogue.json`. The kit does not
write `.cursor/`. Host mount remains agentize.

```yaml
sources:
  - addyosmani/agent-skills
  - vercel-labs/agent-skills
```

```sh
uv run skillize configure
# or just:
uv run skillize
# list packs without the TUI:
uv run skillize refresh
# copy one skill without the TUI:
uv run skillize install planning-and-task-breakdown
```

Needs a real terminal. CI and pipes should call `skillize check`.

## What this kit is not

- Not a skill format ([agentskills.io](https://agentskills.io)).
- Not a skill marketplace (`npx skills`, skills.sh).
- Not a host mounter (that is agentize).

## License

MIT. Copyright (c) 2026 pware | pware.ai
