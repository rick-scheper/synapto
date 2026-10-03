"""M2: the hub's read-only API (spec §9.1) and the web UI fallback."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from synapto.bundle.models import Lesson
from synapto.server.app import create_app
from synapto.store import LessonStore

LESSON_ID = "2026-10-03-voxel-downsampling"


@pytest.fixture
def store(tmp_path: Path, bundle: Path) -> LessonStore:
    store = LessonStore(tmp_path / "home")
    store.publish(bundle, Lesson.model_validate_json((bundle / "lesson.json").read_bytes()))
    return store


@pytest.fixture
def web_dir(tmp_path: Path) -> Path:
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<!doctype html><title>hub</title>")
    (web / "assets" / "app.js").write_text("console.log('hub')")
    return web


@pytest.fixture
def client(store: LessonStore, web_dir: Path) -> TestClient:
    return TestClient(create_app(store, web_dir), base_url="http://127.0.0.1")


def quiz(store: LessonStore) -> dict:
    return json.loads((store.lesson_dir(LESSON_ID) / "quiz.json").read_text())


def repo(store: LessonStore) -> Path:
    return Path(store.load(LESSON_ID).source.repo_path)


def test_list_lessons(client: TestClient, store: LessonStore) -> None:
    [lesson] = client.get("/api/lessons").json()

    assert lesson["id"] == LESSON_ID
    assert lesson["title"] == "Voxel downsampling"
    assert lesson["staleness"] == {"stale": False, "repo_missing": False, "changed": []}
    n_questions = len(quiz(store)["questions"])
    assert lesson["progress"] == {
        "value": 0.0,
        "quiz": {"answered": 0, "correct": 0, "total": n_questions},
        "exercises": {"passed": 0, "total": 2},
        "review": {"reviewed": 0, "total": 0},
    }
    assert lesson["opened_at"] is None


def test_list_filters_by_repo_and_concept(client: TestClient, store: LessonStore) -> None:
    assert len(client.get("/api/lessons", params={"repo": str(repo(store))}).json()) == 1
    assert client.get("/api/lessons", params={"repo": "/elsewhere"}).json() == []
    assert len(client.get("/api/lessons", params={"concept": "spatial hashing"}).json()) == 1
    assert client.get("/api/lessons", params={"concept": "spatial"}).json() == []


def test_changed_and_missing_source_files_make_a_lesson_stale(client: TestClient, store: LessonStore) -> None:
    files = [f.path for f in store.load(LESSON_ID).source.files]
    (repo(store) / files[0]).write_text("# rewritten\n")

    staleness = client.get(f"/api/lessons/{LESSON_ID}").json()["staleness"]
    assert staleness["stale"] is True
    assert {"path": files[0], "change": "modified"} in staleness["changed"]

    (repo(store) / files[0]).unlink()
    staleness = client.get(f"/api/lessons/{LESSON_ID}").json()["staleness"]
    assert {"path": files[0], "change": "missing"} in staleness["changed"]


def test_get_lesson_records_that_it_was_opened(client: TestClient) -> None:
    detail = client.get(f"/api/lessons/{LESSON_ID}").json()

    assert detail["lesson"]["id"] == LESSON_ID
    assert detail["answers"] == {}
    assert client.get("/api/lessons").json()[0]["opened_at"] is not None


@pytest.mark.parametrize("lesson_id", ["no-such-lesson", "%2e%2e"])
def test_unknown_lesson_is_404(client: TestClient, lesson_id: str) -> None:
    assert client.get(f"/api/lessons/{lesson_id}").status_code == 404


def test_raw_files(client: TestClient, store: LessonStore) -> None:
    response = client.get(f"/api/lessons/{LESSON_ID}/files/diagrams/grid.svg")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")

    text = client.get(f"/api/lessons/{LESSON_ID}/files/explanation.md").text
    assert text == (store.lesson_dir(LESSON_ID) / "explanation.md").read_text()

    assert client.get(f"/api/lessons/{LESSON_ID}/files/nope.md").status_code == 404
    assert client.get(f"/api/lessons/{LESSON_ID}/files/..%2F..%2Fsynapto.db").status_code == 404


def test_answering_the_quiz(client: TestClient, store: LessonStore) -> None:
    q1 = quiz(store)["questions"][0]
    wrong = next(o["id"] for o in q1["options"] if o["id"] != q1["correct"])
    url = f"/api/lessons/{LESSON_ID}/quiz/{q1['id']}/answer"

    result = client.post(url, json={"option_id": wrong}).json()
    assert result == {"correct": False, "correct_option": q1["correct"], "explanation": q1["explanation"]}

    assert client.post(url, json={"option_id": q1["correct"]}).json()["correct"] is True

    detail = client.get(f"/api/lessons/{LESSON_ID}").json()
    assert detail["answers"] == {q1["id"]: {"option_id": q1["correct"], "correct": True}}
    assert detail["progress"]["quiz"] == {"answered": 1, "correct": 1, "total": len(quiz(store)["questions"])}
    assert detail["progress"]["value"] > 0


def test_answer_to_unknown_question_or_option(client: TestClient, store: LessonStore) -> None:
    q1 = quiz(store)["questions"][0]
    base = f"/api/lessons/{LESSON_ID}/quiz"
    assert client.post(f"{base}/nope/answer", json={"option_id": "a"}).status_code == 404
    assert client.post(f"{base}/{q1['id']}/answer", json={"option_id": "zz"}).status_code == 422


def test_decisions(client: TestClient) -> None:
    [decision] = client.get(f"/api/lessons/{LESSON_ID}/decisions").json()["decisions"]

    assert decision["title"] == "Group points with a dict instead of sorting"
    assert [o["id"] for o in decision["options"]] == ["A", "B"]
    assert decision["chosen"] == "B"
    assert decision["why"].startswith("a dict is a single O(n) pass")
    assert decision["tradeoffs"].startswith("memory grows")


def test_progress_totals(client: TestClient, store: LessonStore) -> None:
    q1 = quiz(store)["questions"][0]
    client.post(f"/api/lessons/{LESSON_ID}/quiz/{q1['id']}/answer", json={"option_id": q1["correct"]})

    totals = client.get("/api/progress").json()

    assert totals["lessons"] == 1
    assert totals["in_progress"] == 1
    assert totals["completed"] == 0
    assert totals["quiz"]["answered"] == 1
    assert {"name": "spatial hashing", "lessons": 1} in totals["concepts"]


def test_web_ui_is_served_with_a_client_route_fallback(client: TestClient) -> None:
    assert client.get("/assets/app.js").text == "console.log('hub')"
    assert "<title>hub</title>" in client.get(f"/lessons/{LESSON_ID}").text
    assert "<title>hub</title>" in client.get("/").text
    assert client.get("/api/nope").status_code == 404


def test_unbuilt_web_ui_says_how_to_build_it(store: LessonStore, tmp_path: Path) -> None:
    client = TestClient(create_app(store, tmp_path / "missing"), base_url="http://127.0.0.1")
    assert "npm run build" in client.get("/").text


def test_a_lesson_only_serves_its_parts(partial_bundle: Path, tmp_path: Path, web_dir: Path) -> None:
    store = LessonStore(tmp_path / "partial-home")
    store.publish(partial_bundle, Lesson.model_validate_json((partial_bundle / "lesson.json").read_bytes()))
    client = TestClient(create_app(store, web_dir), base_url="http://127.0.0.1")

    detail = client.get(f"/api/lessons/{LESSON_ID}").json()
    assert detail["lesson"]["parts"] == ["explain", "quiz"]
    assert detail["progress"]["exercises"] == {"passed": 0, "total": 0}
    for path in ("decisions", "notebook", "data-slots", "exercises"):
        response = client.get(f"/api/lessons/{LESSON_ID}/{path}")
        assert response.status_code == 404, path

    for q in quiz(store)["questions"]:
        client.post(f"/api/lessons/{LESSON_ID}/quiz/{q['id']}/answer", json={"option_id": q["correct"]})
    assert client.get(f"/api/lessons/{LESSON_ID}").json()["progress"]["value"] == 1.0
    assert client.get("/api/progress").json()["completed"] == 1


def test_deleting_a_lesson_removes_it_and_its_progress(client: TestClient, store: LessonStore) -> None:
    q1 = quiz(store)["questions"][0]
    client.post(f"/api/lessons/{LESSON_ID}/quiz/{q1['id']}/answer", json={"option_id": q1["correct"]})

    assert client.delete(f"/api/lessons/{LESSON_ID}").status_code == 204

    assert client.get("/api/lessons").json() == []
    assert not store.lesson_dir(LESSON_ID).exists()
    assert store.latest_answers(LESSON_ID) == {}
    assert client.get(f"/api/lessons/{LESSON_ID}").status_code == 404
    assert client.delete(f"/api/lessons/{LESSON_ID}").status_code == 404


def test_shutdown_needs_a_stop_callback(store: LessonStore, web_dir: Path, client: TestClient) -> None:
    assert client.post("/api/shutdown").status_code == 404

    stopped = []
    client = TestClient(create_app(store, web_dir, stop=lambda: stopped.append(True)), base_url="http://127.0.0.1")
    assert client.post("/api/shutdown", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/shutdown").status_code == 202
    assert stopped == [True]


def test_reload_stops_the_running_hub(store: LessonStore, web_dir: Path) -> None:
    import socket
    import threading

    import uvicorn

    from synapto.cli import _port_in_use, stop_running_hub

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    def stop() -> None:
        server.should_exit = True

    server = uvicorn.Server(uvicorn.Config(create_app(store, web_dir, stop=stop), host="127.0.0.1",
                                           port=port, log_level="warning"))
    thread = threading.Thread(target=server.run)
    thread.start()
    try:
        while not server.started:
            thread.join(0.05)
        stop_running_hub(port)
        thread.join(10)
        assert not thread.is_alive()
        assert not _port_in_use(port)
        stop_running_hub(port)  # nothing running: a no-op
    finally:
        server.should_exit = True
        thread.join(10)
