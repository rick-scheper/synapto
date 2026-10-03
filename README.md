<p align="center">
  <img src="https://raw.githubusercontent.com/rick-scheper/synapto/main/docs/design/design-system/assets/logos/synapto-logo-lockup.png" alt="Synapto" width="360">
</p>

**Understand the code your coding agent writes.**

After Claude Code has built something, run `/debrief`. The agent writes a lesson about exactly what it just built and publishes it to Synapto, a learning hub that runs on your own machine. In the lesson you can:

- **Explain:** read a walkthrough of the build, with diagrams.
- **Decisions:** review the architectural choices the agent made, and the alternatives it rejected.
- **Notebook:** run and edit the built code, split into functions. It runs in your project's own venv, on fixtures or on your real data.
- **Quiz:** check that you understood it.
- **Rebuild:** rewrite the key functions from a stub until the tests pass.

<!-- Demo GIF: record docs/demo.gif (see "Recording the demo" below), then uncomment:
<p align="center"><img src="https://raw.githubusercontent.com/rick-scheper/synapto/main/docs/demo.gif" alt="Running /debrief and opening the lesson" width="800"></p>
-->

## Install

You need Python ≥ 3.11 and [Claude Code](https://claude.com/claude-code).

```sh
pipx install synapto-hub        # or: uv tool install synapto-hub
```

This installs the `synapto` command. Next, add the Claude Code plugin, which provides the `/debrief` and `/decide` skills. Run these inside Claude Code:

```
/plugin marketplace add rick-scheper/synapto
/plugin install synapto@synapto
```

Your project's venv needs `ipykernel` and `pytest`. `synapto doctor` checks for them and prints the install command if one is missing. The skill runs this check for you.

## Use it

1. In your project, let the agent build something.
2. Type `/debrief`. The agent asks which parts you want: explanation, decisions, notebook, quiz and rebuild exercises. To skip that question, name them: `/debrief only explain,quiz`. To narrow the scope, use `/debrief since a1b2c3d` or `/debrief src/pkg/module.py`.
3. The agent writes the lesson, checks it with `synapto validate` and publishes it with `synapto publish`. It then gives you the lesson URL.
4. Start the hub with `synapto serve --open`. It serves on http://127.0.0.1:8765.

### Before you build: `/decide`

Facing a choice before any code exists, such as which database to use? Type `/decide "which database fits this project?"`, optionally followed by the candidates you have in mind. The agent researches the strongest candidates and publishes a **decision lesson**: an explanation of the problem space, the options compared on criteria that matter for your project, and a quiz.

- `/decide guided "…"`: the lesson leads you to the agent's recommendation.
- `/decide open "…"`: you make the call. Pick an option on the lesson's Options tab and write down why, then run `/decide review <lesson id>`. The agent challenges your reasoning in Claude Code, and the hub then shows its verdict next to the recommendation it wrote down *before* you chose. At the end it offers to record the decision as an ADR in your project.

| Command | What it does |
|---|---|
| `synapto serve [--open] [--port N] [--reload]` | Start the hub on 127.0.0.1; `--reload` restarts a hub that's already running |
| `synapto doctor [--python PATH]` | Check that a project interpreter can run lessons |
| `synapto validate <bundle>` | Check a lesson bundle: it runs the notebook, and checks that the tests pass on the solution and fail on the stub |
| `synapto publish <bundle> [--force]` | Validate a bundle and add it to your library |
| `synapto decision show <id>` / `synapto decision verdict <id> <file>` | Read and store the review of an open decision (used by `/decide review`) |
| `synapto remove <id> [--yes]` | Delete a lesson and your progress in it (or use **Delete lesson** in the hub) |

Lessons and your progress live in `~/.synapto` (override with `SYNAPTO_HOME`).

## Scope and safety

Synapto v1 supports Python projects with Claude Code, for a single local user. Lesson code runs **with your own permissions** in your project's interpreter, with no sandbox. Lessons are generated from your own code. The server binds only to `127.0.0.1` and rejects cross-site and DNS-rebinding requests. See [spec §11](docs/spec.md#11-security-model).

## Development

```sh
uv sync                                   # Python deps + dev tools
uv run pytest
claude --plugin-dir ./plugin              # run from a project to try the skill from this checkout
uv tool install --editable .              # puts this checkout's `synapto` on PATH
```

The UI is a React + Vite app in `web/` ([ADR-0005](docs/adr/0005-frontend-react-vite.md)). Its design reference is in [docs/design/](docs/design/README.md). You only need Node to work on the UI:

```sh
cd web && npm install
npm run build        # writes the app to src/synapto/web/, which `synapto serve` serves and the wheel ships
npm run dev          # hot-reloading UI on :5173; proxies /api to a running `synapto serve`
```

[docs/spec.md](docs/spec.md) is the full specification, and [docs/adr/](docs/adr/README.md) holds the architecture decisions.

### Releasing

1. Bump `version` in `pyproject.toml`, `plugin/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.
2. Tag and push: `git tag v0.1.0 && git push origin main v0.1.0`.

The `release` workflow builds the UI, runs the tests and builds the wheel. It checks that the wheel contains the UI and that the tag matches the version, then publishes `synapto-hub` to PyPI through [trusted publishing](https://docs.pypi.org/trusted-publishers/). Set this up once on PyPI for the repo, the `release.yml` workflow and the `pypi` environment. The plugin goes live when its manifest reaches `main` on GitHub.

### Recording the demo

`docs/demo.gif` is about 20–30 s at 800 px wide. It shows: `/debrief` finishing in Claude Code with a `Lesson URL:` → the Library → Explain → running a Notebook cell → a passing Rebuild test run.

## License

[MIT](LICENSE)
