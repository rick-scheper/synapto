# CLAUDE.md — debrief
 
## What this project is
 
**debrief** (working name) is an open-source, self-hosted learning hub for developers who build with coding agents.
 
After an agent has built something, the developer runs `/debrief` in Claude Code. The skill turns what was just built into an interactive **lesson** and publishes it to a local website. On that website the developer can:
 
- read an explanation with diagrams,
- review the architectural decisions the agent made, and the alternatives it rejected,
- run and edit the built code, dissected into functions, in a notebook that uses the project's real environment and (optionally) real data,
- take a quiz,
- rebuild key functions from a stub until the tests pass.
 
The goal is that developers understand the code their agent writes, instead of blindly accepting it.
 
This is a personal open-source project (to be published on GitHub). It has no ties to any employer.
 
## Scope (v1)
 
- **In scope:** Python projects only; Claude Code only; a single local user; a server bound to `127.0.0.1`.
- **Out of scope:** other languages, other agent harnesses, multiple users or auth, hosting, sandboxing.
 
Don't build for out-of-scope cases. Do keep the design open to them: the skill only writes files and calls the CLI, so it stays harness-agnostic.
 
## Source of truth
 
- `docs/spec.md` is the full specification: bundle format, skill steps, CLI, validation rules, server API, storage, UI and milestones. **Read the relevant section before implementing anything.**
- `docs/adr/` holds the architecture decisions. Follow accepted (and proposed) ADRs. Never silently introduce a new dependency or architectural pattern. Raise it as a decision first, and record it as a new ADR.
 
Current decisions:
 
| ADR | Decision |
|---|---|
| 0001 | Execute lesson code in a Jupyter kernel (`jupyter_client` + `ipykernel`) started with the **project's own venv** interpreter |
| 0002 | The notebook is a standard **`.ipynb`** (nbformat 4), with debrief data in cell metadata under the `debrief` key |
| 0003 | Published lessons live in a **central store** `~/.debrief/` (override: `DEBRIEF_HOME`), with SQLite for the index and progress |
| 0004 | Exercises are graded with **pytest in a subprocess** using the project's interpreter |
 
Still open (they need an ADR before the milestone that depends on them): the frontend stack (before M2), the final name, how lesson updates are versioned, and cross-lesson concept tracking.
 
## Core architecture in one paragraph
 
The **lesson bundle** (a folder with `lesson.json`, `explanation.md`, `decisions.md`, `notebook.ipynb`, `fixtures/`, `quiz.json` and `exercises/`) is the only contract between the skill and the hub. The `/debrief` skill writes a bundle to a temporary directory, then runs `debrief validate`, which executes the notebook in a fresh kernel and checks that the exercise tests **pass on `solution.py` and fail on `stub.py`**. It fixes errors and re-runs, up to 5 attempts, then runs `debrief publish`, which copies the bundle into `~/.debrief/lessons/<id>/` and indexes it. A FastAPI server (`debrief serve`) serves the web UI, starts kernels in the project venv, runs pytest for exercises, and stores everything the learner changes in SQLite. **Published bundles are immutable.**
 
## Repository layout
 
```
plugin/                     Claude Code plugin; skills/debrief/SKILL.md
src/debrief/cli.py          validate · publish · serve · list · open · doctor · remove
src/debrief/bundle/         pydantic models, loader, validator
src/debrief/server/         FastAPI app, kernel manager, test runner
src/debrief/store.py        lesson store + SQLite
src/debrief/web/            built frontend (generated; shipped in the wheel)
web/                        frontend source
docs/                       spec.md, adr/
tests/                      includes example bundles (valid + deliberately broken)
```
 
## Milestones (build in this order)
 
- **M0:** bundle models and `debrief validate`, tested against a hand-written example bundle and broken variants of it.
- **M1:** the `/debrief` skill and `publish`, producing a passing bundle for a real build.
- **M2:** the server and a read-only UI (Library, Explain, Decisions, Quiz).
- **M3:** notebook execution (kernel in the project venv, data slots, working copy and reset).
- **M4:** Rebuild exercises (pytest grading, drafts, progress).
- **M5:** release (pipx-installable wheel with the frontend bundled, plugin published, README).
 
The bundle is the contract, so the validator comes first. Don't start the UI before M0 and M1 work.
 
## Conventions
 
- Python ≥ 3.11, with type hints everywhere and pydantic v2 models for every bundle file.
- The CLI uses Typer. The server uses FastAPI and uvicorn. Tests use pytest.
- Validator errors are formatted as `file:location: message`, and the exit code is non-zero on failure. They are read by an agent, so make them specific and actionable.
- Never execute lesson code inside the debrief server process. Always use the project interpreter (kernel or subprocess).
- Notebook setup cells read data through `DEBRIEF_DATA[...]` and never hard-code paths.
- Keep `fixtures/` small (≤ 5 MB) and generate them with code where possible.
 
## Developer context
 
The author is an ML engineer with a background in applied mathematics, stronger in Python and backend work than frontend. When frontend choices come up, explain the trade-offs clearly instead of assuming familiarity.
