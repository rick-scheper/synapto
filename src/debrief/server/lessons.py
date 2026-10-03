"""What the hub shows about a published lesson: staleness and progress (spec §9.1).

These are computed on request from the published bundle, the project repo and
the learner's records in the store. Nothing here modifies a bundle.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from debrief.bundle.models import Exercise, Lesson, Quiz
from debrief.store import LessonStore


class ChangedFile(BaseModel):
    path: str
    change: Literal["modified", "missing"]


class Staleness(BaseModel):
    """Whether the project's code has moved on since the lesson was made."""

    stale: bool
    repo_missing: bool
    changed: list[ChangedFile]


class QuizProgress(BaseModel):
    answered: int
    correct: int
    total: int


class ExerciseProgress(BaseModel):
    passed: int
    total: int


class Progress(BaseModel):
    value: float
    """Answered questions plus passed exercises, as a fraction of all of them (0…1)."""
    quiz: QuizProgress
    exercises: ExerciseProgress


class LessonSummary(BaseModel):
    """One lesson in the Library."""

    id: str
    title: str
    summary: str
    created_at: str
    difficulty: str
    concepts: list[str]
    repo_path: str
    branch: str | None
    head_commit: str | None
    progress: Progress
    staleness: Staleness
    opened_at: str | None


def staleness(lesson: Lesson) -> Staleness:
    """Compare the ``source.files`` hashes in ``lesson.json`` with the files in the repo now."""
    repo = Path(lesson.source.repo_path)
    if not repo.is_dir():
        return Staleness(stale=True, repo_missing=True, changed=[])
    changed = []
    for file in lesson.source.files:
        path = repo / file.path
        if not path.is_file():
            changed.append(ChangedFile(path=file.path, change="missing"))
        elif hashlib.sha256(path.read_bytes()).hexdigest() != file.sha256:
            changed.append(ChangedFile(path=file.path, change="modified"))
    return Staleness(stale=bool(changed), repo_missing=False, changed=changed)


def load_quiz(store: LessonStore, lesson_id: str) -> Quiz:
    return Quiz.model_validate_json((store.lesson_dir(lesson_id) / "quiz.json").read_bytes())


def exercise_ids(store: LessonStore, lesson_id: str) -> list[str]:
    """The lesson's exercise ids (their folder names), in order."""
    return sorted(p.name for p in (store.lesson_dir(lesson_id) / "exercises").iterdir()
                  if (p / "exercise.json").is_file())


def load_exercise(store: LessonStore, lesson_id: str, exercise_id: str) -> Exercise:
    path = store.lesson_dir(lesson_id) / "exercises" / exercise_id / "exercise.json"
    return Exercise.model_validate_json(path.read_bytes())


def progress(store: LessonStore, lesson_id: str) -> Progress:
    """Answered questions and exercises with at least one passing run."""
    questions = {q.id for q in load_quiz(store, lesson_id).questions}
    answers = {qid: a for qid, a in store.latest_answers(lesson_id).items() if qid in questions}
    exercises = exercise_ids(store, lesson_id)
    runs = store.exercise_runs(lesson_id)
    passed = sum(any(r.passed for r in runs.get(eid, ())) for eid in exercises)
    total = len(questions) + len(exercises)
    return Progress(
        value=(len(answers) + passed) / total if total else 0.0,
        quiz=QuizProgress(answered=len(answers), correct=sum(a.correct for a in answers.values()),
                          total=len(questions)),
        exercises=ExerciseProgress(passed=passed, total=len(exercises)),
    )


def update_completion(store: LessonStore, lesson_id: str) -> None:
    """Record that the lesson is complete once every question is answered and every exercise passed."""
    if progress(store, lesson_id).value >= 1:
        store.mark_completed(lesson_id)


def summarise(store: LessonStore, lesson: Lesson, opened_at: str | None) -> LessonSummary:
    return LessonSummary(
        id=lesson.id, title=lesson.title, summary=lesson.summary,
        created_at=lesson.created_at.isoformat(), difficulty=lesson.difficulty,
        concepts=lesson.concepts, repo_path=lesson.source.repo_path,
        branch=lesson.source.branch, head_commit=lesson.source.head_commit,
        progress=progress(store, lesson.id), staleness=staleness(lesson), opened_at=opened_at,
    )
