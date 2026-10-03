"""Inspect the project interpreter that lesson code runs in (ADR-0001, ADR-0004).

debrief never imports lesson code itself. It runs it in the project's own venv,
so that interpreter must exist and have ``ipykernel`` and ``pytest`` installed.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED_MODULES: tuple[str, ...] = ("ipykernel", "pytest")

_PROBE = """
import importlib.util, json, platform, sys
print(json.dumps({
    "version": platform.python_version(),
    "found": {m: importlib.util.find_spec(m) is not None for m in sys.argv[1:]},
}))
"""


@dataclass(frozen=True)
class InterpreterReport:
    """What ``check_interpreter`` found out about a project interpreter."""

    python: Path
    exists: bool
    version: str | None = None
    missing: tuple[str, ...] = ()
    has_pip: bool = False
    error: str | None = None
    found: dict[str, bool] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.exists and self.error is None and not self.missing

    def fix_command(self) -> str | None:
        """A shell command that installs the missing modules, or None if nothing is missing."""
        if not self.missing:
            return None
        packages = " ".join(self.missing)
        if self.has_pip:
            return f"{self.python} -m pip install {packages}"
        if shutil.which("uv"):
            # uv-created venvs ship without pip.
            return f"uv pip install --python {self.python} {packages}"
        return f"{self.python} -m ensurepip && {self.python} -m pip install {packages}"


def interpreter_path(python: str | os.PathLike[str]) -> Path:
    """Make ``python`` absolute without resolving symlinks.

    A venv's ``bin/python`` is a symlink to the base interpreter. Resolving it
    would drop the venv and with it the project's packages.
    """
    return Path(os.path.abspath(os.path.expanduser(python)))


def check_interpreter(
    python: str | os.PathLike[str],
    required: tuple[str, ...] = REQUIRED_MODULES,
    timeout: float = 30.0,
) -> InterpreterReport:
    """Run ``python`` once and report its version and which required modules it lacks."""
    path = interpreter_path(python)
    if not path.is_file():
        return InterpreterReport(python=path, exists=False, error=f"{path} does not exist")

    try:
        proc = subprocess.run(
            [str(path), "-c", _PROBE, *required, "pip"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return InterpreterReport(python=path, exists=True, error=f"could not run {path}: {exc}")

    if proc.returncode != 0:
        detail = proc.stderr.strip().splitlines()[-1:] or ["no output"]
        return InterpreterReport(
            python=path, exists=True, error=f"{path} exited with {proc.returncode}: {detail[0]}"
        )

    try:
        result = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return InterpreterReport(
            python=path, exists=True, error=f"{path} printed unexpected output: {proc.stdout!r}"
        )

    found: dict[str, bool] = result["found"]
    return InterpreterReport(
        python=path,
        exists=True,
        version=result["version"],
        missing=tuple(m for m in required if not found.get(m)),
        has_pip=found.get("pip", False),
        found={m: found[m] for m in required},
    )


def _venv_python(venv: Path) -> Path:
    if sys.platform == "win32":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def find_project_python(project_dir: Path | None = None) -> Path | None:
    """Guess the project interpreter: ``.venv`` or ``venv`` in ``project_dir``, else ``$VIRTUAL_ENV``."""
    project_dir = project_dir or Path.cwd()
    for name in (".venv", "venv"):
        candidate = _venv_python(project_dir / name)
        if candidate.is_file():
            return interpreter_path(candidate)
    if venv := os.environ.get("VIRTUAL_ENV"):
        candidate = _venv_python(Path(venv))
        if candidate.is_file():
            return interpreter_path(candidate)
    return None


def venv_root(python: Path) -> Path | None:
    """The venv directory that ``python`` belongs to, or None for a non-venv interpreter."""
    root = python.parent.parent
    return root if (root / "pyvenv.cfg").is_file() else None
