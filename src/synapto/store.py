"""The central lesson store (ADR-0003, spec §10).

Published bundles live in ``<home>/lessons/<id>/`` and are never modified after
publish. ``<home>/synapto.db`` indexes them. ``<home>`` is ``~/.synapto``
unless ``SYNAPTO_HOME`` is set.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from synapto.bundle.models import Lesson

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
CREATE TABLE IF NOT EXISTS quiz_answers (
    lesson_id   TEXT NOT NULL,
    question_id TEXT NOT NULL,
    option_id   TEXT NOT NULL,
    correct     INTEGER NOT NULL,
    answered_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exercise_runs (
    lesson_id   TEXT NOT NULL,
    exercise_id TEXT NOT NULL,
    code        TEXT NOT NULL,
    passed      INTEGER NOT NULL,
    n_passed    INTEGER NOT NULL,
    n_total     INTEGER NOT NULL,
    ran_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exercise_drafts (
    lesson_id   TEXT NOT NULL,
    exercise_id TEXT NOT NULL,
    code        TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (lesson_id, exercise_id)
);
CREATE TABLE IF NOT EXISTS notebook_copies (
    lesson_id  TEXT PRIMARY KEY,
    ipynb_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS data_slot_values (
    lesson_id TEXT NOT NULL,
    slot      TEXT NOT NULL,
    value     TEXT NOT NULL,
    PRIMARY KEY (lesson_id, slot)
);
CREATE TABLE IF NOT EXISTS lesson_status (
    lesson_id    TEXT PRIMARY KEY,
    opened_at    TEXT,
    completed_at TEXT
);
"""


def synapto_home() -> Path:
    """``$SYNAPTO_HOME``, else ``~/.synapto``."""
    return Path(os.environ.get("SYNAPTO_HOME") or Path.home() / ".synapto").expanduser()


class LessonExistsError(Exception):
    """A lesson with this id is already published."""

    def __init__(self, lesson_id: str, free_id: str) -> None:
        super().__init__(f"lesson {lesson_id!r} is already published")
        self.lesson_id = lesson_id
        self.free_id = free_id


@dataclass(frozen=True)
class QuizAnswer:
    option_id: str
    correct: bool
    answered_at: str


@dataclass(frozen=True)
class ExerciseRun:
    passed: bool
    n_passed: int
    n_total: int
    ran_at: str


@dataclass(frozen=True)
class LessonStore:
    home: Path

    @classmethod
    def default(cls) -> LessonStore:
        return cls(synapto_home())

    @property
    def lessons_dir(self) -> Path:
        return self.home / "lessons"

    @property
    def db_path(self) -> Path:
        return self.home / "synapto.db"

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

    def lesson_ids(self, repo: str | None = None) -> list[str]:
        """Published lesson ids, newest first, optionally only those built in ``repo``."""
        query, args = "SELECT id FROM lessons", ()
        if repo is not None:
            query, args = query + " WHERE repo_path = ?", (repo,)
        with closing(self.connect()) as db:
            rows = db.execute(query + " ORDER BY created_at DESC, id", args).fetchall()
        return [row[0] for row in rows if self.lesson_dir(row[0]).is_dir()]

    def load(self, lesson_id: str) -> Lesson:
        return Lesson.model_validate_json((self.lesson_dir(lesson_id) / "lesson.json").read_bytes())

    def record_answer(self, lesson_id: str, question_id: str, option_id: str, correct: bool) -> None:
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO quiz_answers VALUES (?, ?, ?, ?, ?)",
                       (lesson_id, question_id, option_id, int(correct), _now()))

    def latest_answers(self, lesson_id: str) -> dict[str, QuizAnswer]:
        """The most recent answer to each question of a lesson, by question id."""
        with closing(self.connect()) as db:
            rows = db.execute(
                "SELECT question_id, option_id, correct, answered_at FROM quiz_answers "
                "WHERE lesson_id = ? ORDER BY answered_at, rowid", (lesson_id,)).fetchall()
        return {qid: QuizAnswer(opt, bool(ok), at) for qid, opt, ok, at in rows}

    def mark_opened(self, lesson_id: str) -> None:
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO lesson_status (lesson_id, opened_at) VALUES (?, ?) "
                       "ON CONFLICT(lesson_id) DO UPDATE SET opened_at = excluded.opened_at",
                       (lesson_id, _now()))

    def opened_at(self) -> dict[str, str]:
        """When each lesson was last opened, by lesson id."""
        with closing(self.connect()) as db:
            rows = db.execute("SELECT lesson_id, opened_at FROM lesson_status "
                              "WHERE opened_at IS NOT NULL").fetchall()
        return dict(rows)

    def mark_completed(self, lesson_id: str) -> None:
        """Record when the lesson was first completed; later calls keep that time."""
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO lesson_status (lesson_id, completed_at) VALUES (?, ?) "
                       "ON CONFLICT(lesson_id) DO UPDATE SET "
                       "completed_at = COALESCE(completed_at, excluded.completed_at)",
                       (lesson_id, _now()))

    def record_run(self, lesson_id: str, exercise_id: str, code: str,
                   passed: bool, n_passed: int, n_total: int) -> ExerciseRun:
        run = ExerciseRun(passed, n_passed, n_total, _now())
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO exercise_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (lesson_id, exercise_id, code, int(passed), n_passed, n_total, run.ran_at))
        return run

    def exercise_runs(self, lesson_id: str) -> dict[str, list[ExerciseRun]]:
        """Every test run of a lesson's exercises, oldest first, by exercise id."""
        with closing(self.connect()) as db:
            rows = db.execute(
                "SELECT exercise_id, passed, n_passed, n_total, ran_at FROM exercise_runs "
                "WHERE lesson_id = ? ORDER BY ran_at, rowid", (lesson_id,)).fetchall()
        runs: dict[str, list[ExerciseRun]] = {}
        for eid, ok, n_passed, n_total, at in rows:
            runs.setdefault(eid, []).append(ExerciseRun(bool(ok), n_passed, n_total, at))
        return runs

    def draft(self, lesson_id: str, exercise_id: str) -> tuple[str, str] | None:
        """The learner's in-progress code for an exercise as ``(code, updated_at)``, if any."""
        with closing(self.connect()) as db:
            row = db.execute("SELECT code, updated_at FROM exercise_drafts "
                             "WHERE lesson_id = ? AND exercise_id = ?", (lesson_id, exercise_id)).fetchone()
        return (row[0], row[1]) if row else None

    def save_draft(self, lesson_id: str, exercise_id: str, code: str) -> str:
        """Store the draft, replacing any earlier one; return its ``updated_at``."""
        updated_at = _now()
        with closing(self.connect()) as db, db:
            db.execute("INSERT OR REPLACE INTO exercise_drafts VALUES (?, ?, ?, ?)",
                       (lesson_id, exercise_id, code, updated_at))
        return updated_at

    def notebook_copy(self, lesson_id: str) -> tuple[str, str] | None:
        """The learner's working copy of the notebook as ``(ipynb_json, updated_at)``, if any."""
        with closing(self.connect()) as db:
            row = db.execute("SELECT ipynb_json, updated_at FROM notebook_copies WHERE lesson_id = ?",
                             (lesson_id,)).fetchone()
        return (row[0], row[1]) if row else None

    def save_notebook_copy(self, lesson_id: str, ipynb_json: str) -> str:
        """Store the working copy, replacing any earlier one; return its ``updated_at``."""
        updated_at = _now()
        with closing(self.connect()) as db, db:
            db.execute("INSERT OR REPLACE INTO notebook_copies VALUES (?, ?, ?)",
                       (lesson_id, ipynb_json, updated_at))
        return updated_at

    def delete_notebook_copy(self, lesson_id: str) -> None:
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM notebook_copies WHERE lesson_id = ?", (lesson_id,))

    def data_slot_values(self, lesson_id: str) -> dict[str, str | int | float]:
        """The data slot values the learner chose, by slot name."""
        with closing(self.connect()) as db:
            rows = db.execute("SELECT slot, value FROM data_slot_values WHERE lesson_id = ?",
                              (lesson_id,)).fetchall()
        return {slot: json.loads(value) for slot, value in rows}

    def set_data_slot_values(self, lesson_id: str, values: dict[str, str | int | float]) -> None:
        """Replace all of a lesson's chosen data slot values; slots left out use their default."""
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM data_slot_values WHERE lesson_id = ?", (lesson_id,))
            db.executemany("INSERT INTO data_slot_values VALUES (?, ?, ?)",
                           [(lesson_id, slot, json.dumps(v)) for slot, v in values.items()])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
