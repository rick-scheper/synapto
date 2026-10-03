# Synapto design handoff

Design reference for the debrief/Synapto hub UI (spec §12, milestone M2+). Put this folder at `docs/design/` in the repo. Nothing here is production code.

## What's here

```
design-system/
  brand-book.md        Read first. Voice, colour, type, layout, states, page layouts.
  tokens.json          Source of truth for all tokens (colours in dark + light, type, spacing, radius, shadows, sizes).
  tokens.css           The same tokens as CSS custom properties. Dark is default; light via <html data-theme="light">.
  components/
    <Name>/README.md   Usage rules per component (props, when to use, do/don't).
    <Name>/preview.html  Live preview markup (expects tokens.css + bundle.css + bundle.js + React 18 on the page).
    bundle.js / bundle.css / index.d.ts   Reference React implementation (window.Synapto), plain JS, no build step.
  assets/logos/        PNG logo files (raster on navy; no transparent/vector version yet).
screens/
  Main.dc.html         Library
  Explain.dc.html      Lesson · Explain tab
  Decisions.dc.html    Lesson · Decisions tab
  Notebook.dc.html     Lesson · Notebook tab
  Quiz.dc.html         Lesson · Quiz tab (interactive)
  Rebuild.dc.html      Lesson · Rebuild tab
  *-light.dc.html      Light-theme wrappers: they mount the dark screen with theme="light".
```

## How to use it when building the frontend

1. **Tokens are the contract.** Load `tokens.css` (or generate your stack's theme from `tokens.json`). Never hard-code a hex value or font; use the token names (`--surface`, `--accent`, `--space-4`, …).
2. **Components are a reference, not a dependency.** The frontend stack is still an open decision (spec §14, needs an ADR before M2). Rebuild the components in the chosen stack, matching the class styles in `bundle.css` and the props in `index.d.ts`. Don't import `bundle.js` into the app.
3. **Screens show layout and content.** The `.dc.html` files are Claude Design artboards: normal HTML with inline styles, plus `{{holes}}` filled from the `renderVals()` script at the bottom and `<x-import component-from-global-scope="Synapto.X">` tags that mount a component with the given props. Read them for structure, spacing and copy; they won't run on their own (they need the Claude Design runtime, `support.js`).
   - Paths `ds/synapto/…` point at `design-system/components/…`.
   - `/_blob/60a25a56…` is the logo mark → `design-system/assets/logos/synapto-mark.png`.
4. **Sample content is placeholder.** Lesson text, numbers and repo names in the screens illustrate the bundle format; real content comes from lesson bundles (spec §5).

## Rules worth repeating

- One primary (teal) button per view; glow (`--shadow-glow`) only on a running cell / just-passed exercise / hovered primary button, one at a time.
- Status is never colour alone: always ✓ / ✕ / ! plus a word.
- Lesson prose max `--reading-width` (720px); notebook and rebuild `--notebook-width` (960px).
- Sentence case everywhere; uppercase only for the `overline` style.
