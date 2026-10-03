# ADR-0004: Grade "rebuild" exercises with pytest in the project venv

- **Status:** Accepted
- **Date:** 2026-10-03

## Context

In the Rebuild tab the learner rewrites a key function from a stub. They need clear, per-case feedback on what's wrong. The agent also has to prove, before publishing, that the tests are correct (they pass on the real implementation) and meaningful (they fail on the empty stub).

## Options considered

1. **pytest in a subprocess** using the project's interpreter. The learner's code is written to `candidate.py` and the tests import from it. You get per-test results with readable failure messages, it's the standard Python tool, and the same runner is used for validation. The cost is a subprocess per run (about a second of overhead) and a pytest dependency in the project venv.
2. **`assert` cells in the notebook kernel.** No extra process or dependency. But feedback is poor (it stops at the first failure, with no test names), and it's harder to isolate the learner's code from the original.

Agent recommendation at the time: Option 1, because per-test feedback is the core of the learning loop and the "fails on stub" check is easy with pytest.

## Decision

We chose **pytest in a subprocess, using the project's interpreter**.

**Rationale:** pytest gives per-test feedback and is the standard Python testing tool.

## Consequences

- Learners see every test case passing or failing, with messages.
- `synapto validate` can guarantee that tests pass on `solution.py` and fail on `stub.py`.
- `pytest` must be present in the project venv (checked by `synapto doctor`).
- Revisit if exercise runs feel slow. A pytest session could be kept warm inside the kernel instead.
- Reversibility: easy. The test runner is one small module behind one endpoint.
