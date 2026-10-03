"""M0: the hand-written example bundle validates, and broken variants fail with clear errors.

The example lives in ``tests/example``: ``project/`` stands in for a developer's
repo (package ``gridsnap``) and ``bundle/`` is a lesson about it. Each test
copies both to a temp dir (the ``bundle`` fixture in conftest) and points
``lesson.json`` at the copy and at the ``project_python`` venv.
"""

import json
import os
import shutil
import stat
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from debrief.bundle.validator import validate_bundle
from debrief.cli import app


def edit_json(path: Path, change: Callable[[dict], object]) -> None:
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data, indent=1))


def edit_text(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    assert old in text, f"{old!r} not in {path}"
    path.write_text(text.replace(old, new))


def messages(bundle: Path, execute: bool = False) -> list[str]:
    return [str(issue) for issue in validate_bundle(bundle, execute=execute).issues]


def test_example_bundle_is_valid(bundle: Path) -> None:
    result = CliRunner().invoke(app, ["validate", str(bundle)])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == f"{bundle}: valid"


# --- broken variants caught without running code ---------------------------------


def _set(path: str, value: object) -> Callable[[dict], None]:
    """A JSON edit that sets ``value`` at a dotted path, e.g. ``questions.0.correct``."""

    def change(data: dict) -> None:
        *parents, last = path.split(".")
        for key in parents:
            data = data[int(key)] if isinstance(data, list) else data[key]
        if isinstance(data, list):
            data[int(last)] = value
        else:
            data[last] = value

    return change


def _notebook(change: Callable[[list], object]) -> Callable[[Path], None]:
    return lambda b: edit_json(b / "notebook.ipynb", lambda nb: change(nb["cells"]))


EX1 = "exercises/01-voxel-key"

STATIC_VARIANTS: dict[str, tuple[Callable[[Path], object], str]] = {
    "missing quiz": (
        lambda b: (b / "quiz.json").unlink(),
        "quiz.json: required file is missing",
    ),
    "invalid json": (
        lambda b: (b / "lesson.json").write_text('{"id": '),
        "lesson.json: Invalid JSON",
    ),
    "bad lesson id": (
        lambda b: edit_json(b / "lesson.json", _set("id", "Voxel Downsampling")),
        'lesson.json:id: String should match pattern',
    ),
    "unknown field": (
        lambda b: edit_json(b / "lesson.json", _set("titel", "typo")),
        "lesson.json:titel: unknown field; remove it or fix its spelling",
    ),
    "missing field": (
        lambda b: edit_json(b / "lesson.json", lambda d: d.pop("summary")),
        "lesson.json:summary: required field is missing",
    ),
    "relative interpreter": (
        lambda b: edit_json(b / "lesson.json", _set("environment.python", ".venv/bin/python")),
        "lesson.json:environment.python: must be an absolute path, got '.venv/bin/python'",
    ),
    "naive timestamp": (
        lambda b: edit_json(b / "lesson.json", _set("created_at", "2026-10-03T11:20:00")),
        "lesson.json:created_at: Input should have timezone info",
    ),
    "slot default outside bundle": (
        lambda b: edit_json(b / "lesson.json", _set("data_slots.0.default", "../points.xyz")),
        "lesson.json:data_slots[0]: default of a file slot must be a path inside the bundle",
    ),
    "slot default missing": (
        lambda b: (b / "fixtures" / "points.xyz").unlink(),
        "lesson.json:data_slots[0].default: fixtures/points.xyz is not a file in the bundle",
    ),
    "number slot with string default": (
        lambda b: edit_json(b / "lesson.json", _set("data_slots.1.default", "1.0")),
        "lesson.json:data_slots[1]: default of a number slot must be a JSON number, got '1.0'",
    ),
    "quiz answer not an option": (
        lambda b: edit_json(b / "quiz.json", _set("questions.0.correct", "z")),
        "quiz.json:questions[0]: correct 'z' is not one of the option ids (a, b, c, d)",
    ),
    "quiz too few options": (
        lambda b: edit_json(b / "quiz.json", lambda d: d["questions"][1]["options"].pop()),
        "quiz.json:questions[1]: needs at least 3 options, has 2",
    ),
    "quiz empty explanation": (
        lambda b: edit_json(b / "quiz.json", _set("questions.2.explanation", "  ")),
        "quiz.json:questions[2].explanation: must not be empty",
    ),
    "quiz too few questions": (
        lambda b: edit_json(b / "quiz.json", lambda d: d["questions"].pop()),
        "quiz.json:questions: List should have at least 5 items",
    ),
    "malformed source_ref": (
        lambda b: edit_json(b / "quiz.json", _set("questions.0.source_ref", "snap.py line 33")),
        "quiz.json:questions[0].source_ref: must look like 'path/to/file.py:12'",
    ),
    "source_ref to unlisted file": (
        lambda b: edit_json(b / "quiz.json", _set("questions.0.source_ref", "src/gridsnap/io.py:3")),
        "quiz.json:questions[0].source_ref: src/gridsnap/io.py:3 points to src/gridsnap/io.py, "
        "which is not in lesson.json source.files",
    ),
    "missing diagram": (
        lambda b: (b / "diagrams" / "grid.svg").unlink(),
        "references diagrams/grid.svg, which does not exist",
    ),
    "empty decisions": (
        lambda b: (b / "decisions.md").write_text("\n"),
        "decisions.md: is empty; if no architectural decisions were made, say so in one line",
    ),
    "unreadable notebook": (
        lambda b: (b / "notebook.ipynb").write_text("not json"),
        "notebook.ipynb: not a readable notebook",
    ),
    "notebook schema": (
        _notebook(lambda cells: cells[1].pop("outputs")),
        "notebook.ipynb:cells[1]: does not match the nbformat 4 schema",
    ),
    "cell without debrief metadata": (
        _notebook(lambda cells: cells[1]["metadata"].clear()),
        "notebook.ipynb:cells[1]: metadata.debrief is missing",
    ),
    "unknown role": (
        _notebook(lambda cells: cells[1]["metadata"]["debrief"].update(role="imports")),
        "notebook.ipynb:cells[1].metadata.debrief.role: Input should be 'setup', 'function', "
        "'demo' or 'explain'",
    ),
    "function cell without function": (
        _notebook(lambda cells: cells[3]["metadata"]["debrief"].pop("function")),
        "notebook.ipynb:cells[3].metadata.debrief: a function cell needs both 'function' and "
        "'source_ref'",
    ),
    "explain role on code cell": (
        _notebook(lambda cells: cells[4]["metadata"]["debrief"].update(role="explain")),
        "notebook.ipynb:cells[4]: role 'explain' needs a markdown cell, but this is a code cell",
    ),
    "function cell without demo": (
        _notebook(lambda cells: cells.pop(4)),
        "notebook.ipynb:cells[3]: function cell for 'voxel_key' has no demo cell after it",
    ),
    "function cell names the wrong function": (
        _notebook(lambda cells: cells[3]["metadata"]["debrief"].update(function="voxel_index")),
        "notebook.ipynb:cells[3]: function cell for 'voxel_index' has no top-level "
        "'def voxel_index'",
    ),
    "fixtures too large": (
        lambda b: (b / "fixtures" / "big.bin").write_bytes(b"\0" * 6_000_000),
        "fixtures: is 6.0 MB; the limit is 5 MB. Largest: fixtures/big.bin (6.0 MB)",
    ),
    "no exercises": (
        lambda b: [shutil.rmtree(p) for p in (b / "exercises").iterdir()],
        "exercises: has 0 exercise folders; need 1 to 3",
    ),
    "exercise id differs from folder": (
        lambda b: edit_json(b / EX1 / "exercise.json", _set("id", "01-voxel-index")),
        f"{EX1}/exercise.json:id: is '01-voxel-index' but the folder is named '01-voxel-key'",
    ),
    "exercise missing stub": (
        lambda b: (b / EX1 / "stub.py").unlink(),
        f"{EX1}/stub.py: required file is missing",
    ),
    "stub syntax error": (
        lambda b: edit_text(b / EX1 / "stub.py", "raise NotImplementedError", "raise NotImplementedError("),
        f"{EX1}/stub.py:10: syntax error",
    ),
    "stub missing function": (
        lambda b: edit_text(b / EX1 / "stub.py", "def voxel_key(", "def voxel_index("),
        f"{EX1}/stub.py: defines no top-level function 'voxel_key' (named in exercise.json)",
    ),
    "stub signature differs": (
        lambda b: edit_text(b / EX1 / "stub.py", "size: float)", "size: int)"),
        f"{EX1}/stub.py:8: signature of voxel_key differs from solution.py: "
        "(point: Point, size: int) -> VoxelKey vs (point: Point, size: float) -> VoxelKey",
    ),
    "tests don't import candidate": (
        lambda b: edit_text(b / EX1 / "test_exercise.py", "from candidate import", "from solution import"),
        f"{EX1}/test_exercise.py: never imports from 'candidate'; use 'from candidate import voxel_key'",
    ),
}


@pytest.mark.parametrize("variant", STATIC_VARIANTS, ids=list(STATIC_VARIANTS))
def test_static_variant_fails(bundle: Path, variant: str) -> None:
    break_bundle, expected = STATIC_VARIANTS[variant]
    break_bundle(bundle)
    report = validate_bundle(bundle, execute=False)
    assert not report.ok
    found = [str(i) for i in report.errors]
    assert any(expected in m for m in found), "\n".join(found)


def test_static_checks_pass_on_example(bundle: Path) -> None:
    assert messages(bundle) == []


def test_not_a_directory(tmp_path: Path) -> None:
    report = validate_bundle(tmp_path / "nope")
    assert [str(i) for i in report.issues] == [f"{tmp_path / 'nope'}: bundle is not a directory"]


def test_mermaid_parse_errors_are_warnings(bundle: Path, tmp_path: Path, monkeypatch) -> None:
    # A stand-in for mmdc that rejects any diagram containing BROKEN.
    fake = tmp_path / "bin" / "mmdc"
    fake.parent.mkdir()
    fake.write_text('#!/bin/sh\nwhile [ $# -gt 0 ]; do [ "$1" = -i ] && f=$2; shift; done\n'
                    'grep -q BROKEN "$f" && { echo "Parse error on line 2" >&2; exit 1; }\nexit 0\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{fake.parent}{os.pathsep}{os.environ['PATH']}")

    assert messages(bundle) == []
    edit_text(bundle / "explanation.md", "flowchart LR", "flowchart LR\n    BROKEN -->")
    report = validate_bundle(bundle, execute=False)
    assert report.ok
    assert [str(w) for w in report.warnings] == [
        "explanation.md:21: warning: Mermaid block does not parse:\n    Parse error on line 2"
    ]


# --- broken variants caught by running code --------------------------------------


def test_execution_failures_are_all_reported(bundle: Path) -> None:
    # A demo cell that raises, a solution that fails a test, and tests that pass on the stub.
    _notebook(lambda cells: cells[4].update(source="print('before')\n1 / 0"))(bundle)
    edit_text(bundle / EX1 / "solution.py", "math.floor(x / size)", "int(x / size)")
    ex2 = bundle / "exercises" / "02-downsample"
    (ex2 / "test_exercise.py").write_text(
        "from candidate import downsample\n\n\ndef test_exists():\n    assert callable(downsample)\n"
    )

    found = messages(bundle, execute=True)
    assert len(found) == 3, "\n".join(found)
    cell, solution, stub = found
    assert cell.startswith("notebook.ipynb:cells[4]: raised ZeroDivisionError: division by zero\n")
    assert "----> 2 1 / 0" in cell and "(2 later code cell(s) were not run)" in cell
    assert solution.startswith(
        f"{EX1}/test_exercise.py:test_negative_coordinates_floor_toward_minus_infinity: "
        "failed against solution.py:\n"
    )
    assert "assert (0, -2, 0) == (-1, -2, 0)" in solution
    assert stub == (
        "exercises/02-downsample/test_exercise.py: every test passes against stub.py, so the "
        "tests don't check the implementation; assert on what downsample returns"
    )


def test_a_test_that_passes_on_the_stub_is_a_warning(bundle: Path) -> None:
    with (bundle / EX1 / "test_exercise.py").open("a") as f:
        f.write("\n\ndef test_is_callable():\n    assert callable(voxel_key)\n")
    report = validate_bundle(bundle)
    assert report.ok
    assert [str(w) for w in report.warnings] == [
        f"{EX1}/test_exercise.py:test_is_callable: warning: passes against stub.py, so it "
        "doesn't check the implementation"
    ]


def test_stub_that_does_not_import(bundle: Path) -> None:
    edit_text(bundle / EX1 / "stub.py", "import math", "import mathh")
    found = messages(bundle, execute=True)
    assert len(found) == 1, found
    assert found[0].startswith(f"{EX1}/stub.py: tests could not run against stub.py: pytest "
                               "exited with code 2:")
    assert "No module named 'mathh'" in found[0]


def test_interpreter_without_ipykernel_stops_execution(bundle: Path, bare_python: Path) -> None:
    edit_json(bundle / "lesson.json", _set("environment.python", str(bare_python)))
    result = CliRunner().invoke(app, ["validate", str(bundle)])
    assert result.exit_code == 1
    lines = result.output.strip().splitlines()
    assert lines[0].startswith(f"lesson.json:environment.python: {bare_python} lacks ipykernel, "
                               "pytest. Fix: ")
    assert "were not run" in lines[-3]
    assert lines[-1] == f"{bundle}: 1 error, 0 warnings"


def test_missing_project_dir(bundle: Path, tmp_path: Path) -> None:
    edit_json(bundle / "lesson.json", _set("environment.cwd", str(tmp_path / "gone")))
    assert messages(bundle, execute=True) == [
        f"lesson.json:environment.cwd: {tmp_path / 'gone'} is not a directory"
    ]
