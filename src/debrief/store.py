"""The central lesson store (ADR-0003, spec §10).

Published bundles live in ``<home>/lessons/<id>/`` and are never modified after
publish. ``<home>/debrief.db`` indexes them. ``<home>`` is ``~/.debrief``
unless ``DEBRIEF_HOME`` is set.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from debrief.bundle.models import Lesson

# Left behind in a bundle by validation or by the agent's own test runs.
_SCRATCH = shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ipynb_checkpoints")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS lessons (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    repo_path     TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    concepts_json TEXT NOT NULL,
    difficulty    TEXT NOT NULL
);
"""


def debrief_home() -> Path:
    """``$DEBRIEF_HOME``, else ``~/.debrief``."""
    return Path(os.environ.get("DEBRIEF_HOME") or Path.home() / ".debrief").expanduser()


class LessonExistsError(Exception):
    """A lesson with this id is already published."""

    def __init__(self, lesson_id: str, free_id: str) -> None:
        super().__init__(f"lesson {lesson_id!r} is already published")
        self.lesson_id = lesson_id
        self.free_id = free_id


@dataclass(frozen=True)
class LessonStore:
    home: Path

    @classmethod
    def default(cls) -> LessonStore:
        return cls(debrief_home())

    @property
    def lessons_dir(self) -> Path:
        return self.home / "lessons"

    @property
    def db_path(self) -> Path:
        return self.home / "debrief.db"

    def lesson_dir(self, lesson_id: str) -> Path:
        return self.lessons_dir / lesson_id

    def connect(self) -> sqlite3.Connection:
        self.home.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.db_path)
        db.executescript(_SCHEMA)
        return db

    def exists(self, lesson_id: str) -> bool:
        if self.lesson_dir(lesson_id).exists():
            return True
        with closing(self.connect()) as db:
            return db.execute("SELECT 1 FROM lessons WHERE id = ?", (lesson_id,)).fetchone() is not None

    def free_id(self, lesson_id: str) -> str:
        """``lesson_id`` if it's unused, else the first free ``<lesson_id>-2``, ``-3``, …"""
        candidate, n = lesson_id, 1
        while self.exists(candidate):
            n += 1
            candidate = f"{lesson_id}-{n}"
        return candidate

    def publish(self, bundle: Path, lesson: Lesson, force: bool = False) -> Path:
        """Copy a validated ``bundle`` into the store and index it; return its new folder.

        Raises ``LessonExistsError`` if the id is taken, unless ``force`` is set,
        in which case the published bundle and its index row are replaced.
        """
        if not force and self.exists(lesson.id):
            raise LessonExistsError(lesson.id, self.free_id(lesson.id))

        target = self.lesson_dir(lesson.id)
        staging = self.lessons_dir / f".staging-{lesson.id}"
        old = self.lessons_dir / f".old-{lesson.id}"
        for leftover in (staging, old):
            shutil.rmtree(leftover, ignore_errors=True)
        self.lessons_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(bundle, staging, ignore=_SCRATCH)

        # Move the folder inside the transaction, so a failed move rolls back the index row.
        with closing(self.connect()) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO lessons VALUES (?, ?, ?, ?, ?, ?)",
                (lesson.id, lesson.title, lesson.source.repo_path, lesson.created_at.isoformat(),
                 json.dumps(lesson.concepts), lesson.difficulty),
            )
            if target.exists():
                target.rename(old)
            staging.rename(target)
        shutil.rmtree(old, ignore_errors=True)
        return target
