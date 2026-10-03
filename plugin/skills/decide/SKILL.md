---
name: decide
description: Turn a choice that's still open (which database, queue, framework…) into a decision lesson, or review the developer's decision in one.
argument-hint: "[guided|open] \"<question>\" [candidate…] | review <lesson id>"
disable-model-invocation: true
---

# /decide

Write a **decision lesson**: a lesson about a choice the developer faces *before* the code exists, so they understand the trade-offs instead of accepting the first suggestion. Like `/debrief`, the lesson is a **bundle** that `synapto validate` checks and `synapto publish` copies into the developer's local hub.

Arguments: `$ARGUMENTS`

Before anything else, run `synapto --help`. If the command is missing, tell the developer to install it (`pipx install synapto-hub`) and stop.

If the arguments start with `review`, read [review.md](review.md) and follow it instead of the steps below.

A decision lesson has a **mode**:

- `guided`: the lesson leads to your recommendation, shown from the start.
- `open`: the developer decides. The hub keeps your recommendation hidden until `/decide review` has challenged their choice.

## 1. Question

Restate the question in one sentence. Then write down the **project context** it depends on: what is being built, the scale, who runs it, the existing stack and the hard constraints. Read the repo (if there is one) and this conversation for it.

If the question is too vague to choose criteria from, ask the developer once.

**Done when** you have the question and a context list specific enough that two candidates could score differently on it.

## 2. Mode and parts

If the arguments start with `guided` or `open`, that is the mode. Otherwise ask the developer once: do they want a recommendation (`guided`), or do they want to decide themselves and have you test that decision (`open`)?

The parts are `options` (always), plus `explain` and `quiz`. Make all three unless the developer asked for fewer.

**Done when** you have the mode and the parts.

## 3. Candidates and criteria

- **Criteria**: 2–8 things this project's context makes matter, each with a weight from 1 to 3. Derive them from the context in step 1; a criterion that every candidate scores the same on teaches nothing, so drop it.
- **Candidates**: start from the ones the developer named. Add the strongest alternatives they missed, and drop any that can't meet a hard constraint, telling the developer why. Keep 2–5.

**Done when** every candidate is either kept or dropped with a reason, and every criterion traces back to a line of the context list.

## 4. Research

Check the facts each score rests on (limits, licences, current versions, maintenance status) against primary sources: official docs, the project's own repo, release notes. Put the sources in each option's `links`.

**Done when** every score on a criterion has a fact behind it, and you've noted which facts you couldn't verify.

## 5. Recommend

Pick the option you would choose for *this* project and write `recommendation`: why, what it costs, and what would change your mind. Do this now in both modes, before the developer has chosen: in open mode it stays sealed until the review, so it can't bend towards their answer.

**Done when** `would_change_if` names a concrete change in the context, not a generic one.

## 6. Write the bundle

Read [decision-format.md](decision-format.md) in full first: it is the format and the bar for each file.

Create a working directory with `mktemp -d` and write the bundle to `<that dir>/<lesson id>/`. Keep it out of the project repo.

**Done when** every file of the chosen parts exists and every rule in decision-format.md has been applied.

## 7. Validate

Run `synapto validate <bundle>`. Each error reads `file:location: message`; fix them all and re-run, up to 5 runs.

**Done when** the output ends in `<bundle>: valid`. After 5 failing runs, stop: report the remaining errors and the bundle path to the developer.

## 8. Publish

Run `synapto publish <bundle>`. If the id is already published, set `id` in `lesson.json` to the free id the error suggests and publish again.

**Done when** publish prints `Lesson URL:`. Give the developer that URL and a two-line summary. In open mode, add the next step: make the choice on the lesson's Options tab, then run `/decide review <lesson id>`. If the hub isn't running, they start it with `synapto serve`.
