# Lesson bundle format

`debrief validate` enforces every **must** below. Unknown JSON fields are errors, so copy key names exactly.

```
<lesson-id>/
├── lesson.json            metadata, source, environment, data slots
├── explanation.md         the narrative, with at least one diagram
├── decisions.md           architectural decisions, or one line saying there were none
├── diagrams/              optional: .svg / .mmd files referenced from the Markdown
├── notebook.ipynb         the key functions, dissected and runnable
├── fixtures/              optional: small sample inputs, ≤ 5 MB in total
├── quiz.json              5–10 questions
└── exercises/             1–3 exercises
    └── 01-<slug>/
        ├── exercise.json
        ├── stub.py
        ├── solution.py
        └── test_exercise.py
```

## lesson.json

```json
{
  "schema_version": 1,
  "id": "2026-10-03-voxel-downsampling",
  "title": "Voxel downsampling",
  "summary": "One or two sentences on what was built and why.",
  "created_at": "2026-10-03T11:20:00+02:00",
  "difficulty": "intermediate",
  "concepts": ["voxel grid", "spatial hashing"],
  "prerequisites": ["python dicts"],
  "source": {
    "repo_path": "/abs/path/to/repo",
    "remote": "https://github.com/me/repo",
    "branch": "main",
    "base_commit": "a1b2c3d",
    "head_commit": "e4f5a6b",
    "includes_uncommitted": false,
    "files": [{ "path": "src/pkg/snap.py", "sha256": "<64 hex chars>" }]
  },
  "environment": {
    "python": "/abs/path/to/repo/.venv/bin/python",
    "python_version": "3.12.4",
    "cwd": "/abs/path/to/repo",
    "extra_sys_path": ["src"]
  },
  "data_slots": [
    {
      "name": "points",
      "kind": "file",
      "description": "An .xyz point cloud: one 'x y z' line per point.",
      "default": "fixtures/points.xyz",
      "required": false
    }
  ]
}
```

- `id` is `<today's date>-<kebab-slug>`; the bundle folder has the same name.
- `created_at` has a timezone. `difficulty`: `beginner`, `intermediate` or `advanced`.
- `remote`, `branch`, `base_commit`, `head_commit` may be `null`.
- `source.files` lists every file that any `source_ref` points into, with the sha256 of its current contents (`sha256sum`, or `shasum -a 256` on macOS). Paths are relative to `repo_path`.
- `environment` comes from `debrief doctor`. `cwd` is usually the repo root. `extra_sys_path` holds directories, relative to `cwd`, that must be importable — `["src"]` for a src layout the venv doesn't already install, `[]` otherwise.
- `data_slots[].kind`: `file`, `dir`, `string` or `number`. A `file`/`dir` default is a path inside the bundle (a fixture); a `number` default is a JSON number.

## explanation.md

GitHub-flavoured Markdown, in this order:

1. **What was built** — one paragraph, plain terms.
2. **The problem it solves** — before any code.
3. **How it works** — concepts first, then a walk-through of the main path, with at least one diagram.
4. **How it fits in the codebase** — callers, data flow, files touched.
5. **Things to watch** — edge cases, performance, known limitations.

Diagrams go in ```` ```mermaid ```` fences, or as `![](diagrams/x.svg)` with the file present. Cite code as `path:start-end` (e.g. `src/pkg/snap.py:24-33`), matching the `source_ref` of the notebook cell it refers to.

## decisions.md

One section per decision from the session:

```markdown
## <Decision title>

**Context:** why a choice was needed.
**Options:** A — …; B — …; (C — …)
**Chosen:** B
**Why:** tied to this project's constraints.
**Trade-offs:** what this costs, and what would change the choice.
**ADR:** docs/adr/0007-….md (only if the project has one)
```

With no architectural decisions, the file is one line saying so.

## notebook.ipynb

A standard nbformat 4 notebook. Every cell carries `metadata.debrief.role`:

| role | cell type | contains |
|---|---|---|
| `setup` | code | imports from the real project, loading data from `DEBRIEF_DATA` |
| `function` | code | one key function, copied verbatim from the source; also needs `function` and `source_ref` |
| `demo` | code | a call to the function above on fixture data, printing inputs, an intermediate value and the output |
| `explain` | markdown | a few sentences between code cells: what to notice, what to try changing |

Optional metadata: `"hidden": true` hides a cell; `"editable": false` locks it (use for setup cells).

```json
{
  "nbformat": 4,
  "nbformat_minor": 5,
  "metadata": {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"}
  },
  "cells": [
    {"cell_type": "markdown", "id": "intro", "metadata": {"debrief": {"role": "explain"}},
     "source": "# Voxel downsampling\n\nWhat this notebook walks through."},
    {"cell_type": "code", "id": "setup", "execution_count": null, "outputs": [],
     "metadata": {"debrief": {"role": "setup", "editable": false}},
     "source": "import math\n\nfrom pkg.snap import read_xyz\n\npoints = read_xyz(DEBRIEF_DATA[\"points\"])"},
    {"cell_type": "code", "id": "fn-voxel-key", "execution_count": null, "outputs": [],
     "metadata": {"debrief": {"role": "function", "function": "voxel_key", "source_ref": "src/pkg/snap.py:24-33"}},
     "source": "def voxel_key(point, size):\n    ..."},
    {"cell_type": "code", "id": "demo-voxel-key", "execution_count": null, "outputs": [],
     "metadata": {"debrief": {"role": "demo"}},
     "source": "print(voxel_key(points[0], 1.0))"}
  ]
}
```

Cell `id`s are unique, 1–64 characters of letters, digits, `-` and `_`.

**Dissection:**

- Each `function` cell holds one top-level `def <function>` copied verbatim, and its `source_ref` is that function's exact line range in the current file.
- Each `function` cell is followed by at least one `demo` cell before the next `function` cell.
- Order cells so the notebook runs top to bottom in a fresh kernel.

**Runtime:** cells run with the project interpreter, in `environment.cwd`. Before the first cell, a hidden preamble puts `extra_sys_path` and the bundle folder on `sys.path` and defines `DEBRIEF_DATA` (slot name → value; file/dir slots become absolute paths) and `DEBRIEF_LESSON_DIR` (the bundle folder). Read inputs through `DEBRIEF_DATA[...]`, never through hard-coded paths.

## fixtures/

Small sample inputs for the data slots. Generate them with a script in your working directory rather than copying real data, and keep the total under 5 MB. A fixture is realistic enough that the demos show the interesting cases (the edge case, a collision, a negative value).

## quiz.json

```json
{
  "questions": [
    {
      "id": "q1",
      "prompt": "Why does voxel_key use math.floor instead of int()?",
      "options": [
        {"id": "a", "text": "…"},
        {"id": "b", "text": "…"},
        {"id": "c", "text": "…"},
        {"id": "d", "text": "…"}
      ],
      "correct": "b",
      "explanation": "Why b is right, and why the tempting wrong answers are wrong.",
      "concept": "floor division",
      "source_ref": "src/pkg/snap.py:24-33"
    }
  ]
}
```

5–10 questions, each with at least 3 options and a non-empty explanation; `concept` and `source_ref` are optional. Ask about understanding — why, what happens if, which trade-off — rather than names. Each wrong option is a misconception a smart developer could plausibly hold.

## exercises/

Folders are numbered `01-<slug>`, `02-<slug>`, `03-<slug>`, and each folder name equals its `exercise.json` `id`.

```json
{
  "id": "01-voxel-key",
  "title": "Compute voxel keys",
  "function": "voxel_key",
  "prompt": "Markdown: what to implement, the behaviour the tests expect, and why it matters.",
  "difficulty": "easy",
  "hints": ["A gentle nudge.", "A stronger one."],
  "source_ref": "src/pkg/snap.py:24-33"
}
```

- `difficulty`: `easy`, `medium` or `hard`. Hints go from gentle to nearly the answer.
- `solution.py`: the function as built, plus the imports it needs.
- `stub.py`: the same imports, signature, type hints and docstring, with the body `raise NotImplementedError`. The signatures must match exactly.
- `test_exercise.py`: imports with `from candidate import <function>`. Cover normal behaviour and at least one edge case taken from how the real code handles it. Every test fails against the stub.

**Runtime:** the tests run with the project interpreter in a fresh temp directory holding only `candidate.py` (the stub, the solution or the learner's code) and `test_exercise.py`, with `extra_sys_path` on `PYTHONPATH`. The bundle's fixtures are out of reach, so put test inputs inline.
