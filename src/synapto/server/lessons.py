"""What the hub shows about a published lesson: staleness and progress (spec §9.1).

These are computed on request from the published bundle, the project repo and
the learner's records in the store. Nothing here modifies a bundle.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from synapto.bundle.models import Exercise, Lesson, Quiz
from synapto.store import LessonStore


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


class ReviewProgress(BaseModel):
    reviewed: int
    total: int
    """1 for an open decision lesson, which completes once its choice is reviewed; else 0."""


class Progress(BaseModel):
    value: float
    """Answered questions, passed exercises and a done review, as a fraction of all of them (0…1).

    0 for a lesson with none of them: it has nothing to complete.
    """
    quiz: QuizProgress
    exercises: ExerciseProgress
    review: ReviewProgress


class LessonSummary(BaseModel):
    """One lesson in the Library."""

    id: str
    kind: Literal["debrief", "decision"]
    mode: Literal["guided", "open"] | None
    title: str
    summary: str
    created_at: str
    difficulty: str
    concepts: list[str]
    repo_path: str | None
    """None for a decision lesson made without a repo."""
    branch: str | None
    head_commit: str | None
    progress: Progress
    staleness: Staleness
    opened_at: str | None


def staleness(lesson: Lesson) -> Staleness:
    """Compare the ``source.files`` hashes in ``lesson.json`` with the files in the repo now.

    A lesson without source files (a decision lesson) has nothing to go stale.
    """
    if lesson.source is None or not lesson.source.files:
        return Staleness(stale=False, repo_missing=False, changed=[])
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


def progress(store: LessonStore, lesson: Lesson) -> Progress:
    """Answered questions, exercises with at least one passing run, and a done review."""
    questions = {q.id for q in load_quiz(store, lesson.id).questions} if "quiz" in lesson.parts else set()
    answers = {qid: a for qid, a in store.latest_answers(lesson.id).items() if qid in questions}
    exercises = exercise_ids(store, lesson.id) if "rebuild" in lesson.parts else []
    runs = store.exercise_runs(lesson.id)
    passed = sum(any(r.passed for r in runs.get(eid, ())) for eid in exercises)
    reviewable = lesson.mode == "open"
    reviewed = int(reviewable and store.verdict(lesson.id) is not None)
    total = len(questions) + len(exercises) + reviewable
    return Progress(
        value=(len(answers) + passed + reviewed) / total if total else 0.0,
        quiz=QuizProgress(answered=len(answers), correct=sum(a.correct for a in answers.values()),
                          total=len(questions)),
        exercises=ExerciseProgress(passed=passed, total=len(exercises)),
        review=ReviewProgress(reviewed=reviewed, total=int(reviewable)),
    )


def update_completion(store: LessonStore, lesson: Lesson) -> None:
    """Record that the lesson is complete once everything in it is answered, passed or reviewed."""
    if progress(store, lesson).value >= 1:
        store.mark_completed(lesson.id)


def summarise(store: LessonStore, lesson: Lesson, opened_at: str | None) -> LessonSummary:
    source = lesson.source
    return LessonSummary(
        id=lesson.id, kind=lesson.kind, mode=lesson.mode, title=lesson.title, summary=lesson.summary,
        created_at=lesson.created_at.isoformat(), difficulty=lesson.difficulty,
        concepts=lesson.concepts, repo_path=source.repo_path if source else None,
        branch=source.branch if source else None, head_commit=source.head_commit if source else None,
        progress=progress(store, lesson), staleness=staleness(lesson), opened_at=opened_at,
    )
