# Tabs

Tabs switch between the five views of a lesson.

**Props:** `items` — array of strings or `{id, label, count?}`; `value` — the active id; `onChange(id)`.

- The lesson's tab order is fixed: Explain · Decisions · Notebook · Quiz · Rebuild.
- The active tab gets `ink` text and a 2px `accent` underline; the rest `ink-muted`. `count` shows remaining questions or exercises.
- One tab row per page; don't nest tabs.
