"""The ``debrief`` command line (spec §7)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from debrief.bundle.models import Lesson
from debrief.bundle.validator import validate_bundle
from debrief.environment import check_interpreter, find_project_python
from debrief.store import LessonExistsError, LessonStore

DEFAULT_PORT = 8765  # debrief serve (spec §7)

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def main() -> None:
    """Turn what your coding agent just built into an interactive lesson."""


@app.command()
def validate(
    bundle: Annotated[Path, typer.Argument(help="The lesson bundle folder to check.")],
) -> None:
    """Check a lesson bundle: schemas, references, notebook execution and exercise tests.

    Prints one issue per line as file:location: message. Exit code 0 means valid.
    """
    if not _check(bundle):
        raise typer.Exit(1)


@app.command()
def publish(
    bundle: Annotated[Path, typer.Argument(help="The lesson bundle folder to publish.")],
    force: Annotated[
        bool, typer.Option("--force", help="Replace a published lesson with the same id.")
    ] = False,
) -> None:
    """Validate a lesson bundle, copy it into the lesson store and index it."""
    if not _check(bundle):
        typer.echo("Not published: fix the errors above and publish again.")
        raise typer.Exit(1)

    lesson = Lesson.model_validate_json((bundle / "lesson.json").read_bytes())
    store = LessonStore.default()
    try:
        target = store.publish(bundle, lesson, force=force)
    except LessonExistsError as exc:
        typer.echo(f'lesson.json:id: lesson {exc.lesson_id!r} is already published in '
                   f'{store.lessons_dir}. Set "id" to "{exc.free_id}" and publish again, '
                   "or pass --force to replace it.")
        raise typer.Exit(1) from None

    typer.echo(f"\nPublished {lesson.id} to {target}")
    typer.echo(f"Lesson URL: {lesson_url(lesson.id)}")


@app.command()
def serve(
    port: Annotated[int, typer.Option(help="Port on 127.0.0.1 to serve the hub on.")] = DEFAULT_PORT,
    open_browser: Annotated[
        bool, typer.Option("--open", help="Open the hub in the browser once it's up.")
    ] = False,
) -> None:
    """Start the hub on 127.0.0.1 (the only interface it binds to)."""
    import threading
    import webbrowser

    import uvicorn

    from debrief.server.app import create_app

    url = f"http://127.0.0.1:{port}/"
    if open_browser:
        threading.Timer(1.0, webbrowser.open, (url,)).start()
    typer.echo(f"debrief hub: {url}")
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")


def lesson_url(lesson_id: str) -> str:
    return f"http://127.0.0.1:{DEFAULT_PORT}/lessons/{lesson_id}"


def _check(bundle: Path) -> bool:
    """Validate ``bundle`` and print the report. True if it's valid."""
    report = validate_bundle(bundle)
    for issue in report.issues:
        typer.echo(str(issue))

    n_errors, n_warnings = len(report.errors), len(report.warnings)
    warnings = f"{n_warnings} warning{'s' * (n_warnings != 1)}"
    if report.ok:
        gap = "\n" if report.issues else ""
        typer.echo(f"{gap}{bundle}: valid" + (f" ({warnings})" if n_warnings else ""))
        return True
    if not report.executed:
        typer.echo("\nThe notebook and exercise tests were not run: lesson.json or its "
                   "environment has errors. Fix those first.")
    typer.echo(f"\n{bundle}: {n_errors} error{'s' * (n_errors != 1)}, {warnings}")
    return False


@app.command()
def doctor(
    python: Annotated[
        Path | None,
        typer.Option(
            help="Project interpreter to check. Default: .venv or venv in the current "
            "directory, else $VIRTUAL_ENV."
        ),
    ] = None,
) -> None:
    """Check that the project interpreter can run lessons (ipykernel) and exercises (pytest)."""
    if python is None:
        python = find_project_python()
        if python is None:
            typer.echo(
                "error: no project interpreter found in ./.venv, ./venv or $VIRTUAL_ENV. "
                "Pass one with --python PATH.",
                err=True,
            )
            raise typer.Exit(2)

    report = check_interpreter(python)
    if report.error:
        typer.echo(f"error: {report.error}", err=True)
        raise typer.Exit(1)

    typer.echo(f"python     {report.python} ({report.version})")
    for module, present in report.found.items():
        typer.echo(f"{module:<10} {'ok' if present else 'MISSING'}")

    if not report.ok:
        typer.echo(f"\nFix: {report.fix_command()}")
        raise typer.Exit(1)
    typer.echo("\nReady: lessons can run in this interpreter.")
