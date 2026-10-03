"""Pydantic models for the files in a lesson bundle (spec §5).

Every model forbids unknown fields, so a misspelt key is reported instead of
silently ignored. Rules that only need one file are checked here; rules that
span files (references, fixtures, execution) live in ``validator``.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 1

_SOURCE_REF = re.compile(r"^(?P<path>[^:\s]+):(?P<start>\d+)(?:-(?P<end>\d+))?$")


def _non_empty(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty")
    return value


def _relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if "\\" in value or path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"must be a relative POSIX path inside the tree, got {value!r}")
    return value


def _absolute_path(value: str) -> str:
    # Accept Windows paths too, so a bundle written on Windows reads the same.
    if not (value.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", value)):
        raise ValueError(f"must be an absolute path, got {value!r}")
    return value


def _source_ref(value: str) -> str:
    match = _SOURCE_REF.match(value)
    if match is None:
        raise ValueError(f"must look like 'path/to/file.py:12' or 'path/to/file.py:12-30', got {value!r}")
    _relative_path(match["path"])
    start, end = int(match["start"]), int(match["end"] or match["start"])
    if start < 1 or end < start:
        raise ValueError(f"line range {start}-{end} is invalid; lines start at 1 and end >= start")
    return value


PARTS = ("explain", "decisions", "options", "notebook", "quiz", "rebuild")
"""The parts a lesson can have, in the order the hub shows them."""
Part = Literal["explain", "decisions", "options", "notebook", "quiz", "rebuild"]
DEBRIEF_PARTS: tuple[Part, ...] = ("explain", "decisions", "notebook", "quiz", "rebuild")
"""The parts a debrief lesson can have, and its default."""
DECISION_PARTS: tuple[Part, ...] = ("explain", "options", "quiz")
"""The parts a decision lesson can have (ADR-0008), and its default."""
RUNNABLE_PARTS: tuple[Part, ...] = ("notebook", "rebuild")
"""The parts whose code runs in the project interpreter."""

NonEmptyStr = Annotated[str, AfterValidator(_non_empty)]
RelativePath = Annotated[str, AfterValidator(_relative_path)]
AbsolutePath = Annotated[str, AfterValidator(_absolute_path)]
SourceRef = Annotated[str, AfterValidator(_source_ref)]
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]
Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]


def source_ref_path(ref: str) -> str:
    """The file part of a valid source ref: ``'src/a.py:3-9'`` -> ``'src/a.py'``."""
    return ref.rsplit(":", 1)[0]


def _duplicates(values: list[str]) -> list[str]:
    return sorted(v for v, n in Counter(values).items() if n > 1)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- lesson.json -------------------------------------------------------------


class SourceFile(_Model):
    path: RelativePath
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Source(_Model):
    repo_path: AbsolutePath
    remote: str | None = None
    branch: str | None = None
    base_commit: str | None = None
    head_commit: str | None = None
    includes_uncommitted: bool = False
    files: list[SourceFile]
    """Every file a ``source_ref`` points into; at least one in a debrief lesson."""

    @model_validator(mode="after")
    def _unique_paths(self) -> Source:
        if dupes := _duplicates([f.path for f in self.files]):
            raise ValueError(f"files lists these paths more than once: {', '.join(dupes)}")
        return self


class Environment(_Model):
    python: AbsolutePath
    python_version: NonEmptyStr
    cwd: AbsolutePath
    extra_sys_path: list[RelativePath] = []


class DataSlot(_Model):
    name: Identifier
    kind: Literal["file", "dir", "string", "number"]
    description: NonEmptyStr
    default: str | int | float | None = None
    required: bool = False

    @model_validator(mode="after")
    def _default_matches_kind(self) -> DataSlot:
        value = self.default
        if value is None:
            return self
        if self.kind == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"default of a number slot must be a JSON number, got {value!r}")
        elif not isinstance(value, str):
            raise ValueError(f"default of a {self.kind} slot must be a string, got {value!r}")
        elif self.kind in ("file", "dir"):
            try:
                _relative_path(value)
            except ValueError:
                raise ValueError(
                    f"default of a {self.kind} slot must be a path inside the bundle "
                    f"(e.g. 'fixtures/sample.csv'), got {value!r}"
                ) from None
        return self


class Lesson(_Model):
    schema_version: Literal[1]
    kind: Literal["debrief", "decision"] = "debrief"
    """``debrief`` looks back on built code; ``decision`` teaches a choice before it's built (ADR-0008)."""
    id: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")]
    title: NonEmptyStr
    summary: NonEmptyStr
    created_at: AwareDatetime
    difficulty: Literal["beginner", "intermediate", "advanced"]
    concepts: Annotated[list[NonEmptyStr], Field(min_length=1)]
    prerequisites: list[NonEmptyStr] = []
    question: NonEmptyStr | None = None
    """A decision lesson's question, in the developer's words."""
    mode: Literal["guided", "open"] | None = None
    """A decision lesson's mode: lead to the recommendation, or let the developer decide."""
    source: Source | None = None
    """Required in a debrief lesson; a decision lesson may have no repo yet."""
    environment: Environment | None = None
    """Required when the lesson has a runnable part."""
    data_slots: list[DataSlot] = []
    parts: Annotated[list[Part], Field(min_length=1)]
    """The parts the developer chose; each has its own file(s) in the bundle.

    Defaults to every part of the lesson's kind.
    """

    @model_validator(mode="before")
    @classmethod
    def _default_parts(cls, data: object) -> object:
        if isinstance(data, dict) and "parts" not in data:
            parts = DECISION_PARTS if data.get("kind") == "decision" else DEBRIEF_PARTS
            data = {**data, "parts": list(parts)}
        return data

    @model_validator(mode="after")
    def _consistent(self) -> Lesson:
        if dupes := _duplicates([s.name for s in self.data_slots]):
            raise ValueError(f"data_slots has duplicate names: {', '.join(dupes)}")
        if dupes := _duplicates(list(self.parts)):
            raise ValueError(f"parts lists these more than once: {', '.join(dupes)}")
        allowed = DECISION_PARTS if self.kind == "decision" else DEBRIEF_PARTS
        if wrong := [p for p in self.parts if p not in allowed]:
            raise ValueError(f"a {self.kind} lesson can't have the part(s) {', '.join(wrong)}; "
                             f"its parts are {', '.join(allowed)}")
        if self.kind == "decision":
            missing = [f for f in ("question", "mode") if getattr(self, f) is None]
            if missing:
                raise ValueError(f"a decision lesson needs {' and '.join(missing)}")
            if "options" not in self.parts:
                raise ValueError("a decision lesson needs the 'options' part")
        else:
            if self.question is not None or self.mode is not None:
                raise ValueError("question and mode belong to decision lessons; remove them, "
                                 "or set kind to 'decision'")
            if self.source is None:
                raise ValueError("a debrief lesson needs source")
            if not self.source.files:
                raise ValueError("source.files must list at least one file in a debrief lesson")
        if self.environment is None and any(p in self.parts for p in RUNNABLE_PARTS):
            raise ValueError("environment is required when parts has notebook or rebuild")
        return self


# --- options.json (decision lessons) ------------------------------------------


class Criterion(_Model):
    id: Slug
    name: NonEmptyStr
    description: NonEmptyStr
    weight: Annotated[int, Field(ge=1, le=3)]


class Link(_Model):
    title: NonEmptyStr
    url: Annotated[str, Field(pattern=r"^https?://\S+$")]


class Candidate(_Model):
    id: Slug
    name: NonEmptyStr
    summary: NonEmptyStr
    strengths: Annotated[list[NonEmptyStr], Field(min_length=1)]
    weaknesses: Annotated[list[NonEmptyStr], Field(min_length=1)]
    fits_when: NonEmptyStr
    scores: dict[str, Annotated[int, Field(ge=1, le=5)]]
    """Criterion id -> 1 (poor) to 5 (excellent)."""
    links: list[Link] = []


class Recommendation(_Model):
    option: NonEmptyStr
    why: NonEmptyStr
    trade_offs: NonEmptyStr
    would_change_if: NonEmptyStr


class Options(_Model):
    criteria: Annotated[list[Criterion], Field(min_length=2, max_length=8)]
    options: Annotated[list[Candidate], Field(min_length=2, max_length=5)]
    recommendation: Recommendation

    @model_validator(mode="after")
    def _references(self) -> Options:
        criteria = [c.id for c in self.criteria]
        if dupes := _duplicates(criteria):
            raise ValueError(f"duplicate criterion ids: {', '.join(dupes)}")
        ids = [o.id for o in self.options]
        if dupes := _duplicates(ids):
            raise ValueError(f"duplicate option ids: {', '.join(dupes)}")
        for option in self.options:
            if missing := [c for c in criteria if c not in option.scores]:
                raise ValueError(f"option {option.id!r} has no score for: {', '.join(missing)}")
            if unknown := sorted(set(option.scores) - set(criteria)):
                raise ValueError(f"option {option.id!r} scores unknown criteria: {', '.join(unknown)}")
        if self.recommendation.option not in ids:
            raise ValueError(f"recommendation.option {self.recommendation.option!r} is not one of "
                             f"the option ids ({', '.join(ids)})")
        return self


# --- a review verdict (``synapto decision verdict``) ---------------------------


class Challenge(_Model):
    question: NonEmptyStr
    response: NonEmptyStr


class Verdict(_Model):
    final_option: NonEmptyStr
    """The option the developer settled on in the review; may differ from their recorded choice."""
    challenges: Annotated[list[Challenge], Field(min_length=1)]
    opinion: NonEmptyStr


# --- quiz.json -----------------------------------------------------------------


class QuizOption(_Model):
    id: NonEmptyStr
    text: NonEmptyStr


class QuizQuestion(_Model):
    id: NonEmptyStr
    prompt: NonEmptyStr
    options: list[QuizOption]
    correct: str
    explanation: NonEmptyStr
    concept: NonEmptyStr | None = None
    source_ref: SourceRef | None = None

    @model_validator(mode="after")
    def _options(self) -> QuizQuestion:
        ids = [o.id for o in self.options]
        if len(ids) < 3:
            raise ValueError(f"needs at least 3 options, has {len(ids)}")
        if dupes := _duplicates(ids):
            raise ValueError(f"duplicate option ids: {', '.join(dupes)}")
        if self.correct not in ids:
            raise ValueError(f"correct {self.correct!r} is not one of the option ids ({', '.join(ids)})")
        return self


class Quiz(_Model):
    questions: Annotated[list[QuizQuestion], Field(min_length=5, max_length=10)]

    @model_validator(mode="after")
    def _unique_ids(self) -> Quiz:
        if dupes := _duplicates([q.id for q in self.questions]):
            raise ValueError(f"duplicate question ids: {', '.join(dupes)}")
        return self


# --- exercises/<id>/exercise.json ----------------------------------------------


class Exercise(_Model):
    id: Annotated[str, Field(pattern=r"^\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")]
    title: NonEmptyStr
    function: Identifier
    prompt: NonEmptyStr
    difficulty: Literal["easy", "medium", "hard"]
    hints: list[NonEmptyStr] = []
    source_ref: SourceRef


# --- notebook.ipynb cell metadata (``metadata.synapto``) -----------------------


class CellMeta(_Model):
    role: Literal["setup", "function", "demo", "explain"]
    function: Identifier | None = None
    source_ref: SourceRef | None = None
    hidden: bool = False
    editable: bool = True

    @model_validator(mode="after")
    def _function_fields(self) -> CellMeta:
        if self.role == "function" and (self.function is None or self.source_ref is None):
            raise ValueError("a function cell needs both 'function' and 'source_ref'")
        return self
