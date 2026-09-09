# skillize

[![License](https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square)](LICENSE)

Skill policy kit. It records which agent skills are enabled in a tree and
**when** they should fire. It does not plant host files
([agentize](https://github.com/pleware/agentize) mounts) and it does not
install a toolchain ([ignite](https://github.com/pleware/ignite)).

Status: the public repository exists. Schema and CLI are not shipped yet.

## Consumer layout

Same shape as ignite and agentize: a committed file at the workspace root,
plus a local directory for machine state.

```text
<workspace>/
  skillize.yaml    # policy — commit this
  .skillize/       # machine state — gitignore this
```

The kit name is **skillize** (two L's). Empty `skills:` means nothing is
enabled, not everything.

## What this kit is not

- Not a skill format ([agentskills.io](https://agentskills.io)).
- Not a skill marketplace (`npx skills`, skills.sh).
- Not a host mounter (that is agentize).

## License

MIT. Copyright (c) 2026 pware | pware.ai
