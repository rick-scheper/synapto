"""``debrief validate``: check a lesson bundle before it is published (spec §8).

The validator reports every problem it can find in one pass, so the agent
writing the bundle can fix them all before re-running. Each issue reads
``file:location: message``, where ``location`` is a JSON path
(``questions[2].correct``), a notebook cell (``cells[4]``), a line number or a
test name.

Static checks always run. With ``execute=True`` (the default, and what the CLI
does) the validator also checks the project interpreter, runs the notebook top
to bottom in a fresh kernel (ADR-0001) and runs each exercise's tests against
``solution.py`` and ``stub.py`` (ADR-0004).
"""

from __future__ import annotations

import ast
import asyncio
import json
import re
import shutil
import subprocess
import tempfile
import textwrap
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypeVar

import nbformat
from pydantic import BaseModel, ValidationError

from debrief.bundle.models import CellMeta, Exercise, Lesson, Quiz, source_ref_path
from debrief.environment import check_interpreter
from debrief.server.kernels import KernelConfig, KernelError, LessonKernel
from debrief.server.testrunner import run_tests

REQUIRED_FILES = ("lesson.json", "explanation.md", "decisions.md", "notebook.ipynb", "quiz.json")
MARKDOWN_FILES = ("explanation.md", "decisions.md")
MAX_FIXTURES_BYTES = 5 * 1024 * 1024
MIN_EXERCISES, MAX_EXERCISES = 1, 3
SLOW_CELL_SECONDS = 30.0
CELL_TIMEOUT = 300.0
_TRACEBACK_LINES = 20

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_DIAGRAM_REF = re.compile(r"\]\(\s*<?(diagrams/[^)\s>]+)|src=[\"'](diagrams/[^\"']+)")
_MERMAID = re.compile(r"^```mermaid[ \t]*\n(.*?)^```", re.MULTILINE | re.DOTALL)

M = TypeVar("M", bound=BaseModel)


@dataclass(frozen=True)
class Issue:
    file: str
    location: str | None
    message: str
    severity: Literal["error", "warning"] = "error"

    def __str__(self) -> str:
        where = f"{self.file}:{self.location}" if self.location else self.file
        prefix = "warning: " if self.severity == "warning" else ""
        return f"{where}: {prefix}{self.message}"


@dataclass
class ValidationReport:
    bundle: Path
    issues: list[Issue] = field(default_factory=list)
    executed: bool = False  # whether the notebook and exercise tests were run

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_bundle(bundle: Path, execute: bool = True) -> ValidationReport:
    """Check the bundle at ``bundle``; ``execute=False`` skips everything that runs code."""
    return _Validator(Path(bundle).resolve(), execute).run()


def _json_path(loc: Sequence[int | str]) -> str:
    out = ""
    for part in loc:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out


def _pydantic_message(err: Any) -> str:
    kind, msg = err["type"], err["msg"]
    if kind == "missing":
        return "required field is missing"
    if kind == "extra_forbidden":
        return "unknown field; remove it or fix its spelling"
    if kind == "value_error":
        return msg.removeprefix("Value error, ")
    value = err.get("input")
    if kind != "json_invalid" and (value is None or isinstance(value, (str, int, float, bool))):
        return f"{msg} (got {json.dumps(value)})"
    return msg


def _indent(text: str) -> str:
    return textwrap.indent(text.rstrip(), "    ")


def _top_level_function(tree: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _signature(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    returns = f" -> {ast.unparse(fn.returns)}" if fn.returns else ""
    return f"({ast.unparse(fn.args)}){returns}"


def _imports_candidate(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "candidate":
            return True
        if isinstance(node, ast.Import) and any(a.name == "candidate" for a in node.names):
            return True
    return False


class _Validator:
    def __init__(self, bundle: Path, execute: bool) -> None:
        self.bundle = bundle
        self.execute = execute
        self.report = ValidationReport(bundle)

    def error(self, file: str, location: str | None, message: str) -> None:
        self.report.issues.append(Issue(file, location, message))

    def warn(self, file: str, location: str | None, message: str) -> None:
        self.report.issues.append(Issue(file, location, message, "warning"))

    # --- driver ------------------------------------------------------------

    def run(self) -> ValidationReport:
        if not self.bundle.is_dir():
            self.error(str(self.bundle), None, "bundle is not a directory")
            return self.report

        for name in REQUIRED_FILES:
            if not (self.bundle / name).is_file():
                self.error(name, None, "required file is missing")

        lesson = self.load_json("lesson.json", Lesson)
        quiz = self.load_json("quiz.json", Quiz)
        for name in MARKDOWN_FILES:
            self.check_markdown(name)
        cells = self.load_notebook()
        exercises = self.load_exercises()
        self.check_fixtures()

        if lesson is not None:
            self.check_data_slots(lesson)
            self.check_source_refs(lesson, quiz, cells, exercises)

        if self.execute and lesson is not None and self.check_environment(lesson):
            self.report.executed = True
            if cells is not None:
                asyncio.run(self.run_notebook(lesson, cells))
            for folder, exercise in exercises:
                if exercise is not None:
                    self.run_exercise(lesson, folder, exercise)
        return self.report

    # --- loading -----------------------------------------------------------

    def load_json(self, name: str, model: type[M], path: Path | None = None) -> M | None:
        path = path or self.bundle / name
        if not path.is_file():
            return None
        try:
            return model.model_validate_json(path.read_bytes())
        except ValidationError as exc:
            for err in exc.errors():
                self.error(name, _json_path(err["loc"]) or None, _pydantic_message(err))
            return None

    def load_notebook(self) -> list[tuple[int, Any, CellMeta]] | None:
        """The notebook's cells with their parsed ``debrief`` metadata, or None if unusable."""
        name = "notebook.ipynb"
        path = self.bundle / name
        if not path.is_file():
            return None
        try:
            nb = nbformat.reads(path.read_text(encoding="utf-8"), as_version=nbformat.NO_CONVERT)
        except Exception as exc:  # nbformat raises several unrelated types for bad input
            self.error(name, None, f"not a readable notebook: {exc}")
            return None
        if nb.get("nbformat") != 4:
            self.error(name, "nbformat", f"must be 4, got {nb.get('nbformat')!r}")
            return None
        try:
            nbformat.validate(nb)
        except nbformat.ValidationError as exc:
            where = _json_path(list(exc.absolute_path)) or None
            self.error(name, where, f"does not match the nbformat 4 schema: {exc.message}")
            return None

        cells: list[tuple[int, Any, CellMeta]] = []
        ok = True
        for i, cell in enumerate(nb.cells):
            raw = cell.metadata.get("debrief")
            if raw is None:
                self.error(name, f"cells[{i}]", "metadata.debrief is missing; every cell needs "
                           "a role (setup, function, demo or explain)")
                ok = False
                continue
            try:
                meta = CellMeta.model_validate(raw)
            except ValidationError as exc:
                for err in exc.errors():
                    where = _json_path([f"cells[{i}]", "metadata", "debrief", *err["loc"]])
                    self.error(name, where, _pydantic_message(err))
                ok = False
                continue
            want = "markdown" if meta.role == "explain" else "code"
            if cell.cell_type != want:
                self.error(name, f"cells[{i}]", f"role {meta.role!r} needs a {want} cell, "
                           f"but this is a {cell.cell_type} cell")
                ok = False
                continue
            cells.append((i, cell, meta))
        if not ok:
            return None

        self.check_dissection(cells)
        return cells

    def load_exercises(self) -> list[tuple[str, Exercise | None]]:
        root = self.bundle / "exercises"
        if not root.is_dir():
            self.error("exercises", None, "required folder is missing")
            return []
        folders = sorted(
            p for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "__"))
        )
        if not MIN_EXERCISES <= len(folders) <= MAX_EXERCISES:
            self.error("exercises", None, f"has {len(folders)} exercise folders; "
                       f"need {MIN_EXERCISES} to {MAX_EXERCISES}")

        loaded = []
        for folder in folders:
            loaded.append((folder.name, self.load_exercise(folder)))
        return loaded

    def load_exercise(self, folder: Path) -> Exercise | None:
        """Load one exercise and check its files statically. None if it can't be run."""
        rel = f"exercises/{folder.name}"
        missing = [
            f for f in ("exercise.json", "stub.py", "solution.py", "test_exercise.py")
            if not (folder / f).is_file()
        ]
        for f in missing:
            self.error(f"{rel}/{f}", None, "required file is missing")

        exercise = self.load_json(f"{rel}/exercise.json", Exercise, folder / "exercise.json")
        if exercise is not None and exercise.id != folder.name:
            self.error(f"{rel}/exercise.json", "id", f"is {exercise.id!r} but the folder is "
                       f"named {folder.name!r}; they must match")

        trees: dict[str, ast.Module] = {}
        for f in ("stub.py", "solution.py", "test_exercise.py"):
            if (folder / f).is_file():
                try:
                    trees[f] = ast.parse((folder / f).read_text(encoding="utf-8"), filename=f)
                except SyntaxError as exc:
                    self.error(f"{rel}/{f}", str(exc.lineno), f"syntax error: {exc.msg}")
        if exercise is None or missing or len(trees) < 3:
            return None

        ok = True
        if not _imports_candidate(trees["test_exercise.py"]):
            self.error(f"{rel}/test_exercise.py", None, "never imports from 'candidate'; use "
                       f"'from candidate import {exercise.function}' so the tests run against "
                       "the learner's code")
            ok = False
        fns = {f: _top_level_function(trees[f], exercise.function) for f in ("stub.py", "solution.py")}
        for f, fn in fns.items():
            if fn is None:
                self.error(f"{rel}/{f}", None, f"defines no top-level function "
                           f"{exercise.function!r} (named in exercise.json)")
                ok = False
        stub, solution = fns["stub.py"], fns["solution.py"]
        if stub and solution and _signature(stub) != _signature(solution):
            self.error(f"{rel}/stub.py", str(stub.lineno), f"signature of {exercise.function} "
                       f"differs from solution.py: {_signature(stub)} vs {_signature(solution)}")
        return exercise if ok else None

    # --- static checks -------------------------------------------------------

    def check_markdown(self, name: str) -> None:
        path = self.bundle / name
        if not path.is_file():
            return
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            self.error(name, None, "is empty" + (
                "; if no architectural decisions were made, say so in one line"
                if name == "decisions.md" else ""))
            return
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in _DIAGRAM_REF.finditer(line):
                ref = match[1] or match[2]
                if not (self.bundle / ref).is_file():
                    self.error(name, str(lineno), f"references {ref}, which does not exist")
        self.check_mermaid(name, text)

    def check_mermaid(self, name: str, text: str) -> None:
        mmdc = shutil.which("mmdc")
        if mmdc is None:
            return
        with tempfile.TemporaryDirectory(prefix="debrief-mmd-") as tmp:
            for match in _MERMAID.finditer(text):
                lineno = text.count("\n", 0, match.start()) + 1
                src, out = Path(tmp) / "block.mmd", Path(tmp) / "block.svg"
                src.write_text(match[1], encoding="utf-8")
                try:
                    proc = subprocess.run([mmdc, "-q", "-i", str(src), "-o", str(out)],
                                          capture_output=True, text=True, timeout=60)
                except (OSError, subprocess.TimeoutExpired) as exc:
                    self.warn(name, str(lineno), f"could not check Mermaid block: {exc}")
                    return
                if proc.returncode != 0:
                    detail = (proc.stderr or proc.stdout).strip().splitlines()[:3]
                    self.warn(name, str(lineno), "Mermaid block does not parse:\n"
                              + _indent("\n".join(detail)))

    def check_dissection(self, cells: list[tuple[int, Any, CellMeta]]) -> None:
        """Each function cell defines its function and is followed by a demo cell."""
        for pos, (i, cell, meta) in enumerate(cells):
            if meta.role != "function":
                continue
            try:
                tree = ast.parse(cell.source)
            except SyntaxError:
                tree = None  # IPython syntax, or an error that execution will report
            if tree is not None and _top_level_function(tree, meta.function or "") is None:
                self.error("notebook.ipynb", f"cells[{i}]", f"function cell for "
                           f"{meta.function!r} has no top-level 'def {meta.function}'")
            demo_follows = False
            for _, _, later in cells[pos + 1:]:
                if later.role == "function":
                    break
                demo_follows = demo_follows or later.role == "demo"
            if not demo_follows:
                self.error("notebook.ipynb", f"cells[{i}]", f"function cell for "
                           f"{meta.function!r} has no demo cell after it; add a demo cell that "
                           "calls it before the next function cell")

    def check_fixtures(self) -> None:
        root = self.bundle / "fixtures"
        if not root.is_dir():
            return
        files = [p for p in root.rglob("*") if p.is_file()]
        total = sum(p.stat().st_size for p in files)
        if total > MAX_FIXTURES_BYTES:
            largest = sorted(files, key=lambda p: p.stat().st_size, reverse=True)[:3]
            names = ", ".join(
                f"{p.relative_to(self.bundle).as_posix()} ({p.stat().st_size / 1e6:.1f} MB)"
                for p in largest
            )
            self.error("fixtures", None, f"is {total / 1e6:.1f} MB; the limit is "
                       f"{MAX_FIXTURES_BYTES / 1e6:.0f} MB. Largest: {names}. Generate smaller "
                       "samples with code")

    def check_data_slots(self, lesson: Lesson) -> None:
        for i, slot in enumerate(lesson.data_slots):
            if slot.kind not in ("file", "dir") or slot.default is None:
                continue
            assert isinstance(slot.default, str)
            path = (self.bundle / slot.default).resolve()
            where = f"data_slots[{i}].default"
            if not path.is_relative_to(self.bundle):
                self.error("lesson.json", where, f"{slot.default} points outside the bundle")
            elif slot.kind == "file" and not path.is_file():
                self.error("lesson.json", where, f"{slot.default} is not a file in the bundle")
            elif slot.kind == "dir" and not path.is_dir():
                self.error("lesson.json", where, f"{slot.default} is not a folder in the bundle")

    def check_source_refs(
        self,
        lesson: Lesson,
        quiz: Quiz | None,
        cells: list[tuple[int, Any, CellMeta]] | None,
        exercises: list[tuple[str, Exercise | None]],
    ) -> None:
        listed = {f.path for f in lesson.source.files}
        refs: list[tuple[str, str, str]] = []
        if quiz is not None:
            refs += [("quiz.json", f"questions[{i}].source_ref", q.source_ref)
                     for i, q in enumerate(quiz.questions) if q.source_ref]
        if cells is not None:
            refs += [("notebook.ipynb", f"cells[{i}].metadata.debrief.source_ref", m.source_ref)
                     for i, _, m in cells if m.source_ref]
        refs += [(f"exercises/{folder}/exercise.json", "source_ref", ex.source_ref)
                 for folder, ex in exercises if ex is not None]
        for file, where, ref in refs:
            path = source_ref_path(ref)
            if path not in listed:
                self.error(file, where, f"{ref} points to {path}, which is not in lesson.json "
                           "source.files")

    # --- execution -----------------------------------------------------------

    def check_environment(self, lesson: Lesson) -> bool:
        env = lesson.environment
        report = check_interpreter(env.python)
        ok = True
        if report.error:
            self.error("lesson.json", "environment.python", report.error)
            ok = False
        elif report.missing:
            self.error("lesson.json", "environment.python", f"{env.python} lacks "
                       f"{', '.join(report.missing)}. Fix: {report.fix_command()}")
            ok = False
        cwd = Path(env.cwd)
        if not cwd.is_dir():
            self.error("lesson.json", "environment.cwd", f"{env.cwd} is not a directory")
            return False
        for i, entry in enumerate(env.extra_sys_path):
            if not (cwd / entry).is_dir():
                self.error("lesson.json", f"environment.extra_sys_path[{i}]",
                           f"{cwd / entry} is not a directory")
                ok = False
        return ok

    async def run_notebook(self, lesson: Lesson, cells: list[tuple[int, Any, CellMeta]]) -> None:
        kernel = LessonKernel(KernelConfig.for_lesson(lesson, self.bundle))
        try:
            await kernel.start()
        except KernelError as exc:
            self.error("lesson.json", "environment.python", str(exc))
            return
        try:
            code_cells = [(i, cell) for i, cell, _ in cells if cell.cell_type == "code"]
            for pos, (i, cell) in enumerate(code_cells):
                started = time.monotonic()
                events = await kernel.run(cell.source, timeout=CELL_TIMEOUT)
                elapsed = time.monotonic() - started
                if events[-1]["status"] != "ok":
                    self.cell_failed(i, events, skipped=len(code_cells) - pos - 1)
                    return
                if elapsed > SLOW_CELL_SECONDS:
                    self.warn("notebook.ipynb", f"cells[{i}]", f"took {elapsed:.0f}s to run; "
                              "keep cells fast by using smaller fixtures")
        finally:
            await kernel.shutdown()

    def cell_failed(self, index: int, events: list[dict[str, Any]], skipped: int) -> None:
        errors = [e for e in events if e["type"] == "error"]
        if errors:
            first = errors[0]
            message = f"raised {first['ename']}: {first['evalue']}"
            traceback = _ANSI.sub("", "\n".join(first["traceback"])).strip().splitlines()
            if len(traceback) > 1:
                message += "\n" + _indent("\n".join(traceback[-_TRACEBACK_LINES:]))
        else:
            message = f"failed with status {events[-1]['status']!r}"
        if skipped:
            message += f"\n    ({skipped} later code cell(s) were not run)"
        self.error("notebook.ipynb", f"cells[{index}]", message)

    def run_exercise(self, lesson: Lesson, folder: str, exercise: Exercise) -> None:
        env = lesson.environment
        root = self.bundle / "exercises" / folder
        tests = root / "test_exercise.py"
        rel = f"exercises/{folder}"

        def run(name: str):
            code = (root / name).read_text(encoding="utf-8")
            return run_tests(code, tests, env.python, Path(env.cwd), env.extra_sys_path)

        solution = run("solution.py")
        if solution.error:
            self.error(f"{rel}/test_exercise.py", None,
                       f"could not run against solution.py: {solution.error}")
        for result in solution.results:
            if result.status != "passed":
                self.error(f"{rel}/test_exercise.py", result.name,
                           f"{result.status} against solution.py:\n{_indent(result.message)}")

        stub = run("stub.py")
        if stub.error:
            self.error(f"{rel}/stub.py", None, f"tests could not run against stub.py: {stub.error}")
        elif stub.passed:
            self.error(f"{rel}/test_exercise.py", None, "every test passes against stub.py, so "
                       f"the tests don't check the implementation; assert on what "
                       f"{exercise.function} returns")
        else:
            for result in stub.results:
                if result.status == "passed":
                    self.warn(f"{rel}/test_exercise.py", result.name,
                              "passes against stub.py, so it doesn't check the implementation")
