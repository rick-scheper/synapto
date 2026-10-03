"""M3: notebook working copy, data slots and the lesson kernel over HTTP and WebSocket (spec §9.1, §9.2)."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from debrief.bundle.models import Lesson
from debrief.server.app import create_app
from debrief.store import LessonStore

LESSON_ID = "2026-10-03-voxel-downsampling"
BASE = f"/api/lessons/{LESSON_ID}"
# websocket_connect() ignores base_url, so give it the full URL.
SOCKET = f"ws://127.0.0.1{BASE}/kernel/ws"


@pytest.fixture
def store(tmp_path: Path, bundle: Path) -> LessonStore:
    store = LessonStore(tmp_path / "home")
    store.publish(bundle, Lesson.model_validate_json((bundle / "lesson.json").read_bytes()))
    return store


@pytest.fixture
def client(store: LessonStore, tmp_path: Path) -> Iterator[TestClient]:
    # `with` runs the lifespan, which shuts the kernels down afterwards; it also
    # keeps one event loop for all requests, which the kernels need.
    with TestClient(create_app(store, tmp_path / "web"), base_url="http://127.0.0.1") as client:
        yield client


def original(store: LessonStore) -> dict:
    return json.loads((store.lesson_dir(LESSON_ID) / "notebook.ipynb").read_text())


def code_cells(notebook: dict) -> list[str]:
    return ["".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"]


def run(ws: WebSocketTestSession, code: str, rid: str = "r1") -> list[dict]:
    ws.send_json({"type": "execute", "id": rid, "code": code})
    events = []
    while True:
        event = ws.receive_json()
        assert event["id"] == rid
        events.append(event)
        if event["type"] == "done":
            return events


def stdout(events: list[dict]) -> str:
    return "".join(e["text"] for e in events if e["type"] == "stream" and e["name"] == "stdout")


# --- Working copy -------------------------------------------------------------


def test_notebook_falls_back_to_the_original(client: TestClient, store: LessonStore) -> None:
    state = client.get(f"{BASE}/notebook").json()
    assert state == {"notebook": original(store), "modified": False, "updated_at": None}


def test_working_copy_is_saved_and_reset(client: TestClient, store: LessonStore) -> None:
    notebook = original(store)
    notebook["cells"][1]["source"] = "print('edited')\n"

    saved = client.put(f"{BASE}/notebook", json={"notebook": notebook}).json()
    assert saved["modified"] is True and saved["updated_at"]
    assert client.get(f"{BASE}/notebook").json()["notebook"] == notebook
    # The published bundle is never modified.
    assert original(store)["cells"][1]["source"] != "print('edited')\n"

    reset = client.post(f"{BASE}/notebook/reset").json()
    assert reset == {"notebook": original(store), "modified": False, "updated_at": None}
    assert client.get(f"{BASE}/notebook").json()["modified"] is False


def test_invalid_working_copy_is_refused(client: TestClient, store: LessonStore) -> None:
    broken = original(store)
    broken["cells"][0]["cell_type"] = "spreadsheet"
    response = client.put(f"{BASE}/notebook", json={"notebook": broken})
    assert response.status_code == 422
    assert "not a valid notebook" in response.json()["detail"]
    assert client.put(f"{BASE}/notebook", json={"notebook": {"nbformat": 3}}).status_code == 422
    assert client.get(f"{BASE}/notebook").json()["modified"] is False


# --- Data slots ---------------------------------------------------------------


def test_data_slots_show_defaults(client: TestClient) -> None:
    slots = client.get(f"{BASE}/data-slots").json()
    assert [(s["name"], s["kind"], s["default"], s["value"]) for s in slots] == [
        ("points", "file", "fixtures/points.xyz", None),
        ("voxel_size", "number", 1.0, None),
    ]


def test_data_slot_values_are_checked_and_stored(client: TestClient, tmp_path: Path) -> None:
    cloud = tmp_path / "mine.xyz"
    cloud.write_text("0 0 0\n")

    slots = client.put(f"{BASE}/data-slots", json={"values": {"points": str(cloud), "voxel_size": 0.25}}).json()
    assert {s["name"]: s["value"] for s in slots} == {"points": str(cloud), "voxel_size": 0.25}
    assert client.get(f"{BASE}/data-slots").json() == slots

    # Leaving a slot out (or sending null) goes back to the default.
    slots = client.put(f"{BASE}/data-slots", json={"values": {"voxel_size": None}}).json()
    assert {s["name"]: s["value"] for s in slots} == {"points": None, "voxel_size": None}


@pytest.mark.parametrize(
    ("values", "slot", "message"),
    [
        ({"points": "relative/points.xyz"}, "points", "Use an absolute path"),
        ({"points": "/no/such/file.xyz"}, "points", "File not found: /no/such/file.xyz"),
        ({"points": "/"}, "points", "is a folder, not a file"),
        ({"voxel_size": "big"}, "voxel_size", "Enter a number"),
        ({"voxel_size": True}, "voxel_size", "Enter a number"),
        ({"colour": "red"}, "colour", "no data slot 'colour'"),
    ],
)
def test_unusable_data_slot_values_are_refused(client: TestClient, values: dict, slot: str, message: str) -> None:
    response = client.put(f"{BASE}/data-slots", json={"values": values})
    assert response.status_code == 422
    assert message in response.json()["detail"]["errors"][slot]
    assert all(s["value"] is None for s in client.get(f"{BASE}/data-slots").json())


def test_a_value_that_stopped_working_is_reported(client: TestClient, tmp_path: Path) -> None:
    cloud = tmp_path / "mine.xyz"
    cloud.write_text("0 0 0\n")
    client.put(f"{BASE}/data-slots", json={"values": {"points": str(cloud)}})
    cloud.unlink()

    [points, _] = client.get(f"{BASE}/data-slots").json()
    assert points["value"] == str(cloud)
    assert points["error"] == f"File not found: {cloud}"


# --- Kernel -------------------------------------------------------------------


def test_whole_notebook_runs_over_the_socket(client: TestClient, store: LessonStore) -> None:
    session = client.post(f"{BASE}/kernel").json()["session"]
    with client.websocket_connect(SOCKET) as ws:
        for i, code in enumerate(code_cells(original(store))):
            events = run(ws, code, rid=f"c{i}")
            assert events[0] == {"type": "kernel", "session": session, "id": f"c{i}"}
            assert events[-1]["status"] == "ok", events
        out = stdout(run(ws, "print(DEBRIEF_DATA['points'], DEBRIEF_DATA['voxel_size'])"))
    lesson_dir = store.lesson_dir(LESSON_ID).resolve()
    assert out == f"{lesson_dir / 'fixtures' / 'points.xyz'} 1.0\n"


def test_socket_starts_the_kernel_if_needed(client: TestClient) -> None:
    with client.websocket_connect(SOCKET) as ws:
        events = run(ws, "print(1 + 1)")
    assert events[0]["type"] == "kernel"
    assert stdout(events) == "2\n"
    assert events[-1]["status"] == "ok"


def test_restart_applies_new_data_slots(client: TestClient, tmp_path: Path) -> None:
    first = client.post(f"{BASE}/kernel").json()["session"]
    assert client.post(f"{BASE}/kernel").json()["session"] == first  # same kernel

    client.put(f"{BASE}/data-slots", json={"values": {"voxel_size": 0.5}})
    second = client.post(f"{BASE}/kernel/restart").json()["session"]
    assert second != first
    with client.websocket_connect(SOCKET) as ws:
        events = run(ws, "print(DEBRIEF_DATA['voxel_size'])")
    assert events[0]["session"] == second
    assert stdout(events) == "0.5\n"


def test_errors_and_shutdown(client: TestClient) -> None:
    with client.websocket_connect(SOCKET) as ws:
        events = run(ws, "1 / 0")
        assert events[-1]["status"] == "error"
        assert [e["ename"] for e in events if e["type"] == "error"] == ["ZeroDivisionError"]

        ws.send_json({"type": "nonsense"})
        assert ws.receive_json()["type"] == "protocol_error"

        assert client.delete(f"{BASE}/kernel").status_code == 204
        # The next request starts a fresh kernel.
        events = run(ws, "print('again')")
        assert stdout(events) == "again\n"


def test_interrupt_stops_a_running_cell(client: TestClient) -> None:
    with client.websocket_connect(SOCKET) as ws:
        ws.send_json({"type": "execute", "id": "slow", "code": "import time\nprint('start', flush=True)\ntime.sleep(60)"})
        while (event := ws.receive_json()).get("text") != "start\n":
            pass
        ws.send_json({"type": "interrupt"})
        events = []
        while (event := ws.receive_json())["type"] != "done":
            events.append(event)
    assert event["status"] == "error"
    assert [e["ename"] for e in events if e["type"] == "error"] == ["KeyboardInterrupt"]


def test_required_slot_without_value_blocks_the_kernel(client: TestClient, store: LessonStore) -> None:
    lesson_json = store.lesson_dir(LESSON_ID) / "lesson.json"
    lesson = json.loads(lesson_json.read_text())
    lesson["data_slots"].append({"name": "labels", "kind": "string", "description": "Labels.", "required": True})
    lesson_json.write_text(json.dumps(lesson))

    response = client.post(f"{BASE}/kernel")
    assert response.status_code == 409
    assert "'labels'" in response.json()["detail"]
    with client.websocket_connect(SOCKET) as ws:
        events = run(ws, "print(1)")
    assert events[0]["ename"] == "KernelStartError"
    assert events[-1]["status"] == "error"

    client.put(f"{BASE}/data-slots", json={"values": {"labels": "a,b"}})
    assert client.post(f"{BASE}/kernel").status_code == 200


def test_unknown_lesson(client: TestClient) -> None:
    assert client.post("/api/lessons/nope/kernel").status_code == 404
    assert client.get("/api/lessons/nope/notebook").status_code == 404
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("ws://127.0.0.1/api/lessons/nope/kernel/ws") as ws:
        ws.receive_json()


# --- Requests from elsewhere --------------------------------------------------


def test_requests_for_other_hosts_are_refused(client: TestClient) -> None:
    # A DNS-rebinding page reaches 127.0.0.1 under its own host name.
    assert client.get("/api/lessons", headers={"Host": "evil.example"}).status_code == 400


def test_cross_origin_writes_and_sockets_are_refused(client: TestClient) -> None:
    evil = {"Origin": "https://evil.example"}
    assert client.post(f"{BASE}/kernel", headers=evil).status_code == 403
    assert client.post(f"{BASE}/notebook/reset", headers=evil).status_code == 403
    with pytest.raises(WebSocketDisconnect), client.websocket_connect(SOCKET, headers=evil) as ws:
        ws.receive_json()
    # Reads, and the hub's own pages, are fine.
    assert client.get(f"{BASE}/notebook", headers=evil).status_code == 200
    same = {"Origin": "http://127.0.0.1"}
    assert client.post(f"{BASE}/notebook/reset", headers=same).status_code == 200
