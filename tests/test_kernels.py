from pathlib import Path

import pytest

from debrief.server.kernels import (
    KernelConfig,
    KernelPool,
    KernelStartError,
    LessonKernel,
    build_preamble,
)


def _texts(events, name="stdout") -> str:
    return "".join(e["text"] for e in events if e["type"] == "stream" and e["name"] == name)


@pytest.fixture
def config(project_python: Path, tmp_path: Path) -> KernelConfig:
    repo = tmp_path / "repo"
    (repo / "src" / "pkg").mkdir(parents=True)
    (repo / "src" / "pkg" / "__init__.py").write_text("def answer():\n    return 42\n")
    lesson = tmp_path / "lesson"
    (lesson / "fixtures").mkdir(parents=True)
    return KernelConfig(
        python=project_python,
        cwd=repo,
        lesson_dir=lesson,
        extra_sys_path=("src",),
        data={"input": str(lesson / "fixtures" / "a.txt"), "n": 3},
    )


@pytest.fixture
async def kernel(config: KernelConfig):
    k = LessonKernel(config)
    await k.start()
    yield k
    await k.shutdown()


async def test_runs_in_project_interpreter_with_preamble(kernel: LessonKernel, config) -> None:
    events = await kernel.run(
        "import os, sys, projmarker, pkg\n"
        "print(sys.executable)\n"
        "print(os.getcwd())\n"
        "print(projmarker.WHERE, pkg.answer())\n"
        "print(DEBRIEF_DATA['n'], DEBRIEF_DATA['input'])\n"
        "print(DEBRIEF_LESSON_DIR)\n"
    )
    assert events[-1] == {"type": "done", "status": "ok", "execution_count": 1}
    lines = _texts(events).splitlines()
    assert lines[0] == str(config.python)
    assert lines[1] == str(config.cwd)
    assert lines[2] == "project venv 42"
    assert lines[3] == f"3 {config.lesson_dir / 'fixtures' / 'a.txt'}"
    assert lines[4] == str(config.lesson_dir)


async def test_event_protocol(kernel: LessonKernel) -> None:
    events = await kernel.run("import sys\nprint('out'); print('err', file=sys.stderr)\n6 * 7")
    types = [e["type"] for e in events]
    assert types[0] == "status" and types[-2:] == ["status", "done"]
    assert _texts(events) == "out\n" and _texts(events, "stderr") == "err\n"
    (result,) = [e for e in events if e["type"] == "display"]
    assert result["data"]["text/plain"] == "42"
    assert result["execution_count"] == 1

    events = await kernel.run("from IPython.display import clear_output, display\n"
                              "h = display('a', display_id=True); h.update('b'); clear_output()")
    displays = [e for e in events if e["type"] == "display"]
    assert [d["update"] for d in displays] == [False, True]
    assert displays[0]["display_id"] == displays[1]["display_id"] is not None
    assert any(e["type"] == "clear" for e in events)


async def test_errors_and_state(kernel: LessonKernel) -> None:
    await kernel.run("x = 10")
    events = await kernel.run("y = x + 1\n1 / 0")
    (error,) = [e for e in events if e["type"] == "error"]
    assert error["ename"] == "ZeroDivisionError" and error["traceback"]
    assert events[-1]["status"] == "error"
    assert _texts(await kernel.run("print(y)")) == "11\n"


async def test_timeout_interrupts(kernel: LessonKernel) -> None:
    events = await kernel.run("import time\ntime.sleep(30)", timeout=1)
    enames = [e["ename"] for e in events if e["type"] == "error"]
    assert enames[0] == "Timeout" and "KeyboardInterrupt" in enames
    assert events[-1]["status"] == "error"
    # The kernel keeps its state after an interrupt.
    assert _texts(await kernel.run("print(time.time() > 0)")) == "True\n"


async def test_kernel_death_is_reported_and_restart_recovers(kernel: LessonKernel) -> None:
    await kernel.run("x = 1")
    events = await kernel.run("import os\nos._exit(1)")
    assert any(e["type"] == "error" and e["ename"] == "KernelDied" for e in events)
    assert events[-1]["status"] == "error"

    await kernel.restart()
    events = await kernel.run("print('x' in dir(), DEBRIEF_DATA['n'])")
    assert _texts(events) == "False 3\n"


async def test_restart_while_hanging(kernel: LessonKernel) -> None:
    import asyncio

    async def hang():
        return await kernel.run("import time\ntime.sleep(60)")

    task = asyncio.create_task(hang())
    await asyncio.sleep(1)
    await kernel.restart()
    events = await asyncio.wait_for(task, 10)
    assert any(e["type"] == "error" and e["ename"] == "KernelRestarted" for e in events)
    assert events[-1]["status"] == "aborted"
    assert _texts(await kernel.run("print('alive')")) == "alive\n"


async def test_missing_ipykernel_gives_actionable_error(bare_python: Path, config) -> None:
    from dataclasses import replace

    kernel = LessonKernel(replace(config, python=bare_python))
    with pytest.raises(KernelStartError, match=r"lacks ipykernel.*Fix: .*install .*ipykernel"):
        await kernel.start(timeout=20)
    assert not kernel.started


async def test_missing_interpreter(config, tmp_path: Path) -> None:
    from dataclasses import replace

    with pytest.raises(KernelStartError, match="does not exist"):
        await LessonKernel(replace(config, python=tmp_path / "nope")).start()


def test_preamble_rejects_bad_data(config) -> None:
    from dataclasses import replace

    with pytest.raises(ValueError, match="finite"):
        build_preamble(replace(config, data={"x": float("nan")}))
    with pytest.raises(ValueError, match="expected str"):
        build_preamble(replace(config, data={"x": [1]}))


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


async def test_pool_reuses_evicts_lru_and_reaps(config) -> None:
    from dataclasses import replace

    clock = FakeClock()
    pool = KernelPool(max_kernels=2, idle_timeout=100, clock=clock)
    try:
        a = await pool.get("a", config)
        clock.now = 1
        assert await pool.get("a", config) is a  # reused

        clock.now = 2
        await pool.get("b", config)
        clock.now = 3
        await pool.get("a", config)  # a is now more recently used than b
        clock.now = 4
        await pool.get("c", config)  # evicts b
        assert pool.lesson_ids() == ["a", "c"]
        assert await a.is_alive()

        # Changing data slots replaces the kernel.
        a2 = await pool.get("a", replace(config, data={"n": 5}))
        assert a2 is not a and not a.started
        assert _texts(await a2.run("print(DEBRIEF_DATA)")) == "{'n': 5}\n"

        clock.now = 4 + 101
        await pool.get("c", config)  # touch c
        assert await pool.reap_idle() == ["a"]
        assert pool.lesson_ids() == ["c"]
    finally:
        await pool.shutdown_all()
    assert len(pool) == 0
