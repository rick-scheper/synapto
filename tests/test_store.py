"""M1: ``synapto publish`` validates a bundle, copies it into the store and indexes it."""

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from synapto.cli import app

LESSON_ID = "2026-10-03-voxel-downsampling"


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "synapto-home"
    monkeypatch.setenv("SYNAPTO_HOME", str(home))
    return home


def publish(bundle: Path, *args: str):
    return CliRunner().invoke(app, ["publish", str(bundle), *args])


def indexed(home: Path) -> list[tuple]:
    with sqlite3.connect(home / "synapto.db") as db:
        return db.execute("SELECT id, title, difficulty, concepts_json FROM lessons").fetchall()


def test_publish_copies_and_indexes(bundle: Path, home: Path) -> None:
    (bundle / "exercises" / "01-voxel-key" / "__pycache__").mkdir(exist_ok=True)

    result = publish(bundle)

    assert result.exit_code == 0, result.output
    target = home / "lessons" / LESSON_ID
    assert f"Published {LESSON_ID} to {target}" in result.output
    assert f"Lesson URL: http://127.0.0.1:8765/lessons/{LESSON_ID}" in result.output
    assert (target / "notebook.ipynb").read_bytes() == (bundle / "notebook.ipynb").read_bytes()
    assert not (target / "exercises" / "01-voxel-key" / "__pycache__").exists()
    assert indexed(home) == [(LESSON_ID, "Voxel downsampling", "beginner",
                              json.dumps(["voxel grid", "floor division", "spatial hashing"]))]
    assert [p.name for p in (home / "lessons").iterdir()] == [LESSON_ID]


def test_invalid_bundle_is_not_published(bundle: Path, home: Path) -> None:
    (bundle / "quiz.json").unlink()

    result = publish(bundle)

    assert result.exit_code == 1
    assert "quiz.json: required file is missing" in result.output
    assert "Not published" in result.output
    assert not (home / "lessons").exists()


def test_existing_id_suggests_a_free_one(bundle: Path, home: Path) -> None:
    assert publish(bundle).exit_code == 0
    (home / "lessons" / f"{LESSON_ID}-2").mkdir()

    result = publish(bundle)

    assert result.exit_code == 1
    assert (f'lesson.json:id: lesson {LESSON_ID!r} is already published in {home / "lessons"}. '
            f'Set "id" to "{LESSON_ID}-3" and publish again, or pass --force to replace it.'
            ) in " ".join(result.output.split())


def test_force_replaces_the_published_lesson(bundle: Path, home: Path) -> None:
    assert publish(bundle).exit_code == 0
    stale = home / "lessons" / LESSON_ID / "stale.txt"
    stale.write_text("from the first publish")
    lesson = json.loads((bundle / "lesson.json").read_text())
    lesson["title"] = "Voxel downsampling, revised"
    (bundle / "lesson.json").write_text(json.dumps(lesson))

    result = publish(bundle, "--force")

    assert result.exit_code == 0, result.output
    assert not stale.exists()
    assert [row[1] for row in indexed(home)] == ["Voxel downsampling, revised"]
    assert [p.name for p in (home / "lessons").iterdir()] == [LESSON_ID]


def remove(*args: str, input: str | None = None):
    return CliRunner().invoke(app, ["remove", *args], input=input)


def test_remove_deletes_the_lesson(bundle: Path, home: Path) -> None:
    assert publish(bundle).exit_code == 0

    declined = remove(LESSON_ID, input="n\n")
    assert declined.exit_code == 1
    assert (home / "lessons" / LESSON_ID).is_dir()

    result = remove(LESSON_ID, "--yes")
    assert result.exit_code == 0, result.output
    assert f"Removed {LESSON_ID}" in result.output
    assert not (home / "lessons" / LESSON_ID).exists()
    assert indexed(home) == []


def test_remove_unknown_lesson(home: Path) -> None:
    result = remove("2026-01-01-nope", "--yes")
    assert result.exit_code == 1
    assert "no lesson '2026-01-01-nope'" in result.output
