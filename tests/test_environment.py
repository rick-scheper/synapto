from pathlib import Path

from typer.testing import CliRunner

from debrief.cli import app
from debrief.environment import check_interpreter, find_project_python, venv_root


def test_project_interpreter_is_ready(project_python: Path) -> None:
    report = check_interpreter(project_python)
    assert report.ok
    assert report.found == {"ipykernel": True, "pytest": True}
    assert report.version
    assert report.fix_command() is None


def test_missing_modules_are_reported_with_a_fix(bare_python: Path) -> None:
    report = check_interpreter(bare_python)
    assert not report.ok
    assert report.missing == ("ipykernel", "pytest")
    fix = report.fix_command()
    assert fix is not None and str(bare_python) in fix and "ipykernel pytest" in fix


def test_nonexistent_interpreter(tmp_path: Path) -> None:
    report = check_interpreter(tmp_path / "nope" / "python")
    assert not report.exists and not report.ok
    assert "does not exist" in (report.error or "")


def test_venv_symlink_is_not_resolved(project_python: Path) -> None:
    # Resolving bin/python would point at the base interpreter and lose the venv.
    report = check_interpreter(project_python)
    assert report.python == project_python
    assert venv_root(report.python) == project_python.parent.parent


def test_find_project_python(project_python: Path, monkeypatch) -> None:
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    project_dir = project_python.parent.parent.parent
    assert find_project_python(project_dir) == project_python
    assert find_project_python(project_dir / "elsewhere") is None


def test_doctor_cli(project_python: Path, bare_python: Path) -> None:
    runner = CliRunner()
    ok = runner.invoke(app, ["doctor", "--python", str(project_python)])
    assert ok.exit_code == 0, ok.output
    assert "Ready" in ok.output

    bad = runner.invoke(app, ["doctor", "--python", str(bare_python)])
    assert bad.exit_code == 1
    assert "ipykernel  MISSING" in bad.output
    assert "Fix:" in bad.output
