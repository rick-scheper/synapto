# TestResult

TestResult lists per-test results after "Run tests" in Rebuild.

**Props:** `tests` — `[{name, status: 'passed' | 'failed', message?}]`.

- Header shows "n of m passed" as a success/danger badge.
- Failing rows sit on `danger-soft` with the trimmed pytest message in mono; passing rows stay on the panel.
- Test names are the pytest function names, in mono.
