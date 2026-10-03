"""Grade exercise code with pytest in the project's own venv (ADR-0004, spec §9.3).

The code under test is written to ``candidate.py`` in a fresh temp dir next to
a copy of the exercise's ``test_exercise.py``, and pytest runs there with the
project interpreter. Results come from pytest's JUnit XML report, so the
project venv needs nothing beyond pytest itself.

``synapto validate`` uses this to check that tests pass on ``solution.py`` and
fail on ``stub.py``; the server uses it to grade the learner's code.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from synapto.environment import interpreter_path, project_env

TEST_TIMEOUT = 60.0
_MAX_MESSAGE_LINES = 30

TestStatus = Literal["passed", "failed", "error", "skipped"]


@dataclass(frozen=True)
class TestResult:
    __test__ = False  # not a pytest test class

    name: str
    status: TestStatus
    message: str = ""


@dataclass(frozen=True)
class TestRun:
    """The outcome of one pytest run.

    ``error`` is set when pytest couldn't produce per-test results: a collection
    error (e.g. the candidate doesn't import), no tests found, or a timeout.
    """

    __test__ = False

    results: tuple[TestResult, ...] = ()
    error: str | None = None

    @property
    def n_passed(self) -> int:
        return sum(r.status == "passed" for r in self.results)

    @property
    def passed(self) -> bool:
        """True if pytest ran and every test passed."""
        return self.error is None and bool(self.results) and self.n_passed == len(self.results)


def _trim(text: str) -> str:
    lines = text.strip().splitlines()
    if len(lines) > _MAX_MESSAGE_LINES:
        lines = ["...", *lines[-_MAX_MESSAGE_LINES:]]
    return "\n".join(lines)


def _parse_report(report: Path) -> tuple[TestResult, ...]:
    results = []
    for case in ET.parse(report).getroot().iter("testcase"):
        status: TestStatus = "passed"
        message = ""
        for tag in ("failure", "error", "skipped"):
            node = case.find(tag)
            if node is not None:
                status = "failed" if tag == "failure" else tag  # type: ignore[assignment]
                message = _trim(node.text or node.get("message") or "")
                break
        results.append(TestResult(name=case.get("name", "?"), status=status, message=message))
    return tuple(results)


def run_tests(
    code: str,
    test_file: Path,
    python: str | os.PathLike[str],
    cwd: Path,
    extra_sys_path: Sequence[str] = (),
    timeout: float = TEST_TIMEOUT,
) -> TestRun:
    """Run ``test_file`` against ``code`` (as ``candidate.py``) with ``python``.

    ``cwd`` and ``extra_sys_path`` are the lesson's ``environment``: the entries
    are resolved against ``cwd`` and put on ``PYTHONPATH`` so tests can import
    the real project.
    """
    python = interpreter_path(python)
    env = project_env(python)
    env["PYTHONPATH"] = os.pathsep.join(str((cwd / p).resolve()) for p in extra_sys_path)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    with tempfile.TemporaryDirectory(prefix="synapto-test-") as tmp:
        root = Path(tmp)
        (root / "candidate.py").write_text(code, encoding="utf-8")
        shutil.copyfile(test_file, root / "test_exercise.py")
        # An empty config file pins pytest's rootdir here, so no outer config applies.
        (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        try:
            proc = subprocess.run(
                [str(python), "-m", "pytest", "-q", "-p", "no:cacheprovider",
                 "--junitxml=report.xml", "test_exercise.py"],
                cwd=root, env=env, capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return TestRun(error=f"pytest did not finish within {timeout:g}s")
        except OSError as exc:
            return TestRun(error=f"could not run {python}: {exc}")

        output = _trim(proc.stdout + proc.stderr)
        if proc.returncode == 5:
            return TestRun(error="pytest collected no tests; test functions must be named test_*")
        if proc.returncode not in (0, 1):
            return TestRun(error=f"pytest exited with code {proc.returncode}:\n{output}")
        report = root / "report.xml"
        if not report.is_file():
            return TestRun(error=f"pytest wrote no report:\n{output}")
        return TestRun(results=_parse_report(report))
