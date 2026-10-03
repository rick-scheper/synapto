Synapto is a local learning hub: after a coding agent builds something, Synapto turns that build into a lesson — explanation, decisions, a runnable notebook, a quiz and rebuild exercises. The interface should feel like a **calm, precise instrument**: a dark navy workspace where the code is the subject, and the logo's teal glow appears only where something is alive — running, focused, passing.

Three ideas carry the whole system:

1. **Navy is the room, teal is the signal.** Large areas are always `surface` / `surface-raised` / `surface-sunken`. `accent` marks the one thing to act on or the thing that is active. If a screen has more than two teal elements at rest, remove one.
2. **Glow means "live".** `shadow-glow` and the `glow` colour come straight from the logo's lit nodes. Use them only for a running notebook cell, a just-passed exercise and the hovered primary button — one glowing element on screen at a time. Never decorative.
3. **Code is the hero.** Lessons are about code, so code cells get the most contrast (`surface-sunken` + full syntax colours) and the widest column. Chrome (nav, tabs, metadata) stays muted.

## Content fundamentals

- **Voice:** a patient senior colleague walking you through a PR. Direct, specific, never cute. Explain *why* before *what*.
- **Person:** address the learner as "you"; refer to the agent as "the agent" (not "AI", not "Claude did"). Synapto itself rarely says "I" or "we".
- **Casing:** sentence case for everything — titles, buttons, tabs ("Run tests", "Show solution"). The only uppercase is the `overline` style ("LESSON · INTERMEDIATE").
- **Buttons are verbs:** "Run all", "Restart kernel", "Revisit decision", "Check answer". Not "OK", "Submit", "Go".
- **Numbers over adjectives:** "3 of 5 tests passed", "Ran in 0.42 s", "Changed 2 days after this lesson".
- **No emoji** in UI or lesson prose. Status uses ✓ / ✕ / ! glyphs or icons, always next to a word.
- Real examples: "Why is the voxel key computed with floor division instead of rounding?" · "The code has changed since this lesson was made — 2 files differ." · "Show solution (available after 3 attempts)".

## Colour

Dark is the default theme (it is the logo's own ground); Light exists for long reading in bright rooms and must look like the same product.

- Page ground `surface`; cards and panels `surface-raised` with a 1px `line` border and `radius-lg`; anything *inside* a panel (code, outputs, inputs) `surface-sunken`.
- Text: `ink` for content, `ink-muted` for metadata. Never put `ink-muted` on an `*-soft` tint.
- `accent` for: the primary button (label `on-accent`), the active-tab underline, links (`link`), focus (`focus`), selection, progress fill. Tinted backgrounds use `accent-soft` with `accent` or `ink` text.
- `accent-deep` is the second teal from the logo's strands: diagram edges, the second data series, progress-ring track highlights. Not for text smaller than 18px.
- Status: `success` / `warning` / `danger` with their `*-soft` grounds. Status is never colour alone — always an icon or word ("✓ Passed", "✕ Failed", "! Stale").
- Syntax highlighting uses the `code-*` tokens on `surface-sunken`. `code-function` is the only text in `glow` colour, because function names are what a lesson is about.
- **Don't:** gradients (the logo's glow is a single radial bloom, not a gradient fill), purple, teal backgrounds larger than a button, glow on resting elements.

## Typography

- **Montserrat** (`display` family) for `display`, `h1`–`h3` and `overline` — the geometric caps echo the SYNAPTO wordmark. Weight 600; never above 700.
- **Inter** (`sans`) for all prose and UI: `body` (16/26) for lesson text, `body-sm` for UI copy, `label` for buttons/tabs, `caption` for timings.
- **JetBrains Mono** (`mono`) for `code` and `code-sm`: cells, the exercise editor, file paths and `source_ref` anchors like `src/pointtools/downsample.py:40-72`.
- All three are Google Fonts: load `https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap`.
- Lesson prose never exceeds `reading-width` (720px). Headings sit `space-7` above the previous section.

## Spacing, radius, layout

- 4px grid: `space-1` … `space-8`. Cards pad `space-4`; panels pad `space-5`; sections are `space-6`–`space-7` apart.
- Radii: `radius-sm` chips/badges, `radius-md` buttons/inputs/cells, `radius-lg` cards/panels, `radius-full` pills and dots.
- Controls are `control-height` (36px); `sm` controls 28px.
- Shadows are rare: resting cards have none. `shadow-raised` for menus and popovers only.

### Page layouts

- **Top bar** (`header-height`, `surface` with bottom `line`): logo mark + "Synapto" in `display` 600 at 16px, a repo switcher, search, theme toggle. Nothing teal at rest.
- **Library:** `page-max` centred. Header row: `h1` "Lessons" + filters (repo, concept chips). Lesson cards in a responsive grid (min 320px columns, `space-4` gap), grouped by repo with an `overline` repo heading. Each card: overline (date · difficulty), `h3` title, 2-line summary, concept badges, progress ring, stale badge if the code moved on.
- **Lesson:** a lesson header (overline, `h1`, `body-lg` summary, source line in `code-sm` + `ink-muted`) then **Tabs**: Explain · Decisions · Notebook · Quiz · Rebuild. Explain, Decisions and Quiz use a `reading-width` column with an optional sticky outline on the left (`sidebar-width`). Notebook and Rebuild use `notebook-width`; the Notebook puts the data-slot panel in the right sidebar.
- **Notebook:** a vertical stack of CodeCells, `space-5` apart, with a sticky toolbar (Run all · Restart · Reset) and kernel status (idle = `ink-muted` dot, busy = `accent` dot with glow).
- **Quiz:** one question per screen, options as full-width QuizOption rows, explanation revealed below after answering, score at the end.
- **Rebuild:** exercise prompt (prose) above, editor (CodeCell style, editable) in the middle, TestResult list below, hints as a disclosure list.
- Mobile isn't a target (it's a local dev tool), but the layout should still collapse to one column below 768px.

## Diagrams (Mermaid)

Explain tabs render Mermaid. Theme it from the tokens: node fill `surface-raised`, node border `accent-deep`, text `ink`, edges `accent-deep`, the highlighted/"this is what was built" node bordered in `accent`. 1.5px strokes, `radius-md` corners. No other colours.

## Iconography

No icon set ships with the brand yet. Use **Lucide** (outline, 1.5px stroke, 16px in UI, 20px in empty states) — its thin rounded strokes match the logo's strands. This is a substitution; replace it if Synapto gets its own icons. Icons take `currentColor` (`ink-muted` at rest, `ink` on hover, `accent` when active).

## Logo

- Assets in **Logos**: `synapto-logo-lockup.png` (mark above wordmark), `synapto-mark.png` (the neuron mark alone — favicon and top bar), `synapto-wordmark.png`, and the original artwork.
- They are rasters on the logo's navy ground. Place them only on a dark ground (`surface` dark). In the Light theme put the mark on a `#18202a` tile with `radius-md`, or set the name in Montserrat 600 instead.
- Give the mark clear space equal to its node-dot diameter ×2; never recolour, outline or add extra glow.

## States and motion

- Hover: background steps one surface up (`surface` → `surface-raised`) or text `ink-muted` → `ink`. Primary button hover adds `shadow-glow`.
- Focus: `shadow-focus` on every interactive element, always visible on keyboard focus.
- Active/selected: `accent-soft` ground + `accent` indicator (underline for tabs, 1px border for options).
- Disabled: 40% opacity, no hover.
- Running: `accent` 1px border + `shadow-glow` + a pulsing `glow` dot (opacity 1 → 0.4, 1.2 s ease-in-out). Respect `prefers-reduced-motion` — no pulse then.
- Transitions: 120–160 ms ease-out for colour/shadow; nothing bounces.

## Components

Components live in the `Synapto` namespace (React). They are reference implementations for design and prototyping — the tokens (CSS custom properties) are the contract for whatever frontend stack the hub ends up using.
