import json
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest

EXAMPLE = Path(__file__).parent / "example"

# The example bundle's test_exercise.py files run against candidate.py via synapto validate.
collect_ignore = ["example"]


def _make_venv(root: Path) -> tuple[Path, Path]:
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(root)], check=True)
    python = root / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    site = subprocess.run(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return python, Path(site)


@pytest.fixture(scope="session")
def project_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A separate venv standing in for a developer's project.

    It borrows ipykernel and pytest from the dev venv through a .pth file and
    has a package, ``projmarker``, that only exists in this venv.
    """
    python, site = _make_venv(tmp_path_factory.mktemp("project") / ".venv")
    (site / "borrow-dev-venv.pth").write_text(sysconfig.get_paths()["purelib"] + "\n")
    (site / "projmarker.py").write_text("WHERE = 'project venv'\n")
    return python


@pytest.fixture(scope="session")
def bare_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A venv without ipykernel or pytest."""
    python, _ = _make_venv(tmp_path_factory.mktemp("bare") / ".venv")
    return python


@pytest.fixture
def bundle(tmp_path: Path, project_python: Path) -> Path:
    """A copy of the example bundle, pointed at a copy of its project and at ``project_python``."""
    project = shutil.copytree(EXAMPLE / "project", tmp_path / "project")
    bundle = shutil.copytree(EXAMPLE / "bundle", tmp_path / "bundle")
    lesson_json = bundle / "lesson.json"
    lesson = json.loads(lesson_json.read_text())
    lesson["source"]["repo_path"] = str(project)
    lesson["environment"].update(python=str(project_python), cwd=str(project))
    lesson_json.write_text(json.dumps(lesson, indent=1))
    return bundle


@pytest.fixture
def partial_bundle(bundle: Path) -> Path:
    """The example bundle with only its explain and quiz parts (ADR-0007)."""
    lesson_json = bundle / "lesson.json"
    lesson = json.loads(lesson_json.read_text())
    lesson.update(parts=["explain", "quiz"], data_slots=[])
    lesson_json.write_text(json.dumps(lesson, indent=1))
    (bundle / "decisions.md").unlink()
    (bundle / "notebook.ipynb").unlink()
    shutil.rmtree(bundle / "exercises")
    return bundle
