# debrief

Work in progress. See [docs/spec.md](docs/spec.md).

## Try it (development)

```sh
uv tool install --editable .              # puts `debrief` on PATH
claude --plugin-dir ./plugin              # run from your project; then type /debrief
```

`debrief publish` copies lessons into `~/.debrief` (override with `DEBRIEF_HOME`).
