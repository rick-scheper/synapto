"""The ``synapto`` command line (spec §7)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from synapto.bundle.models import Lesson
from synapto.bundle.validator import validate_bundle
from synapto.environment import check_interpreter, find_project_python
from synapto.store import LessonExistsError, LessonStore

DEFAULT_PORT = 8765  # synapto serve (spec §7)

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
def remove(
    lesson_id: Annotated[str, typer.Argument(metavar="ID", help="The id of the lesson to delete.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Don't ask for confirmation.")] = False,
) -> None:
    """Delete a published lesson and all progress recorded for it."""
    store = LessonStore.default()
    if not store.exists(lesson_id):
        typer.echo(f"error: no lesson {lesson_id!r} in {store.lessons_dir}", err=True)
        raise typer.Exit(1)
    if not yes:
        typer.confirm(f"Delete lesson {lesson_id!r} and its progress? This can't be undone", abort=True)
    store.remove(lesson_id)
    typer.echo(f"Removed {lesson_id}")


@app.command()
def serve(
    port: Annotated[int, typer.Option(help="Port on 127.0.0.1 to serve the hub on.")] = DEFAULT_PORT,
    open_browser: Annotated[
        bool, typer.Option("--open", help="Open the hub in the browser once it's up.")
    ] = False,
    reload: Annotated[
        bool, typer.Option("--reload", help="Stop the hub already running on this port, then start a new one.")
    ] = False,
) -> None:
    """Start the hub on 127.0.0.1 (the only interface it binds to)."""
    import threading
    import webbrowser

    import uvicorn

    from synapto.server.app import create_app

    if reload:
        stop_running_hub(port)
    elif _port_in_use(port):
        typer.echo(f"error: port {port} is in use, probably by a running hub. "
                   "Restart it with --reload, or pick another --port.", err=True)
        raise typer.Exit(1)

    def stop() -> None:
        server.should_exit = True

    server = uvicorn.Server(uvicorn.Config(create_app(stop=stop), host="127.0.0.1", port=port,
                                           log_level="warning"))
    url = f"http://127.0.0.1:{port}/"
    if open_browser:
        threading.Timer(1.0, webbrowser.open, (url,)).start()
    typer.echo(f"Synapto hub: {url}")
    server.run()


def stop_running_hub(port: int, timeout: float = 15.0) -> None:
    """Ask the hub on ``port`` to shut down and wait until the port is free.

    Does nothing if nothing is listening there.
    """
    import time
    import urllib.error
    import urllib.request

    url = f"http://127.0.0.1:{port}/api/shutdown"
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="POST"), timeout=5).close()
    except urllib.error.HTTPError as exc:
        typer.echo(f"error: whatever is on port {port} can't be stopped with --reload (HTTP {exc.code}). "
                   "A hub started before --reload existed has to be stopped by hand (Ctrl+C).", err=True)
        raise typer.Exit(1) from None
    except (urllib.error.URLError, OSError):
        return  # nothing is running
    deadline = time.monotonic() + timeout
    while _port_in_use(port):
        if time.monotonic() > deadline:
            typer.echo(f"error: the hub on port {port} didn't stop within {timeout:.0f}s.", err=True)
            raise typer.Exit(1)
        time.sleep(0.1)
    typer.echo(f"Stopped the hub on port {port}.")


def _port_in_use(port: int) -> bool:
    import socket

    with socket.socket() as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


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
