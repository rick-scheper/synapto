# ADR-0006: Name the project Synapto and publish it on PyPI as `synapto-hub`

- **Status:** Accepted
- **Date:** 2026-10-03

## Context

Until M5 the project went by the working name `debrief`, while the repo (`rick-scheper/synapto`), the logo and the brand book already said **Synapto**. A release fixes the name in places that are hard to change later: the PyPI distribution, the CLI command, the import package, the Claude Code plugin and the store directory (`~/.<name>`). Both `debrief` and `synapto` are already taken on PyPI. `synapto` (v0.9.0) is a memory graph for AI coding agents, so it is in the same space as this project.

## Options considered

1. **Synapto everywhere, with a different PyPI distribution name** (`synapto-hub`): the product, CLI, import package, plugin and store are all `synapto`. Only `pipx install synapto-hub` differs. This matches the repo and the brand. The cost is possible confusion with the unrelated `synapto` package, which also targets coding agents.
2. **Keep `debrief`, with a different distribution name** (`debrief-hub`): the least churn, but it contradicts the logo, brand book and repo name.
3. **A new name that is free everywhere**: no clashes, but the design assets would need a rebrand.

Agent recommendation at the time: Option 1. The brand already exists, and the clash only affects `pipx install`.

## Decision

We chose **Synapto**, with the **PyPI distribution `synapto-hub`**.

**Rationale:** the user chose the recommended option without adding a rationale of their own.

## Consequences

- `pipx install synapto-hub` installs the `synapto` command and the `synapto` import package. Installing both this and the PyPI package `synapto` in one environment would clash on the import name. pipx gives each tool its own venv, so the recommended install avoids that.
- The store is `~/.synapto` (`SYNAPTO_HOME`), the notebook metadata key is `synapto` (ADR-0002), and the preamble defines `SYNAPTO_DATA` and `SYNAPTO_LESSON_DIR`. Earlier ADRs and the spec were updated to the new names.
- The Claude Code plugin is `synapto`. Its skill keeps the name `debrief`, because the skill names an action: you run `/debrief` after a build.
- Lessons published under the working name (`~/.debrief`, `metadata.debrief`) are not migrated. There were no releases before this one.
- Reversibility: low after the first PyPI release. Renaming then means a new distribution and a migration of the store.
