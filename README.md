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

This installs the `synapto` command. Next, add the Claude Code plugin, which provides the `/debrief` skill. Run these inside Claude Code:

```
/plugin marketplace add rick-scheper/synapto
/plugin install synapto@synapto
```

Your project's venv needs `ipykernel` and `pytest`. `synapto doctor` checks for them and prints the install command if one is missing. The skill runs this check for you.

## Use it

1. In your project, let the agent build something.
2. Type `/debrief`. To narrow the scope, use `/debrief since a1b2c3d` or `/debrief src/pkg/module.py`.
3. The agent writes the lesson, checks it with `synapto validate` and publishes it with `synapto publish`. It then gives you the lesson URL.
4. Start the hub with `synapto serve --open`. It serves on http://127.0.0.1:8765.

| Command | What it does |
|---|---|
| `synapto serve [--open] [--port N]` | Start the hub on 127.0.0.1 |
| `synapto doctor [--python PATH]` | Check that a project interpreter can run lessons |
| `synapto validate <bundle>` | Check a lesson bundle: it runs the notebook, and checks that the tests pass on the solution and fail on the stub |
| `synapto publish <bundle> [--force]` | Validate a bundle and add it to your library |

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
