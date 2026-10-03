# ADR-0001: Execute lesson code in a Jupyter kernel in the project's own venv

- **Status:** Accepted
- **Date:** 2026-10-03

## Context

A lesson's notebook and exercises run code that the agent just built. That code depends on the project's own packages (sometimes with native extensions), and the developer may want to run it on real local data instead of fixtures. Synapto runs locally for a single user, on code they wrote with their agent, so isolating that code from the developer's own machine isn't a goal.

## Options considered

1. **Jupyter kernel in the project venv** (`jupyter_client` + `ipykernel` in the project's interpreter). All of the project's dependencies and local files work, and it's mature, well-understood tech. The cost is that `ipykernel` has to be installed in each project's environment, and there is no isolation.
2. **Docker container per lesson.** It's reproducible and isolated. But it's heavy to build and start, it needs Docker installed, and using real data means mounting volumes.
3. **Pyodide in the browser.** It needs no backend and is safe. But it can't run arbitrary or native packages and can't read local files.

Agent recommendation at the time: Option 1, because real dependencies and real data are core requirements, and isolation buys nothing for a local single-user tool.

## Decision

We chose **Jupyter kernel in the project venv**.

**Rationale:** A Jupyter kernel in the project venv is the best option. It is the simplest and most widely understood solution to the problem.

## Consequences

- Lessons can import the real package and read any local file. The data slots feature becomes trivial.
- Each project needs `ipykernel` and `pytest` in its venv. `synapto doctor` detects and explains this.
- No sandboxing: a lesson runs with the developer's permissions. Importing bundles from others later will need a warning or an opt-in sandbox.
- Revisit if Synapto becomes multi-user or hosted, or if lessons get shared between people.
- Reversibility: moderate. The kernel manager is one module, and Docker or Pyodide backends could sit behind the same WebSocket protocol.
