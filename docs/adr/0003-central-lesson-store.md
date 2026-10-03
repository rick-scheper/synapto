# ADR-0003: Keep published lessons in one central store per user

- **Status:** Accepted
- **Date:** 2026-10-03

## Context

Lessons are generated across all the projects a developer works on. The hub should show them in one place, together with the learner's progress (quiz answers, exercise attempts, edited notebooks). Lessons also need to know which project and interpreter they belong to, so their code can run.

## Options considered

1. **Central store** at `~/.debrief/lessons/<id>/`, with a SQLite database for the index and progress. Each lesson records its repo path, commits and interpreter. One hub covers every project, and project repos stay clean. The cost is that lessons aren't versioned alongside the code.
2. **Per-repo store** (`.lessons/` inside each project). Lessons are versioned with the code and could be committed for collaborators. But the hub has to discover and watch many repos, and the project tree gets cluttered.

Agent recommendation at the time: Option 1, because debrief is single-user and the hub is meant as one personal library across projects.

## Decision

We chose a **central store in `~/.debrief`** (overridable with `DEBRIEF_HOME`).

**Rationale:** Developers work on multiple projects, and debrief should be a hub where they see all of them at once. That needs one small database holding the lessons and the paths to their projects. SQLite over Postgres: it ships with Python and is a single file, so there is no server to install or run and `pipx install debrief` stays the only install step. Postgres becomes worth it only if debrief goes multi-user or hosted.

## Consequences

- There's a single library view and a single progress database. Project repos are untouched.
- Lessons can go stale when the repo changes. File hashes in `lesson.json` let the hub show a staleness badge.
- If a repo moves on disk, its lessons' `environment.python` and `cwd` paths break. A future `debrief relink` command can fix that.
- Revisit if sharing lessons with a team becomes a goal. Then an export/import format or a per-repo option becomes useful.
- Reversibility: easy. Bundles are self-contained folders and can be copied anywhere.
