# debrief

Work in progress. See [docs/spec.md](docs/spec.md).

## Try it (development)

```sh
uv tool install --editable .              # puts `debrief` on PATH
claude --plugin-dir ./plugin              # run from your project; then type /debrief
```

`debrief publish` copies lessons into `~/.debrief` (override with `DEBRIEF_HOME`).
`debrief serve --open` starts the hub on http://127.0.0.1:8765.

### Web UI

The UI is a React + Vite app in `web/` ([ADR-0005](docs/adr/0005-frontend-react-vite.md));
its design reference is in [docs/design/](docs/design/README.md). Node is only needed to work on it:

```sh
cd web && npm install
npm run build        # writes the app to src/debrief/web/, which `debrief serve` serves
npm run dev          # hot-reloading UI on :5173; proxies /api to a running `debrief serve`
```
