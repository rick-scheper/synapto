---
name: debrief
description: Turn what was just built into an interactive lesson and publish it to the local Synapto hub.
argument-hint: "[only <part>,...] [since <commit> | <path>...]"
disable-model-invocation: true
---

# /debrief

Write a **lesson** about the code built in this session, so the developer — the **learner** — understands it instead of just accepting it. The lesson is a **bundle**: a folder of files that `synapto validate` checks and `synapto publish` copies into the developer's local hub.

Arguments: `$ARGUMENTS`

Before step 1, run `synapto --help`. If the command is missing, tell the developer to install it (`pipx install synapto-hub`) and stop.

## 1. Scope

The arguments may start with `only <part>,...` (see step 2); the rest is the scope.

- No scope: the uncommitted changes plus the commits made during this session.
- `since <commit>`: everything from `<commit>` to the working tree.
- One or more paths: those files, as they are now.

If the scope is empty, or holds several unrelated features, or is too large for one focused lesson, ask the developer once what to cover. Several unrelated features become separate lessons: propose them, then run steps 3–8 once per lesson.

**Done when** you can name the base commit, the head commit, whether uncommitted changes are included, and every file in scope.

## 2. Parts

A lesson has one or more of these parts:

| part | the learner gets | you write |
|---|---|---|
| `explain` | an explanation with diagrams | `explanation.md` |
| `decisions` | the architectural decisions and rejected alternatives | `decisions.md` |
| `notebook` | the key functions, runnable and editable | `notebook.ipynb`, `fixtures/` |
| `quiz` | 5–10 questions | `quiz.json` |
| `rebuild` | 1–3 functions to rebuild from a stub until the tests pass | `exercises/` |

If the arguments start with `only`, make exactly those parts. Otherwise ask the developer once which parts they want, offering all five as the default. Write them, in the order above, as `parts` in `lesson.json`.

**Done when** you have the list of parts. Steps 3–8 cover only those parts.

## 3. Gather

Read the diff, every touched file in full, and the reasoning in this conversation, including the alternatives that were considered and why they lost.

**Done when** you have a written list of every architectural decision made in the session, each with its rejected alternatives — or you have confirmed there were none.

## 4. Plan

Pick, and write down:

- 3–7 **key functions** — the ones that carry the idea of the build. In the notebook they become `function` cells; everything else is imported from the project.
- the **concepts** a learner needs, and the prerequisites they're assumed to have;
- the **decisions** from step 3;
- with `rebuild`: 1–3 **exercises**, key functions a learner can rebuild from a stub, testable with small inline inputs.

**Done when** each key function has a source ref (`path:start-end`) checked against the current file, and each exercise has the edge case its tests will pin down.

## 5. Environment

In the project root, run `synapto doctor` (add `--python PATH` if the project venv isn't `.venv`, `venv` or `$VIRTUAL_ENV`). With `notebook` or `rebuild`, lesson code runs in that interpreter: if doctor reports `MISSING`, show the developer the printed fix command and ask before running it — it installs into their venv. Without either part nothing runs, so `MISSING` doesn't matter.

**Done when** you have the interpreter path and version for `lesson.json`, and — with `notebook` or `rebuild` — `synapto doctor` prints `Ready`.

## 6. Write the bundle

Read [bundle-format.md](bundle-format.md) in full first: it is the format and the bar for each file.

Create a working directory with `mktemp -d` and write the bundle to `<that dir>/<lesson id>/`: `lesson.json` plus the files of the chosen parts, and nothing for the other parts. Keep everything — the bundle, fixture-generating scripts, scratch files — out of the project repo.

**Done when** every file of the chosen parts exists and every rule in bundle-format.md for those parts has been applied.

## 7. Validate

Run `synapto validate <bundle>`. Each error reads `file:location: message`; fix them all, then re-run. Allow up to 5 runs. Fix the bundle, never the project: if the project code itself is broken, that's a finding for the developer.

**Done when** the output ends in `<bundle>: valid`. After 5 failing runs, stop: report the remaining errors and the bundle path to the developer.

## 8. Publish

Run `synapto publish <bundle>`. If the id is already published, set `id` in `lesson.json` to the free id the error suggests and publish again. Use `--force` only when the developer asked to replace that lesson.

**Done when** publish prints `Lesson URL:`. Give the developer that URL and a two-line summary of what the lesson covers. If the hub isn't running, they start it with `synapto serve`.
