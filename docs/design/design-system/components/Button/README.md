# Button

Button triggers an action; one `primary` per view at most.

**Props:** `variant` — `primary` | `secondary` (default) | `ghost` | `danger`; `size` — `md` (36px) | `sm` (28px); `icon` — a glyph or icon element before the label; plus any `<button>` attribute (`onClick`, `disabled`).

- `primary` (accent fill, `on-accent` label, glow on hover): the main next step — "Run all", "Run tests", "Check answer".
- `secondary` (line-strong border): everything else — "Restart kernel", "Revisit decision".
- `ghost`: toolbar and in-cell actions ("Run" on a CodeCell).
- `danger`: destructive only — "Remove lesson", "Reset notebook".
- Labels are sentence-case verbs. Never two primary buttons side by side.
