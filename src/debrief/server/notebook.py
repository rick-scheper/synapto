"""The Notebook tab's server side: data slots, the working copy and the kernel socket (spec §9.1, §9.2).

The learner's data slot values and notebook working copy live in the store; the
published bundle is never touched. ``serve_kernel_socket`` speaks the small JSON
protocol of ``debrief.server.kernels`` over a WebSocket:

- in: ``{"type": "execute", "id": str, "code": str}`` and ``{"type": "interrupt"}``
- out: the kernel events of each execution, each tagged with the request's ``"id"``.
  Every execution starts with ``{"type": "kernel", "session": str}``, so the UI can
  tell when the kernel was replaced (restart, idle shutdown, eviction) since its
  last run, and ends with ``done``.
"""

from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Awaitable, Callable
from contextlib import aclosing
from pathlib import Path
from typing import Any, Literal

import nbformat
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from debrief.bundle.models import DataSlot, Lesson
from debrief.server.kernels import DataValue, KernelError, LessonKernel


class SlotState(BaseModel):
    """A data slot as the Notebook tab shows it."""

    name: str
    kind: Literal["file", "dir", "string", "number"]
    description: str
    default: DataValue | None
    required: bool
    value: DataValue | None
    """The learner's value, or None to use the default."""
    error: str | None
    """Why ``value`` can't be used (e.g. the file has since been deleted)."""


class NotebookState(BaseModel):
    notebook: dict[str, Any]
    """The nbformat 4 notebook: the learner's working copy, else the original."""
    modified: bool
    updated_at: str | None


class MissingSlotError(Exception):
    """A required data slot has neither a value nor a default."""


def check_slot_value(slot: DataSlot, value: Any) -> tuple[DataValue | None, str | None]:
    """Normalise a learner's value for ``slot``; return ``(value, None)`` or ``(None, error)``."""
    if slot.kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return None, f"Enter a number, e.g. {slot.default if slot.default is not None else 1.0}"
        return value, None
    if not isinstance(value, str) or not value.strip():
        return None, "Enter a value, or clear the field to use the default"
    if slot.kind == "string":
        return value, None

    path = Path(value.strip()).expanduser()
    if not path.is_absolute():
        return None, f"Use an absolute path, e.g. {Path.home() / 'data' / 'example'}"
    if slot.kind == "file" and not path.is_file():
        what = "is a folder, not a file" if path.is_dir() else "not found"
        return None, f"File {what}: {path}"
    if slot.kind == "dir" and not path.is_dir():
        what = "is a file, not a folder" if path.is_file() else "not found"
        return None, f"Folder {what}: {path}"
    return str(path), None


def slot_states(lesson: Lesson, values: dict[str, DataValue]) -> list[SlotState]:
    states = []
    for slot in lesson.data_slots:
        value = values.get(slot.name)
        error = None if value is None else check_slot_value(slot, value)[1]
        states.append(SlotState(name=slot.name, kind=slot.kind, description=slot.description,
                                default=slot.default, required=slot.required, value=value, error=error))
    return states


def check_slot_values(lesson: Lesson, values: dict[str, Any]) -> tuple[dict[str, DataValue], dict[str, str]]:
    """Validate the learner's values (None means "use the default"); return ``(values, errors)``."""
    slots = {s.name: s for s in lesson.data_slots}
    clean: dict[str, DataValue] = {}
    errors: dict[str, str] = {}
    for name, value in values.items():
        if name not in slots:
            errors[name] = f"This lesson has no data slot {name!r}"
            continue
        if value is None:
            continue
        checked, error = check_slot_value(slots[name], value)
        if error is not None:
            errors[name] = error
        else:
            clean[name] = checked  # type: ignore[assignment]
    return clean, errors


def require_slots(lesson: Lesson, values: dict[str, DataValue]) -> None:
    """Raise ``MissingSlotError`` if a required slot has no value and no default."""
    missing = [s.name for s in lesson.data_slots
               if s.required and s.default is None and s.name not in values]
    if missing:
        names = ", ".join(repr(n) for n in missing)
        raise MissingSlotError(f"Choose a value for data slot {names} before starting the kernel")


def parse_notebook(notebook: dict[str, Any]) -> str:
    """Check that ``notebook`` is a valid nbformat 4 notebook; return it as JSON.

    Raises ``ValueError`` with a readable message otherwise.
    """
    if notebook.get("nbformat") != 4:
        raise ValueError("expected an nbformat 4 notebook")
    try:
        node = nbformat.from_dict(notebook)
        nbformat.validate(node)
    except nbformat.ValidationError as exc:
        raise ValueError(f"not a valid notebook: {exc.message}") from None
    return json.dumps(notebook)


async def serve_kernel_socket(ws: WebSocket, get_kernel: Callable[[], Awaitable[LessonKernel]]) -> None:
    """Run execute requests from ``ws`` on the lesson's kernel and stream the events back.

    ``get_kernel`` returns the lesson's running kernel, starting one if needed. It
    may raise ``KernelError`` or ``MissingSlotError``, which become error events.
    Requests run one at a time in the order they arrive.
    """
    send_lock = asyncio.Lock()
    queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
    current: LessonKernel | None = None

    async def send(event: dict[str, Any]) -> None:
        async with send_lock:
            await ws.send_json(event)

    async def fail(rid: str, ename: str, evalue: str) -> None:
        await send({"type": "error", "ename": ename, "evalue": evalue,
                    "traceback": [f"{ename}: {evalue}"], "id": rid})
        await send({"type": "done", "status": "error", "execution_count": None, "id": rid})

    async def execute(rid: str, code: str) -> None:
        nonlocal current
        try:
            kernel = await get_kernel()
        except (KernelError, MissingSlotError) as exc:
            await fail(rid, "KernelStartError", str(exc))
            return
        current = kernel
        await send({"type": "kernel", "session": kernel.session, "id": rid})
        async with aclosing(kernel.execute(code)) as events:
            async for event in events:
                await send({**event, "id": rid})

    async def worker() -> None:
        while True:
            rid, code = await queue.get()
            try:
                await execute(rid, code)
            except KernelError as exc:
                await fail(rid, "KernelError", str(exc))

    running = asyncio.create_task(worker())
    try:
        while True:
            try:
                msg = await ws.receive_json()
            except (json.JSONDecodeError, KeyError):
                await send({"type": "protocol_error", "message": "expected a JSON object"})
                continue
            kind = msg.get("type") if isinstance(msg, dict) else None
            if kind == "execute" and isinstance(msg.get("id"), str) and isinstance(msg.get("code"), str):
                queue.put_nowait((msg["id"], msg["code"]))
            elif kind == "interrupt":
                if current is not None:
                    await current.interrupt()
            else:
                await send({"type": "protocol_error",
                            "message": "expected {type: 'execute', id, code} or {type: 'interrupt'}"})
    except WebSocketDisconnect:
        pass
    finally:
        running.cancel()
        await asyncio.gather(running, return_exceptions=True)
