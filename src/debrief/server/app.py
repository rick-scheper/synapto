"""The hub's HTTP API and the web UI (spec §9).

``create_app`` builds the FastAPI app over a ``LessonStore``. Everything under
``/api`` is JSON (raw bundle files aside); every other path serves the built
single-page app from ``web_dir``, falling back to its ``index.html`` so client
routes such as ``/lessons/<id>`` load the app (ADR-0005).

The kernel socket runs code, so the app only answers requests addressed to
``127.0.0.1``/``localhost`` (against DNS rebinding) and refuses WebSockets and
non-GET requests sent from another origin (against cross-site requests from any
page open in the browser).
"""

from __future__ import annotations

import asyncio
import json
import re
from collections import Counter
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from pydantic import BaseModel
from starlette.datastructures import Headers
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

import debrief
from debrief.bundle.decisions import Decisions, parse_decisions
from debrief.bundle.models import Exercise, Lesson
from debrief.server.lessons import (
    LessonSummary,
    Progress,
    QuizProgress,
    Staleness,
    exercise_ids,
    load_exercise,
    load_quiz,
    progress,
    staleness,
    summarise,
    update_completion,
)
from debrief.server.kernels import KernelConfig, KernelError, KernelPool, LessonKernel
from debrief.server.notebook import (
    MissingSlotError,
    NotebookState,
    SlotState,
    check_slot_values,
    parse_notebook,
    require_slots,
    serve_kernel_socket,
    slot_states,
)
from debrief.server.testrunner import TestStatus, run_tests
from debrief.store import ExerciseRun, LessonStore

WEB_DIR = Path(debrief.__file__).parent / "web"

LOCAL_HOSTS = ("127.0.0.1", "localhost")

_LESSON_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

_NOT_BUILT = """<!doctype html><meta charset="utf-8"><title>debrief</title>
<p>The web UI hasn't been built. Run <code>npm install &amp;&amp; npm run build</code> in
<code>web/</code>, then reload. The API is available under <code>/api</code>.</p>"""


class AnswerRecord(BaseModel):
    option_id: str
    correct: bool


class LessonDetail(BaseModel):
    lesson: Lesson
    progress: Progress
    staleness: Staleness
    answers: dict[str, AnswerRecord]
    """The latest answer to each quiz question, by question id."""


class AnswerRequest(BaseModel):
    option_id: str


class AnswerResult(BaseModel):
    correct: bool
    correct_option: str
    explanation: str


class RunRecord(BaseModel):
    passed: bool
    n_passed: int
    n_total: int
    ran_at: str


class ExerciseState(BaseModel):
    exercise: Exercise
    stub: str
    """``stub.py``, the code the editor starts from."""
    runs: list[RunRecord]
    """Every test run, oldest first; their number is the attempt count."""
    passed: bool
    """Whether any run passed every test."""


class Code(BaseModel):
    code: str


class Draft(BaseModel):
    code: str
    """The learner's in-progress code, else ``stub.py``."""
    saved: bool
    updated_at: str | None


class TestCaseResult(BaseModel):
    __test__ = False  # not a pytest test class

    name: str
    status: TestStatus
    message: str


class RunResult(RunRecord):
    tests: list[TestCaseResult]
    error: str | None
    """Why pytest produced no per-test results, e.g. the code doesn't import."""


class NotebookUpdate(BaseModel):
    notebook: dict[str, Any]


class SlotValues(BaseModel):
    values: dict[str, Any]
    """The learner's value per slot; a slot that's left out or None uses its default."""


class KernelInfo(BaseModel):
    session: str
    """Changes whenever a new kernel process starts."""
    busy: bool


class ConceptProgress(BaseModel):
    name: str
    lessons: int


class Totals(BaseModel):
    lessons: int
    in_progress: int
    completed: int
    stale: int
    quiz: QuizProgress
    concepts: list[ConceptProgress]
    """Every concept with the number of lessons that teach it, most common first."""


class SameOriginMiddleware:
    """Refuse WebSockets and non-GET requests whose ``Origin`` isn't the host they're sent to.

    Browsers let any page open a WebSocket to 127.0.0.1 and send it simple POSTs,
    so without this, a website could run code through the kernel socket.
    Requests without an ``Origin`` (curl, the CLI) aren't from a browser page and pass.
    """

    _SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            headers = Headers(scope=scope)
            origin = headers.get("origin")
            unsafe = scope["type"] == "websocket" or scope["method"] not in self._SAFE_METHODS
            if unsafe and origin is not None and urlsplit(origin).netloc != headers.get("host"):
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                else:
                    await PlainTextResponse("cross-origin request refused", 403)(scope, receive, send)
                return
        await self.app(scope, receive, send)


def create_app(
    store: LessonStore | None = None,
    web_dir: Path = WEB_DIR,
    pool: KernelPool | None = None,
    allowed_hosts: Sequence[str] = LOCAL_HOSTS,
) -> FastAPI:
    store = store or LessonStore.default()
    pool = pool or KernelPool()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        reaper = asyncio.create_task(pool.run_reaper())
        try:
            yield
        finally:
            reaper.cancel()
            await pool.shutdown_all()

    app = FastAPI(title="debrief", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)
    app.add_middleware(SameOriginMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(allowed_hosts))

    def lesson_or_404(lesson_id: str) -> Lesson:
        if not _LESSON_ID.match(lesson_id) or not (store.lesson_dir(lesson_id) / "lesson.json").is_file():
            raise HTTPException(404, f"no lesson {lesson_id!r}")
        return store.load(lesson_id)

    def summaries(repo: str | None = None) -> list[LessonSummary]:
        opened = store.opened_at()
        return [summarise(store, store.load(i), opened.get(i)) for i in store.lesson_ids(repo)]

    @app.get("/api/lessons")
    def list_lessons(repo: str | None = None, concept: str | None = None) -> list[LessonSummary]:
        lessons = summaries(repo)
        if concept is not None:
            lessons = [s for s in lessons if concept in s.concepts]
        return lessons

    @app.get("/api/lessons/{lesson_id}")
    def get_lesson(lesson_id: str) -> LessonDetail:
        lesson = lesson_or_404(lesson_id)
        store.mark_opened(lesson_id)
        answers = {qid: AnswerRecord(option_id=a.option_id, correct=a.correct)
                   for qid, a in store.latest_answers(lesson_id).items()}
        return LessonDetail(lesson=lesson, progress=progress(store, lesson_id),
                            staleness=staleness(lesson), answers=answers)

    @app.get("/api/lessons/{lesson_id}/decisions")
    def get_decisions(lesson_id: str) -> Decisions:
        lesson_or_404(lesson_id)
        return parse_decisions((store.lesson_dir(lesson_id) / "decisions.md").read_text(encoding="utf-8"))

    @app.get("/api/lessons/{lesson_id}/files/{path:path}")
    def get_file(lesson_id: str, path: str) -> FileResponse:
        lesson_or_404(lesson_id)
        root = store.lesson_dir(lesson_id).resolve()
        target = (root / path).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise HTTPException(404, f"no file {path!r} in lesson {lesson_id!r}")
        return FileResponse(target)

    @app.post("/api/lessons/{lesson_id}/quiz/{question_id}/answer")
    def answer(lesson_id: str, question_id: str, body: AnswerRequest) -> AnswerResult:
        lesson_or_404(lesson_id)
        question = next((q for q in load_quiz(store, lesson_id).questions if q.id == question_id), None)
        if question is None:
            raise HTTPException(404, f"no question {question_id!r} in lesson {lesson_id!r}")
        if body.option_id not in {o.id for o in question.options}:
            raise HTTPException(422, f"question {question_id!r} has no option {body.option_id!r}")
        correct = body.option_id == question.correct
        store.record_answer(lesson_id, question_id, body.option_id, correct)
        update_completion(store, lesson_id)
        return AnswerResult(correct=correct, correct_option=question.correct, explanation=question.explanation)

    def exercise_or_404(lesson_id: str, exercise_id: str) -> tuple[Lesson, Path]:
        lesson = lesson_or_404(lesson_id)
        if exercise_id not in exercise_ids(store, lesson_id):
            raise HTTPException(404, f"no exercise {exercise_id!r} in lesson {lesson_id!r}")
        return lesson, store.lesson_dir(lesson_id) / "exercises" / exercise_id

    def run_record(run: ExerciseRun) -> RunRecord:
        return RunRecord(passed=run.passed, n_passed=run.n_passed, n_total=run.n_total, ran_at=run.ran_at)

    @app.get("/api/lessons/{lesson_id}/exercises")
    def list_exercises(lesson_id: str) -> list[ExerciseState]:
        lesson_or_404(lesson_id)
        runs = store.exercise_runs(lesson_id)
        states = []
        for eid in exercise_ids(store, lesson_id):
            stub = (store.lesson_dir(lesson_id) / "exercises" / eid / "stub.py").read_text(encoding="utf-8")
            own = runs.get(eid, [])
            states.append(ExerciseState(exercise=load_exercise(store, lesson_id, eid), stub=stub,
                                        runs=[run_record(r) for r in own], passed=any(r.passed for r in own)))
        return states

    @app.post("/api/lessons/{lesson_id}/exercises/{exercise_id}/run")
    def run_exercise(lesson_id: str, exercise_id: str, body: Code) -> RunResult:
        # A plain def: FastAPI runs it in a worker thread, so pytest doesn't block the event loop.
        lesson, folder = exercise_or_404(lesson_id, exercise_id)
        env = lesson.environment
        outcome = run_tests(body.code, folder / "test_exercise.py", env.python, Path(env.cwd), env.extra_sys_path)
        # The code that was run is the learner's latest draft.
        store.save_draft(lesson_id, exercise_id, body.code)
        run = store.record_run(lesson_id, exercise_id, body.code, outcome.passed,
                               outcome.n_passed, len(outcome.results))
        update_completion(store, lesson_id)
        return RunResult(
            **run_record(run).model_dump(),
            tests=[TestCaseResult(name=r.name, status=r.status, message=r.message) for r in outcome.results],
            error=outcome.error,
        )

    @app.get("/api/lessons/{lesson_id}/exercises/{exercise_id}/draft")
    def get_draft(lesson_id: str, exercise_id: str) -> Draft:
        _, folder = exercise_or_404(lesson_id, exercise_id)
        draft = store.draft(lesson_id, exercise_id)
        if draft is not None:
            return Draft(code=draft[0], saved=True, updated_at=draft[1])
        return Draft(code=(folder / "stub.py").read_text(encoding="utf-8"), saved=False, updated_at=None)

    @app.put("/api/lessons/{lesson_id}/exercises/{exercise_id}/draft")
    def put_draft(lesson_id: str, exercise_id: str, body: Code) -> Draft:
        exercise_or_404(lesson_id, exercise_id)
        updated_at = store.save_draft(lesson_id, exercise_id, body.code)
        return Draft(code=body.code, saved=True, updated_at=updated_at)

    def notebook_state(lesson_id: str) -> NotebookState:
        copy = store.notebook_copy(lesson_id)
        if copy is not None:
            return NotebookState(notebook=json.loads(copy[0]), modified=True, updated_at=copy[1])
        original = (store.lesson_dir(lesson_id) / "notebook.ipynb").read_text(encoding="utf-8")
        return NotebookState(notebook=json.loads(original), modified=False, updated_at=None)

    @app.get("/api/lessons/{lesson_id}/notebook")
    def get_notebook(lesson_id: str) -> NotebookState:
        lesson_or_404(lesson_id)
        return notebook_state(lesson_id)

    @app.put("/api/lessons/{lesson_id}/notebook")
    def put_notebook(lesson_id: str, body: NotebookUpdate) -> NotebookState:
        lesson_or_404(lesson_id)
        try:
            ipynb_json = parse_notebook(body.notebook)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        updated_at = store.save_notebook_copy(lesson_id, ipynb_json)
        return NotebookState(notebook=body.notebook, modified=True, updated_at=updated_at)

    @app.post("/api/lessons/{lesson_id}/notebook/reset")
    def reset_notebook(lesson_id: str) -> NotebookState:
        lesson_or_404(lesson_id)
        store.delete_notebook_copy(lesson_id)
        return notebook_state(lesson_id)

    @app.get("/api/lessons/{lesson_id}/data-slots")
    def get_data_slots(lesson_id: str) -> list[SlotState]:
        lesson = lesson_or_404(lesson_id)
        return slot_states(lesson, store.data_slot_values(lesson_id))

    @app.put("/api/lessons/{lesson_id}/data-slots")
    def put_data_slots(lesson_id: str, body: SlotValues) -> list[SlotState]:
        lesson = lesson_or_404(lesson_id)
        values, errors = check_slot_values(lesson, body.values)
        if errors:
            raise HTTPException(422, {"message": "Some data slot values can't be used", "errors": errors})
        store.set_data_slot_values(lesson_id, values)
        return slot_states(lesson, values)

    def kernel_config(lesson_id: str) -> KernelConfig:
        lesson = lesson_or_404(lesson_id)
        states = slot_states(lesson, store.data_slot_values(lesson_id))
        # A value that has stopped working (e.g. a deleted file) falls back to the default.
        values = {s.name: s.value for s in states if s.value is not None and s.error is None}
        require_slots(lesson, values)
        return KernelConfig.for_lesson(lesson, store.lesson_dir(lesson_id), values)

    async def start_kernel(lesson_id: str) -> LessonKernel:
        return await pool.get(lesson_id, kernel_config(lesson_id))

    async def kernel_info(lesson_id: str, restart: bool = False) -> KernelInfo:
        try:
            config = kernel_config(lesson_id)
            if restart:
                # A fresh start also picks up data slot values changed since the last one.
                await pool.shutdown(lesson_id)
            kernel = await pool.get(lesson_id, config)
        except MissingSlotError as exc:
            raise HTTPException(409, str(exc)) from None
        except KernelError as exc:
            raise HTTPException(503, str(exc)) from None
        return KernelInfo(session=kernel.session, busy=kernel.busy)

    @app.post("/api/lessons/{lesson_id}/kernel")
    async def post_kernel(lesson_id: str) -> KernelInfo:
        return await kernel_info(lesson_id)

    @app.post("/api/lessons/{lesson_id}/kernel/restart")
    async def restart_kernel(lesson_id: str) -> KernelInfo:
        return await kernel_info(lesson_id, restart=True)

    @app.delete("/api/lessons/{lesson_id}/kernel", status_code=204)
    async def delete_kernel(lesson_id: str) -> None:
        lesson_or_404(lesson_id)
        await pool.shutdown(lesson_id)

    @app.websocket("/api/lessons/{lesson_id}/kernel/ws")
    async def kernel_socket(ws: WebSocket, lesson_id: str) -> None:
        try:
            lesson_or_404(lesson_id)
        except HTTPException:
            await ws.close(code=1008, reason=f"no lesson {lesson_id!r}")
            return
        await ws.accept()
        await serve_kernel_socket(ws, lambda: start_kernel(lesson_id))

    @app.get("/api/progress")
    def get_progress() -> Totals:
        lessons = summaries()
        concepts = Counter(c for s in lessons for c in s.concepts)
        return Totals(
            lessons=len(lessons),
            in_progress=sum(0 < s.progress.value < 1 for s in lessons),
            completed=sum(s.progress.value >= 1 for s in lessons),
            stale=sum(s.staleness.stale for s in lessons),
            quiz=QuizProgress(answered=sum(s.progress.quiz.answered for s in lessons),
                              correct=sum(s.progress.quiz.correct for s in lessons),
                              total=sum(s.progress.quiz.total for s in lessons)),
            concepts=[ConceptProgress(name=n, lessons=k) for n, k in concepts.most_common()],
        )

    @app.get("/api/{path:path}", include_in_schema=False)
    def api_not_found(path: str) -> None:
        raise HTTPException(404, f"no API route /api/{path}")

    @app.get("/{path:path}", include_in_schema=False)
    def web(path: str) -> Response:
        root = web_dir.resolve()
        target = (root / path).resolve()
        if path and target.is_relative_to(root) and target.is_file():
            return FileResponse(target)
        if (root / "index.html").is_file():
            return FileResponse(root / "index.html")
        return HTMLResponse(_NOT_BUILT)

    return app
