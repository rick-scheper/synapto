# Decision lesson format

`synapto validate` enforces every **must** below. Unknown JSON fields are errors, so copy key names exactly.

```
<lesson-id>/
├── lesson.json        always: metadata, kind, question, mode, parts
├── options.json       options (always): criteria, candidates, recommendation
├── explanation.md     explain: the problem space, with at least one diagram
├── diagrams/          optional: .svg / .mmd files referenced from the Markdown
└── quiz.json          quiz: 5–10 questions
```

A file is in the bundle exactly when its part is in `lesson.json` `parts`.

## In open mode

The developer reads `explanation.md`, the options and the quiz *before* choosing. Write them so that a careful reader could argue for more than one option: present each option's case on its own terms, and keep your recommendation in `recommendation` alone. The hub hides that field until the review.

## lesson.json

```json
{
  "schema_version": 1,
  "kind": "decision",
  "id": "2026-10-03-gridsnap-storage",
  "title": "Where should gridsnap keep its point clouds?",
  "summary": "One or two sentences on the choice and why it matters for this project.",
  "created_at": "2026-10-03T14:00:00+02:00",
  "difficulty": "intermediate",
  "concepts": ["embedded vs client-server databases", "spatial indexing"],
  "prerequisites": ["basic SQL"],
  "question": "Which database should gridsnap use to store point clouds and query them by bounding box?",
  "mode": "open",
  "parts": ["explain", "options", "quiz"],
  "source": {
    "repo_path": "/abs/path/to/repo",
    "remote": null,
    "branch": "main",
    "base_commit": null,
    "head_commit": "e4f5a6b",
    "includes_uncommitted": true,
    "files": []
  }
}
```

- `id` is `<today's date>-<kebab-slug>`; the bundle folder has the same name.
- `question` is the developer's question, in their words. `mode` is `guided` or `open`.
- `parts` holds `options` and optionally `explain` and `quiz`, in that order.
- `source` is optional: give it when the question is about an existing repo, so the hub groups the lesson with that repo's lessons. `files` stays `[]`, since there's no built code to point at. Leave out `source` when there's no repo yet.
- Leave out `environment` and `data_slots`: nothing runs in a decision lesson.
- `created_at` has a timezone. `difficulty`: `beginner`, `intermediate` or `advanced`.

## options.json

```json
{
  "criteria": [
    { "id": "ops", "name": "Operational simplicity", "description": "Nothing to run, back up or upgrade besides a file.", "weight": 3 }
  ],
  "options": [
    {
      "id": "sqlite",
      "name": "SQLite + R*Tree",
      "summary": "One sentence: what it is.",
      "strengths": ["A strength that matters for this project"],
      "weaknesses": ["A weakness that matters for this project"],
      "fits_when": "The situation in which this is the right choice.",
      "scores": { "ops": 5 },
      "links": [{ "title": "The SQLite R*Tree module", "url": "https://www.sqlite.org/rtree.html" }]
    }
  ],
  "recommendation": {
    "option": "sqlite",
    "why": "Markdown, tied to this project's context.",
    "trade_offs": "What the choice costs.",
    "would_change_if": "The concrete change in context that would make another option better."
  }
}
```

- 2–8 criteria and 2–5 options. Each `id` is lowercase kebab-case and unique.
- `weight`: 1 (nice to have) to 3 (decisive).
- Every option scores **every** criterion, 1 (poor) to 5 (excellent), and nothing else. Score for this project's context, not in general.
- `strengths` and `weaknesses` each have at least one entry, and each one is specific to the project's context.
- `links` point to the primary sources behind the scores.
- `recommendation.option` is one of the option ids.

## explanation.md

GitHub-flavoured Markdown, in this order:

1. **The decision**: what has to be chosen and why it matters now.
2. **What matters here**: the project context, and how it turns into the criteria.
3. **Concepts you need**: the ideas needed to weigh the options (e.g. what a spatial index does), with at least one diagram.
4. **The landscape**: the families of solutions and where each candidate sits, including any candidates you dropped and why.

Diagrams go in ```` ```mermaid ```` fences, or as `![](diagrams/x.svg)` with the file present.

## quiz.json

Same format and bar as in a debrief lesson: see the quiz.json section of [../debrief/bundle-format.md](../debrief/bundle-format.md). Leave out `source_ref`. Ask about the trade-offs (which option suffers when X grows, what a criterion protects against) rather than about product trivia. In open mode, no question has "the recommended option" as its answer.
