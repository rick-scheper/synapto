---
name: debrief
description: Turn what was just built into an interactive lesson and publish it to the local debrief hub.
argument-hint: "[since <commit> | <path>...]"
disable-model-invocation: true
---

# /debrief

Write a **lesson** about the code built in this session, so the developer — the **learner** — understands it instead of just accepting it. The lesson is a **bundle**: a folder of files that `debrief validate` checks and `debrief publish` copies into the developer's local hub.

Scope argument: `$ARGUMENTS`

Before step 1, run `debrief --help`. If the command is missing, tell the developer to install it (`pipx install debrief`) and stop.

## 1. Scope

- No argument: the uncommitted changes plus the commits made during this session.
- `since <commit>`: everything from `<commit>` to the working tree.
- One or more paths: those files, as they are now.

If the scope is empty, or holds several unrelated features, or is too large for one focused lesson, ask the developer once which part to cover. Several unrelated features become separate lessons: propose them, then run steps 2–7 once per lesson.

**Done when** you can name the base commit, the head commit, whether uncommitted changes are included, and every file in scope.

## 2. Gather

Read the diff, every touched file in full, and the reasoning in this conversation, including the alternatives that were considered and why they lost.

**Done when** you have a written list of every architectural decision made in the session, each with its rejected alternatives — or you have confirmed there were none.

## 3. Plan

Pick, and write down:

- 3–7 **key functions** — the ones that carry the idea of the build. These become `function` cells; everything else is imported from the project.
- the **concepts** a learner needs, and the prerequisites they're assumed to have;
- the **decisions** from step 2;
- 1–3 **exercises**: key functions a learner can rebuild from a stub, testable with small inline inputs.

**Done when** each key function has a source ref (`path:start-end`) checked against the current file, and each exercise has the edge case its tests will pin down.

## 4. Environment

In the project root, run `debrief doctor` (add `--python PATH` if the project venv isn't `.venv`, `venv` or `$VIRTUAL_ENV`). If it reports `MISSING`, show the developer the printed fix command and ask before running it — it installs into their venv.

**Done when** `debrief doctor` prints `Ready`, and you have the interpreter path and version for `lesson.json`.

## 5. Write the bundle

Read [bundle-format.md](bundle-format.md) in full first: it is the format and the bar for each file.

Create a working directory with `mktemp -d` and write the bundle to `<that dir>/<lesson id>/`. Keep everything — the bundle, fixture-generating scripts, scratch files — out of the project repo.

**Done when** every required file exists and every rule in bundle-format.md has been applied.

## 6. Validate

Run `debrief validate <bundle>`. Each error reads `file:location: message`; fix them all, then re-run. Allow up to 5 runs. Fix the bundle, never the project: if the project code itself is broken, that's a finding for the developer.

**Done when** the output ends in `<bundle>: valid`. After 5 failing runs, stop: report the remaining errors and the bundle path to the developer.

## 7. Publish

Run `debrief publish <bundle>`. If the id is already published, set `id` in `lesson.json` to the free id the error suggests and publish again. Use `--force` only when the developer asked to replace that lesson.

**Done when** publish prints `Lesson URL:`. Give the developer that URL and a two-line summary of what the lesson covers. If the hub isn't running, they start it with `debrief serve`.
