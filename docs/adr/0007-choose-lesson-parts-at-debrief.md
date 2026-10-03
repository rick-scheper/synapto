# ADR-0007: Let the developer choose a lesson's parts at `/debrief` time

- **Status:** Accepted
- **Date:** 2026-10-03

## Context

Every lesson had all five parts: Explain, Decisions, Notebook, Quiz and Rebuild. Developers don't always want all of them. Sometimes a quick explanation and a quiz are enough. Generating the notebook and the exercises is also the slowest and most expensive step for the agent, because both run in the project venv during validation.

## Options considered

1. **Choose at `/debrief` time.** The skill asks which parts to make, writes only those, and records them in `lesson.json` as `parts`. The validator, server and UI follow that list. Generation gets cheaper, but the bundle contract changes.
2. **Hide parts in the hub.** Bundles stay complete, and the learner hides tabs they don't want. The change is small, but generation costs the same.

## Decision

We chose **option 1**, as decided by the developer.

`lesson.json` gets an optional `parts` list holding any of `explain`, `decisions`, `notebook`, `quiz` and `rebuild`. It must not be empty and must not repeat a part. When `parts` is left out, the lesson has all five parts, so existing bundles stay valid and `schema_version` stays 1.

## Consequences

- Each part has its own file: `explanation.md`, `decisions.md`, `notebook.ipynb`, `quiz.json` and `exercises/`. The validator requires the file of every listed part. It also rejects the file of an unlisted part, so a forgotten `parts` entry is caught as well.
- Without a notebook or rebuild part, nothing runs, so the project interpreter isn't checked.
- The hub shows one tab per part and opens a lesson on its first part. Routes for a missing part return 404. Code references link to the notebook only when there is one.
- Progress counts only quiz questions and exercises that exist. A lesson with neither has nothing to complete: it shows no progress ring and is never "in progress" or "completed".
- Reversibility: easy. Leaving `parts` out means a full lesson again.
