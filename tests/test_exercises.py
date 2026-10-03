"""M4: Rebuild exercises graded with pytest, drafts and progress (spec §9.1, §9.3)."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from debrief.bundle.models import Lesson
from debrief.server.app import create_app
from debrief.store import LessonStore

LESSON_ID = "2026-10-03-voxel-downsampling"
BASE = f"/api/lessons/{LESSON_ID}"
EXERCISE = "01-voxel-key"


@pytest.fixture
def store(tmp_path: Path, bundle: Path) -> LessonStore:
    store = LessonStore(tmp_path / "home")
    store.publish(bundle, Lesson.model_validate_json((bundle / "lesson.json").read_bytes()))
    return store


@pytest.fixture
def client(store: LessonStore, tmp_path: Path) -> TestClient:
    return TestClient(create_app(store, tmp_path / "web"), base_url="http://127.0.0.1")


def bundle_file(store: LessonStore, exercise: str, name: str) -> str:
    return (store.lesson_dir(LESSON_ID) / "exercises" / exercise / name).read_text()


def completed_at(store: LessonStore) -> str | None:
    with closing(sqlite3.connect(store.db_path)) as db:
        row = db.execute("SELECT completed_at FROM lesson_status WHERE lesson_id = ?", (LESSON_ID,)).fetchone()
    return row[0] if row else None


def test_list_exercises(client: TestClient, store: LessonStore) -> None:
    first, second = client.get(f"{BASE}/exercises").json()

    assert first["exercise"]["id"] == EXERCISE
    assert first["exercise"]["function"] == "voxel_key"
    assert first["stub"] == bundle_file(store, EXERCISE, "stub.py")
    assert first["runs"] == []
    assert first["passed"] is False
    assert second["exercise"]["id"] == "02-downsample"


def test_running_the_stub_fails_every_test(client: TestClient, store: LessonStore) -> None:
    result = client.post(f"{BASE}/exercises/{EXERCISE}/run", json={"code": bundle_file(store, EXERCISE, "stub.py")}).json()

    assert result["passed"] is False
    assert result["error"] is None
    assert result["n_passed"] == 0
    assert result["n_total"] == len(result["tests"]) == 4
    assert {t["status"] for t in result["tests"]} == {"failed"}
    assert "NotImplementedError" in result["tests"][0]["message"]


def test_a_partly_right_attempt_reports_each_test(client: TestClient) -> None:
    # Truncating toward zero gets the positive cases right and the negative ones wrong.
    code = (
        "def voxel_key(point, size):\n"
        "    if size <= 0:\n"
        "        raise ValueError(size)\n"
        "    return tuple(int(c / size) for c in point)\n"
    )
    result = client.post(f"{BASE}/exercises/{EXERCISE}/run", json={"code": code}).json()

    statuses = {t["name"]: t["status"] for t in result["tests"]}
    assert statuses == {
        "test_positive_coordinates": "passed",
        "test_voxel_size_scales_the_index": "passed",
        "test_negative_coordinates_floor_toward_minus_infinity": "failed",
        "test_non_positive_size_raises": "passed",
    }
    assert (result["n_passed"], result["n_total"], result["passed"]) == (3, 4, False)


def test_code_that_does_not_import_reports_an_error(client: TestClient) -> None:
    result = client.post(f"{BASE}/exercises/{EXERCISE}/run", json={"code": "def voxel_key(:\n"}).json()

    assert result["passed"] is False
    assert result["tests"] == []
    assert "SyntaxError" in result["error"]


def test_runs_are_recorded_and_passing_counts_toward_progress(client: TestClient, store: LessonStore) -> None:
    client.post(f"{BASE}/exercises/{EXERCISE}/run", json={"code": bundle_file(store, EXERCISE, "stub.py")})
    solution = bundle_file(store, EXERCISE, "solution.py")
    assert client.post(f"{BASE}/exercises/{EXERCISE}/run", json={"code": solution}).json()["passed"] is True

    first = client.get(f"{BASE}/exercises").json()[0]
    assert [(r["passed"], r["n_passed"], r["n_total"]) for r in first["runs"]] == [(False, 0, 4), (True, 4, 4)]
    assert first["passed"] is True

    progress = client.get(BASE).json()["progress"]
    assert progress["exercises"] == {"passed": 1, "total": 2}
    assert progress["value"] > 0

    # A later failing run doesn't undo the pass.
    client.post(f"{BASE}/exercises/{EXERCISE}/run", json={"code": "x = 1\n"})
    assert client.get(BASE).json()["progress"]["exercises"]["passed"] == 1


def test_draft_falls_back_to_the_stub_and_is_saved(client: TestClient, store: LessonStore) -> None:
    url = f"{BASE}/exercises/{EXERCISE}/draft"
    assert client.get(url).json() == {"code": bundle_file(store, EXERCISE, "stub.py"), "saved": False, "updated_at": None}

    saved = client.put(url, json={"code": "# my attempt\n"}).json()
    assert saved["saved"] is True and saved["updated_at"]
    assert client.get(url).json()["code"] == "# my attempt\n"

    # Running code keeps it as the draft.
    client.post(f"{BASE}/exercises/{EXERCISE}/run", json={"code": "# ran this\n"})
    assert client.get(url).json()["code"] == "# ran this\n"
    # Drafts are per exercise.
    assert client.get(f"{BASE}/exercises/02-downsample/draft").json()["saved"] is False


def test_finishing_every_question_and_exercise_completes_the_lesson(client: TestClient, store: LessonStore) -> None:
    for question in client.get(f"{BASE}/files/quiz.json").json()["questions"]:
        client.post(f"{BASE}/quiz/{question['id']}/answer", json={"option_id": question["correct"]})
    client.post(f"{BASE}/exercises/{EXERCISE}/run", json={"code": bundle_file(store, EXERCISE, "solution.py")})
    assert completed_at(store) is None

    client.post(f"{BASE}/exercises/02-downsample/run", json={"code": bundle_file(store, "02-downsample", "solution.py")})

    assert client.get(BASE).json()["progress"]["value"] == 1
    assert completed_at(store) is not None
    assert client.get("/api/progress").json()["completed"] == 1


@pytest.mark.parametrize("exercise", ["nope", "03-missing"])
def test_unknown_exercise_is_404(client: TestClient, exercise: str) -> None:
    url = f"{BASE}/exercises/{exercise}"
    assert client.post(f"{url}/run", json={"code": ""}).status_code == 404
    assert client.get(f"{url}/draft").status_code == 404
    assert client.put(f"{url}/draft", json={"code": ""}).status_code == 404
