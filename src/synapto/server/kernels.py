"""Jupyter kernels that run lesson code in the project's own venv (ADR-0001, spec §9.2).

Lesson code never runs inside the synapto process. Each lesson gets an ipykernel
started with ``environment.python``, so the project's real packages and files
work. Before any cell runs, a hidden preamble puts ``extra_sys_path`` and the
bundle directory on ``sys.path`` and defines ``SYNAPTO_DATA`` and
``SYNAPTO_LESSON_DIR`` (spec §5.4).

``LessonKernel.execute`` translates Jupyter iopub messages into a small JSON
protocol, one dict per event:

- ``{"type": "status", "state": "busy" | "idle"}``
- ``{"type": "stream", "name": "stdout" | "stderr", "text": ...}``
- ``{"type": "display", "data": {mime: ...}, "metadata": {...}, "execution_count": n | None,
  "display_id": str | None, "update": bool}``
- ``{"type": "error", "ename": ..., "evalue": ..., "traceback": [...]}``
- ``{"type": "clear", "wait": bool}``
- ``{"type": "done", "status": "ok" | "error" | "aborted", "execution_count": n | None}``,
  always the last event.

The same class is used by the server and by ``synapto validate``, so a notebook
that validates runs the same way in the hub.
"""

from __future__ import annotations

import asyncio
import math
import queue
import time
import uuid
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jupyter_client.asynchronous.client import AsyncKernelClient
from jupyter_client.kernelspec import KernelSpec
from jupyter_client.manager import AsyncKernelManager
from traitlets import Unicode

from synapto.bundle.models import Lesson
from synapto.environment import check_interpreter, interpreter_path, project_env

KernelEvent = dict[str, Any]
DataValue = str | int | float

STARTUP_TIMEOUT = 60.0
# How long to wait for an interrupted cell to stop before giving up on it.
INTERRUPT_GRACE = 10.0
_POLL_INTERVAL = 0.5


class KernelError(RuntimeError):
    """Base class for kernel failures that the caller should show to the user."""


class KernelStartError(KernelError):
    """The kernel could not be started, or the preamble failed."""


@dataclass(frozen=True)
class KernelConfig:
    """Everything needed to start a lesson's kernel.

    ``python``, ``cwd`` and ``extra_sys_path`` come from ``lesson.json``'s
    ``environment``. ``data`` holds the resolved data slot values: file and dir
    slots must already be absolute paths.
    """

    python: Path
    cwd: Path
    lesson_dir: Path
    extra_sys_path: tuple[str, ...] = ()
    data: Mapping[str, DataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "python", interpreter_path(self.python))
        object.__setattr__(self, "cwd", Path(self.cwd).resolve())
        object.__setattr__(self, "lesson_dir", Path(self.lesson_dir).resolve())
        object.__setattr__(self, "extra_sys_path", tuple(self.extra_sys_path))
        object.__setattr__(self, "data", dict(self.data))

    @classmethod
    def for_lesson(
        cls, lesson: Lesson, lesson_dir: Path, values: Mapping[str, DataValue] | None = None
    ) -> KernelConfig:
        """The config for a lesson's kernel, with ``values`` chosen by the learner (see ``resolve_data``)."""
        env = lesson.environment
        assert env is not None, "only lessons with a notebook part have a kernel"
        return cls(
            python=Path(env.python),
            cwd=Path(env.cwd),
            lesson_dir=lesson_dir,
            extra_sys_path=tuple(env.extra_sys_path),
            data=resolve_data(lesson, lesson_dir, values),
        )

    def sys_path_entries(self) -> list[str]:
        """Absolute paths prepended to the kernel's ``sys.path``, in order."""
        entries = [str((self.cwd / p).resolve()) for p in self.extra_sys_path]
        return [*entries, str(self.lesson_dir)]


def resolve_data(
    lesson: Lesson, lesson_dir: Path, values: Mapping[str, DataValue] | None = None
) -> dict[str, DataValue]:
    """``SYNAPTO_DATA`` for a lesson: the learner's value for each slot, else its default.

    A file or dir default points inside the bundle, so it becomes an absolute path
    in ``lesson_dir``. Slots with neither a value nor a default are left out.
    """
    values = values or {}
    data: dict[str, DataValue] = {}
    for slot in lesson.data_slots:
        if slot.name in values:
            data[slot.name] = values[slot.name]
        elif slot.default is not None and slot.kind in ("file", "dir"):
            data[slot.name] = str((Path(lesson_dir) / str(slot.default)).resolve())
        elif slot.default is not None:
            data[slot.name] = slot.default
    return data


def build_preamble(config: KernelConfig) -> str:
    """The hidden code run in every fresh kernel before any lesson cell (spec §5.4)."""
    for name, value in config.data.items():
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ValueError(f"data slot {name!r}: expected str, int or float, got {value!r}")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"data slot {name!r}: number must be finite, got {value!r}")

    return "\n".join(
        [
            "import sys as _synapto_sys",
            f"for _synapto_p in reversed({config.sys_path_entries()!r}):",
            "    if _synapto_p not in _synapto_sys.path:",
            "        _synapto_sys.path.insert(0, _synapto_p)",
            "del _synapto_sys, _synapto_p",
            f"SYNAPTO_DATA = {dict(config.data)!r}",
            f"SYNAPTO_LESSON_DIR = {str(config.lesson_dir)!r}",
        ]
    )


class ProjectKernelManager(AsyncKernelManager):
    """An ``AsyncKernelManager`` whose kernel is launched with a given interpreter.

    It skips kernelspec lookup entirely, so nothing has to be registered with
    ``jupyter kernelspec install`` in the project venv.
    """

    python = Unicode(help="Absolute path to the project interpreter.")

    @property
    def kernel_spec(self) -> KernelSpec:
        return KernelSpec(
            argv=[self.python, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
            display_name=f"Synapto ({self.python})",
            language="python",
            interrupt_mode="signal",
        )


def translate(msg: dict[str, Any]) -> KernelEvent | None:
    """Turn one iopub message into a protocol event, or None if the UI doesn't need it."""
    msg_type = msg["header"]["msg_type"]
    content = msg["content"]
    if msg_type == "status":
        return {"type": "status", "state": content["execution_state"]}
    if msg_type == "stream":
        return {"type": "stream", "name": content["name"], "text": content["text"]}
    if msg_type in ("display_data", "update_display_data", "execute_result"):
        return {
            "type": "display",
            "data": content.get("data", {}),
            "metadata": content.get("metadata", {}),
            "execution_count": content.get("execution_count"),
            "display_id": content.get("transient", {}).get("display_id"),
            "update": msg_type == "update_display_data",
        }
    if msg_type == "error":
        return {
            "type": "error",
            "ename": content["ename"],
            "evalue": content["evalue"],
            "traceback": content["traceback"],
        }
    if msg_type == "clear_output":
        return {"type": "clear", "wait": content.get("wait", False)}
    return None


def _error_event(ename: str, evalue: str) -> KernelEvent:
    return {"type": "error", "ename": ename, "evalue": evalue, "traceback": [f"{ename}: {evalue}"]}


class LessonKernel:
    """One ipykernel in the project venv, with the preamble already run."""

    def __init__(self, config: KernelConfig, clock: Callable[[], float] = time.monotonic) -> None:
        self.config = config
        self._clock = clock
        self._km: ProjectKernelManager | None = None
        self._kc: AsyncKernelClient | None = None
        self._exec_lock = asyncio.Lock()
        self.last_used = clock()
        self.session = ""
        """A new id each time a kernel process starts, so clients can tell a fresh kernel."""

    @property
    def started(self) -> bool:
        return self._kc is not None

    @property
    def busy(self) -> bool:
        return self._exec_lock.locked()

    def touch(self) -> None:
        self.last_used = self._clock()

    async def is_alive(self) -> bool:
        return self._km is not None and await self._km.is_alive()

    async def start(self, timeout: float = STARTUP_TIMEOUT) -> None:
        """Start the kernel in ``config.cwd`` and run the preamble."""
        if self.started:
            return
        python = self.config.python
        if not python.is_file():
            raise KernelStartError(f"environment.python {python} does not exist")
        if not self.config.cwd.is_dir():
            raise KernelStartError(f"environment.cwd {self.config.cwd} is not a directory")

        self.session = uuid.uuid4().hex
        km = ProjectKernelManager(python=str(python), shutdown_wait_time=2.0)
        await km.start_kernel(cwd=str(self.config.cwd), env=project_env(python))
        kc = km.client()
        kc.start_channels()
        self._km, self._kc = km, kc
        try:
            try:
                await kc.wait_for_ready(timeout=timeout)
            except RuntimeError as exc:
                raise KernelStartError(self._diagnose_start_failure(str(exc))) from exc
            await self._run_preamble(timeout)
        except BaseException:
            await self.shutdown()
            raise
        self.touch()

    def _diagnose_start_failure(self, reason: str) -> str:
        report = check_interpreter(self.config.python)
        if report.missing or report.error:
            problem = report.error or f"{report.python} lacks {', '.join(report.missing)}"
            fix = report.fix_command()
            return f"kernel failed to start: {problem}." + (f" Fix: {fix}" if fix else "")
        return f"kernel failed to start with {self.config.python}: {reason}"

    async def _run_preamble(self, timeout: float) -> None:
        assert self._kc is not None
        msg_id = self._kc.execute(
            build_preamble(self.config), silent=True, store_history=False, allow_stdin=False
        )
        reply = await self._get_reply(self._kc, msg_id, timeout)
        if reply["content"]["status"] != "ok":
            content = reply["content"]
            raise KernelStartError(
                f"preamble failed: {content.get('ename')}: {content.get('evalue')}"
            )

    @staticmethod
    async def _get_reply(kc: AsyncKernelClient, msg_id: str, timeout: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise KernelError(f"no reply from kernel within {timeout:.0f}s")
            try:
                reply = await kc.get_shell_msg(timeout=remaining)
            except queue.Empty:
                continue
            if reply["parent_header"].get("msg_id") == msg_id:
                return reply

    async def execute(self, code: str, timeout: float | None = None) -> AsyncIterator[KernelEvent]:
        """Run ``code`` and yield protocol events; the last one is always ``done``.

        Executions are serialised. If ``timeout`` (seconds) passes, the kernel is
        interrupted. If the kernel dies, or is restarted or shut down meanwhile, an
        error event is yielded instead of raising. Close the iterator
        (``contextlib.aclosing``) if you stop consuming early.
        """
        async with self._exec_lock:
            km, kc = self._km, self._kc
            if km is None or kc is None:
                raise KernelError("kernel is not started")
            try:
                async for event in self._stream(km, kc, code, timeout):
                    yield event
            finally:
                # shutdown() leaves the channels of a running cell open, because closing
                # a socket under a pending poll hangs it. Close them here instead.
                if kc is not self._kc:
                    kc.stop_channels()

    async def _stream(
        self, km: ProjectKernelManager, kc: AsyncKernelClient, code: str, timeout: float | None
    ) -> AsyncIterator[KernelEvent]:
        self.touch()
        msg_id = kc.execute(code, store_history=True, allow_stdin=False)
        deadline = None if timeout is None else time.monotonic() + timeout
        interrupted_at: float | None = None

        while True:
            if kc is not self._kc:
                yield _error_event(
                    "KernelRestarted", "the kernel was restarted or shut down during this cell"
                )
                yield {"type": "done", "status": "aborted", "execution_count": None}
                return
            try:
                msg = await kc.get_iopub_msg(timeout=_POLL_INTERVAL)
            except queue.Empty:
                if kc is not self._kc:
                    continue  # reported at the top of the loop
                if not await km.is_alive():
                    yield _error_event("KernelDied", "the kernel process exited; restart it")
                    yield {"type": "done", "status": "error", "execution_count": None}
                    return
                now = time.monotonic()
                if interrupted_at is None and deadline is not None and now > deadline:
                    yield _error_event("Timeout", f"cell ran longer than {timeout:g}s; interrupted")
                    await km.interrupt_kernel()
                    interrupted_at = now
                elif interrupted_at is not None and now - interrupted_at > INTERRUPT_GRACE:
                    yield _error_event("Timeout", "kernel did not respond to the interrupt; restart it")
                    yield {"type": "done", "status": "error", "execution_count": None}
                    return
                continue

            if msg["parent_header"].get("msg_id") != msg_id:
                continue
            self.touch()
            event = translate(msg)
            if event is not None:
                yield event
            if event == {"type": "status", "state": "idle"}:
                break

        reply = await self._get_reply(kc, msg_id, STARTUP_TIMEOUT)
        yield {
            "type": "done",
            "status": reply["content"]["status"],
            "execution_count": reply["content"].get("execution_count"),
        }

    async def run(self, code: str, timeout: float | None = None) -> list[KernelEvent]:
        """Run ``code`` and collect all its events."""
        return [event async for event in self.execute(code, timeout=timeout)]

    async def interrupt(self) -> None:
        if self._km is not None:
            await self._km.interrupt_kernel()

    async def restart(self) -> None:
        """Replace the kernel with a fresh one. Works even while a cell is hanging."""
        await self.shutdown()
        await self.start()

    async def shutdown(self) -> None:
        km, kc = self._km, self._kc
        self._km = self._kc = None
        if kc is not None and not self.busy:
            kc.stop_channels()  # otherwise the running execute() closes them
        if km is None:
            return
        if await km.is_alive():
            await km.shutdown_kernel()  # also cleans up the connection file
        else:
            await km.cleanup_resources()


class KernelPool:
    """One kernel per open lesson; at most ``max_kernels``, least recently used evicted first.

    Kernels idle for longer than ``idle_timeout`` seconds are shut down by ``reap_idle``.
    """

    def __init__(
        self,
        max_kernels: int = 3,
        idle_timeout: float = 30 * 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_kernels < 1:
            raise ValueError("max_kernels must be at least 1")
        self.max_kernels = max_kernels
        self.idle_timeout = idle_timeout
        self._clock = clock
        self._kernels: dict[str, LessonKernel] = {}
        self._lock = asyncio.Lock()

    def __contains__(self, lesson_id: str) -> bool:
        return lesson_id in self._kernels

    def __len__(self) -> int:
        return len(self._kernels)

    def lesson_ids(self) -> list[str]:
        return list(self._kernels)

    async def get(self, lesson_id: str, config: KernelConfig) -> LessonKernel:
        """Return the lesson's running kernel, starting one if needed.

        A kernel whose config changed (e.g. new data slot values) or that died
        is replaced by a fresh one.
        """
        async with self._lock:
            kernel = self._kernels.get(lesson_id)
            if kernel is not None:
                if kernel.config == config and await kernel.is_alive():
                    kernel.touch()
                    return kernel
                del self._kernels[lesson_id]
                await kernel.shutdown()

            while len(self._kernels) >= self.max_kernels:
                lru = min(self._kernels, key=lambda k: self._kernels[k].last_used)
                await self._kernels.pop(lru).shutdown()

            kernel = LessonKernel(config, clock=self._clock)
            await kernel.start()
            self._kernels[lesson_id] = kernel
            return kernel

    async def restart(self, lesson_id: str) -> LessonKernel:
        kernel = self._kernels.get(lesson_id)
        if kernel is None:
            raise KeyError(lesson_id)
        await kernel.restart()
        return kernel

    async def shutdown(self, lesson_id: str) -> None:
        async with self._lock:
            kernel = self._kernels.pop(lesson_id, None)
        if kernel is not None:
            await kernel.shutdown()

    async def shutdown_all(self) -> None:
        async with self._lock:
            kernels, self._kernels = list(self._kernels.values()), {}
        await asyncio.gather(*(k.shutdown() for k in kernels))

    async def reap_idle(self) -> list[str]:
        """Shut down kernels that have been idle too long. Returns their lesson ids."""
        now = self._clock()
        async with self._lock:
            stale = [
                lesson_id
                for lesson_id, kernel in self._kernels.items()
                if not kernel.busy and now - kernel.last_used > self.idle_timeout
            ]
            kernels = [self._kernels.pop(lesson_id) for lesson_id in stale]
        await asyncio.gather(*(k.shutdown() for k in kernels))
        return stale

    async def run_reaper(self, interval: float = 60.0) -> None:
        """Call ``reap_idle`` forever; run it as a background task in the server lifespan."""
        while True:
            await asyncio.sleep(interval)
            await self.reap_idle()
