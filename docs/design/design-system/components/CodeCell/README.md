# CodeCell

CodeCell is one notebook cell — the heart of the hub.

**Props:** `code` (Python source, highlighted with the `code-*` tokens), `role` — `setup` | `function` | `demo`; `fn` — function name for function cells; `sourceRef` — `path:lines`; `status` — `idle` | `running` | `done` | `error`; `execCount`; `output` (string); `time` ("Ran in 0.42 s").

- Code sits on `surface-sunken`; header shows `[n]`, role overline, function name in `code-function`, the source ref and a ghost Run button.
- `running`: accent border + `shadow-glow` + pulsing glow dot — the only glowing thing on the page.
- `error`: danger border, traceback on `danger-soft`.
- `explain` cells are plain prose between cells, not a CodeCell.
