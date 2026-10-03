# ADR-0005: Build the web UI as a React + Vite + TypeScript single-page app

- **Status:** Accepted
- **Date:** 2026-10-03

## Context

The hub is a local web page served by the FastAPI server. Four of its pages mostly display content (Library, Explain, Decisions, Quiz). Two behave like small applications: the Notebook (editable cells, outputs streamed over a WebSocket while a cell runs, rich outputs such as tables, images and Plotly) and Rebuild (a code editor, a test run, per-test results). The UI must ship prebuilt inside the wheel so `pipx install synapto-hub` needs no Node, work offline on 127.0.0.1, render Markdown and Mermaid, and use a real code editor. The author is stronger in Python than in frontend work and builds the UI mostly with a coding agent.

## Options considered

1. **React + Vite + TypeScript SPA**: suits client-heavy pages, has the largest ecosystem (CodeMirror, Markdown, Mermaid, Plotly components), and coding agents write it fluently. The cost is a Node toolchain for development and CI, and the most code to read.
2. **Svelte + Vite SPA**: the same architecture with much less, more readable code. The cost is a smaller ecosystem and less consistent agent output (Svelte 4 vs 5).
3. **Server-rendered pages with HTMX, plus JS islands**: keeps most of the UI in Python. But the Notebook and Rebuild pages still need hand-written client-side JS, CodeMirror still needs bundling, and Jinja becomes a new dependency.

Agent recommendation at the time: Option 1, because the pages that define Synapto are client-heavy, and that is where libraries and agent fluency save the most.

## Decision

We chose **React + Vite + TypeScript, as a single-page app**.

**Rationale (user's own words):** We are serving client-heavy apps on the site, so this option is the best. I don't need to own the frontend code, since it isn't that important.

## Consequences

- Source lives in `web/`. `vite build` writes static files to `src/synapto/web/`, which FastAPI serves and the wheel ships. Users never need Node; contributors and CI do.
- The HTTP and WebSocket API (spec §9.1) is the only contract between server and UI. The frontend holds no lesson logic of its own.
- Frontend code is agent-maintained rather than author-owned. Keep it conventional (mainstream libraries, few abstractions) so any agent can pick it up, and test behaviour through the API where possible.
- Revisit if the bundle size or the Node toolchain becomes a real burden for releases.
- Reversibility: moderate. The API stays; replacing the framework means rewriting the components, not the server.
