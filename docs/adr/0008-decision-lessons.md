# ADR-0008: Decision lessons for code that isn't built yet

- **Status:** Accepted
- **Date:** 2026-10-03

## Context

Every lesson so far looks back: `/debrief` explains code the agent has already built. Developers also face choices *before* anything is built, such as which database, queue or framework to use. Usually they either accept the agent's first suggestion or pick something without understanding the trade-offs. Synapto can teach that choice the same way it teaches built code.

The developer starts from a question ("which database fits this project?"), optionally with candidates. The agent researches the best candidates and builds a lesson. There are two modes:

- **Guided:** the lesson leads the developer to the agent's recommendation.
- **Open:** the lesson gives the developer the information and lets them decide. The agent then tests their decision. No choice is wrong, but at the end the agent gives its own opinion.

The hub has no LLM: the agent writes a bundle once, and the hub only serves it. Open mode needs the agent to react *after* the developer has chosen, so it needs a way back to the agent.

## Options considered

**Entry point**

1. **A new skill, `/decide`**, with its own steps (question → candidates → research → write). It shares the bundle format, validator, store and hub with `/debrief`.
2. **A mode of `/debrief`** (`/debrief plan "<question>"`). One skill, but its inputs (a prompt vs a diff) and steps differ almost completely.

**How the agent tests an open decision**

1. **Round trip through Claude Code.** The developer records their choice and reasoning in the hub. `/decide review <id>` reads them through the CLI, challenges that reasoning in the terminal, and saves a verdict back through the CLI. The hub then shows the verdict.
2. **Pre-written challenges.** The bundle holds counter-arguments per candidate, and the hub reveals them after the choice. Everything stays in the browser, but the challenge doesn't react to what the developer actually wrote.
3. **The hub calls the Claude API.** A live debate in the browser. It needs an API key, a new dependency and an LLM inside the server.

**Runnable spikes** (a notebook that benchmarks the candidates): in v1, or not.

## Decision

As decided by the developer: **a new `/decide` skill**, the **round trip through Claude Code** for open mode, **no runnable parts** in decision lessons in v1, and at the end of a review the skill **offers to record the decision as an ADR in the project**.

- `lesson.json` gets `kind`: `debrief` (the default, so existing bundles stay valid and `schema_version` stays 1) or `decision`. A decision lesson also has `question` and `mode` (`guided` or `open`).
- A decision lesson has a new part, `options`, with its file `options.json`: the candidates, the criteria, a score per candidate per criterion, and the agent's recommendation. `options` is required for a decision lesson. `explain` and `quiz` are optional. `decisions`, `notebook` and `rebuild` aren't allowed, because there is no built code to look back on or run.
- The agent writes its recommendation into the bundle **before** the developer chooses, and in open mode the hub keeps it hidden until the review is done. The opinion the developer finally sees therefore can't have bent towards their choice.
- The developer's choice and the review's verdict are learner state, so they live in SQLite like quiz answers. The published bundle stays immutable (ADR-0003).

## Consequences

- New CLI commands for the round trip: `synapto decision show <id>` prints the question, the options, the developer's choice and the sealed recommendation as JSON for the agent. `synapto decision verdict <id> <file>` stores the review.
- New API routes: `GET /api/lessons/{id}/decision` (options, choice, review, and the recommendation once it may be shown) and `PUT /api/lessons/{id}/choice` (the choice can be changed until a verdict exists).
- `source` becomes optional for a decision lesson: there may be no repo yet. When it's given, `source.files` may be empty. `environment` is required only when the lesson has a runnable part. A lesson without source files is never stale.
- Progress: in open mode, a decision lesson is complete once the quiz is answered and a verdict exists. In guided mode only the quiz counts.
- The review costs the developer a step: going back to the terminal. The hub makes that step one click (it copies `/decide review <id>`).
- Reversibility: moderate. `kind` and the new part are additive, so removing the feature means deleting code, not migrating bundles.
