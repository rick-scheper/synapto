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

    if not _port_in_use(port):
        return  # nothing is running
    url = f"http://127.0.0.1:{port}/api/shutdown"
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="POST"), timeout=5).close()
    except urllib.error.HTTPError as exc:
        typer.echo(f"error: whatever is on port {port} can't be stopped with --reload (HTTP {exc.code}). "
                   "A hub started before --reload existed has to be stopped by hand (Ctrl+C).", err=True)
        raise typer.Exit(1) from None
    except (urllib.error.URLError, OSError) as exc:
        typer.echo(f"error: port {port} is in use, but no hub answered there ({exc}). "
                   "Stop whatever is using it, or pick another --port.", err=True)
        raise typer.Exit(1) from None
    deadline = time.monotonic() + timeout
    while _port_in_use(port):
        if time.monotonic() > deadline:
            typer.echo(f"error: the hub on port {port} didn't stop within {timeout:.0f}s.", err=True)
            raise typer.Exit(1)
        time.sleep(0.1)
    typer.echo(f"Stopped the hub on port {port}.")


def _port_in_use(port: int) -> bool:
    """Whether something listens on 127.0.0.1:``port``.

    Tries to bind rather than connect: on some setups (WSL among them) a connect to
    a closed port hangs until the TCP timeout instead of being refused.
    """
    import os
    import socket

    with socket.socket() as sock:
        if os.name != "nt":
            # Like uvicorn, so a just-stopped hub's TIME_WAIT connections don't count.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return True
        return False


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


decision_app = typer.Typer(no_args_is_help=True, help="Review a decision lesson's choice (used by /decide review).")
app.add_typer(decision_app, name="decision")


def _decision_lesson(store: LessonStore, lesson_id: str) -> Lesson:
    if not store.exists(lesson_id):
        typer.echo(f"error: no lesson {lesson_id!r} in {store.lessons_dir}", err=True)
        raise typer.Exit(1)
    lesson = store.load(lesson_id)
    if lesson.kind != "decision":
        typer.echo(f"error: lesson {lesson_id!r} is not a decision lesson", err=True)
        raise typer.Exit(1)
    return lesson


@decision_app.command("show")
def decision_show(
    lesson_id: Annotated[str, typer.Argument(metavar="ID", help="The decision lesson's id.")],
) -> None:
    """Print the question, options, recommendation, the developer's choice and any verdict as JSON."""
    from synapto.server.decide import decision_state

    store = LessonStore.default()
    state = decision_state(store, _decision_lesson(store, lesson_id), reveal=True)
    typer.echo(state.model_dump_json(indent=2))


@decision_app.command("verdict")
def decision_verdict(
    lesson_id: Annotated[str, typer.Argument(metavar="ID", help="The decision lesson's id.")],
    file: Annotated[Path, typer.Argument(help="The verdict JSON: final_option, challenges, opinion.")],
    adr: Annotated[
        str | None, typer.Option(help="Path, in the project, of the ADR that records the decision.")
    ] = None,
) -> None:
    """Store the verdict of a review, replacing an earlier one. The hub then shows it."""
    from pydantic import ValidationError

    from synapto.bundle.models import Verdict
    from synapto.bundle.validator import json_path, pydantic_message
    from synapto.server.decide import DecisionError, record_verdict

    store = LessonStore.default()
    lesson = _decision_lesson(store, lesson_id)
    try:
        verdict = Verdict.model_validate_json(file.read_bytes())
    except OSError as exc:
        typer.echo(f"error: can't read {file}: {exc}", err=True)
        raise typer.Exit(1) from None
    except ValidationError as exc:
        for err in exc.errors():
            where = json_path(err["loc"])
            typer.echo(f"{file}:{where}: {pydantic_message(err)}" if where else f"{file}: {pydantic_message(err)}")
        raise typer.Exit(1) from None
    try:
        done = record_verdict(store, lesson, verdict, adr)
    except DecisionError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from None
    agreement = "matches" if done.agrees else "differs from"
    typer.echo(f"Stored the verdict for {lesson_id}: {verdict.final_option} {agreement} the recommendation.")
    typer.echo(f"Lesson URL: {lesson_url(lesson_id)}/options")
