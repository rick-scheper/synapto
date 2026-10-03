# ADR-0002: Store the dissected code as a standard .ipynb notebook

- **Status:** Accepted
- **Date:** 2026-10-03

## Context

Each lesson contains the built code, split into runnable cells: setup, the functions themselves, demos, and short explanations in between. The hub needs some extra information per cell (its role, which source lines it came from, whether it's hidden). The format should be easy for an agent to write correctly, and readable outside debrief too.

## Options considered

1. **Standard nbformat 4 `.ipynb`**, with debrief data in cell metadata. It renders on GitHub, opens in Jupyter or VS Code, and has libraries (`nbformat`, `nbclient`) for reading, validating and executing it. The cost is verbose JSON, and the metadata conventions have to be documented.
2. **Custom JSON cell format.** It gives full control and a smaller schema. But it's another format to maintain and needs its own executor, and nothing else can open it.

Agent recommendation at the time: Option 1, because cell metadata covers the extra fields and the ecosystem (execution, rendering, diffing) comes for free.

## Decision

We chose **standard `.ipynb` with a `debrief` metadata key per cell**.

**Rationale:** `.ipynb` is a standard format that renders everywhere (GitHub, Jupyter, VS Code).

## Consequences

- `nbformat` reads and validates the notebook. Execution does not use `nbclient`: `debrief validate` runs the cells through the same `LessonKernel` the hub uses (ADR-0001), so there is one execution path to maintain and a notebook that validates runs the same way in the hub.
- A lesson stays useful even without the hub (open it in Jupyter).
- The agent has to emit valid nbformat JSON. The validator must give clear errors when it doesn't.
- Revisit if the hub needs cell types that Jupyter can't represent (e.g. interactive widgets bound to quiz state).
- Reversibility: easy. Converting `.ipynb` to a custom format later is a straightforward script.
