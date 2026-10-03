"""The ``debrief`` command line (spec §7)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from debrief.environment import check_interpreter, find_project_python

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def main() -> None:
    """Turn what your coding agent just built into an interactive lesson."""


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
