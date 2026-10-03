# DecisionCard

DecisionCard presents one architectural decision from decisions.md.

**Props:** `title`, `context`, `options` — `[{id, label}]`, `chosen` (an option id), `why`, `tradeoffs`.

- The chosen option is highlighted with `accent-soft` + a "Chosen" badge; rejected options stay visible so the learner sees the alternatives.
- "Revisit decision" copies a prompt for Claude Code to the clipboard.
- Stack cards in a `reading-width` column, `space-4` apart.
