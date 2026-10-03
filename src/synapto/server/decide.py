"""The developer's choice and the review verdict of a decision lesson (ADR-0008, spec §6.1).

An open decision lesson is a round trip: the developer records a choice in the
hub, ``/decide review`` reads it with ``synapto decision show`` and stores a
verdict with ``synapto decision verdict``. The hub and the CLI both go through
this module, so the rules (only open lessons, the choice is locked once
reviewed, the recommendation stays hidden until then) live in one place.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from synapto.bundle.models import Candidate, Criterion, Lesson, Options, Recommendation, Verdict
from synapto.server.lessons import update_completion
from synapto.store import LessonStore


class DecisionError(Exception):
    """A choice or verdict that can't be recorded; the message says why."""


class Choice(BaseModel):
    option_id: str
    reasoning: str
    decided_at: str


class Review(BaseModel):
    verdict: Verdict
    agrees: bool
    """Whether the developer settled on the recommendation."""
    adr_path: str | None
    reviewed_at: str


class DecisionState(BaseModel):
    """Everything about a decision lesson's decision, as the hub and the reviewing agent see it."""

    question: str
    mode: Literal["guided", "open"]
    criteria: list[Criterion]
    options: list[Candidate]
    recommendation: Recommendation | None
    """Hidden (None) in an open lesson until it's reviewed, unless revealed for the agent."""
    choice: Choice | None
    review: Review | None


def load_options(store: LessonStore, lesson_id: str) -> Options:
    return Options.model_validate_json((store.lesson_dir(lesson_id) / "options.json").read_bytes())


def choice(store: LessonStore, lesson: Lesson) -> Choice | None:
    row = store.choice(lesson.id)
    return Choice(option_id=row.option_id, reasoning=row.reasoning, decided_at=row.decided_at) if row else None


def review(store: LessonStore, lesson: Lesson, options: Options | None = None) -> Review | None:
    row = store.verdict(lesson.id)
    if row is None:
        return None
    verdict = Verdict.model_validate_json(row.verdict_json)
    options = options or load_options(store, lesson.id)
    return Review(verdict=verdict, agrees=verdict.final_option == options.recommendation.option,
                  adr_path=row.adr_path, reviewed_at=row.reviewed_at)


def decision_state(store: LessonStore, lesson: Lesson, reveal: bool = False) -> DecisionState:
    """The lesson's decision. ``reveal`` shows the recommendation even before the review."""
    assert lesson.question is not None and lesson.mode is not None  # a decision lesson has both
    options = load_options(store, lesson.id)
    done = review(store, lesson, options)
    shown = reveal or lesson.mode == "guided" or done is not None
    return DecisionState(
        question=lesson.question, mode=lesson.mode,
        criteria=options.criteria, options=options.options,
        recommendation=options.recommendation if shown else None,
        choice=choice(store, lesson), review=done,
    )


def _require_open(lesson: Lesson) -> None:
    if lesson.kind != "decision":
        raise DecisionError(f"lesson {lesson.id!r} is not a decision lesson")
    if lesson.mode != "open":
        raise DecisionError(f"lesson {lesson.id!r} is a guided decision lesson; only open ones "
                            "have a choice and a review")


def record_choice(store: LessonStore, lesson: Lesson, option_id: str, reasoning: str) -> Choice:
    _require_open(lesson)
    ids = [o.id for o in load_options(store, lesson.id).options]
    if option_id not in ids:
        raise DecisionError(f"{option_id!r} is not one of the options ({', '.join(ids)})")
    if not reasoning.strip():
        raise DecisionError("write down why you chose it; the review challenges that reasoning")
    if store.verdict(lesson.id) is not None:
        raise DecisionError("this decision has been reviewed, so the choice can't change any more")
    row = store.save_choice(lesson.id, option_id, reasoning.strip())
    return Choice(option_id=row.option_id, reasoning=row.reasoning, decided_at=row.decided_at)


def record_verdict(store: LessonStore, lesson: Lesson, verdict: Verdict, adr_path: str | None = None) -> Review:
    _require_open(lesson)
    if store.choice(lesson.id) is None:
        raise DecisionError("the developer hasn't recorded a choice yet; they do that in the hub, "
                            "on the lesson's Options tab")
    options = load_options(store, lesson.id)
    ids = [o.id for o in options.options]
    if verdict.final_option not in ids:
        raise DecisionError(f"final_option {verdict.final_option!r} is not one of the options "
                            f"({', '.join(ids)})")
    store.save_verdict(lesson.id, verdict.model_dump_json(), adr_path)
    update_completion(store, lesson)
    done = review(store, lesson, options)
    assert done is not None
    return done
