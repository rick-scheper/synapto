"""Decision lessons (ADR-0008): the bundle, the hub's choice and the CLI review round trip.

The example lives in ``tests/example/decision``: an open decision lesson about
where gridsnap should store its point clouds, without a repo or environment.
"""

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from synapto.bundle.models import Lesson
from synapto.bundle.validator import validate_bundle
from synapto.cli import app as cli
from synapto.server.app import create_app
from synapto.store import LessonStore

EXAMPLE = Path(__file__).parent / "example" / "decision"
LESSON_ID = "2026-10-03-gridsnap-storage"
VERDICT = {
    "final_option": "postgis",
    "challenges": [{"question": "Who else writes to this data?", "response": "Two ingest workers, soon."}],
    "opinion": "With concurrent ingest workers on the way, PostGIS is a defensible choice.",
}


def edit_json(path: Path, change: Callable[[dict], object]) -> None:
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data, indent=1))


def messages(bundle: Path) -> list[str]:
    return [str(issue) for issue in validate_bundle(bundle).issues]


@pytest.fixture
def decision_bundle(tmp_path: Path) -> Path:
    return shutil.copytree(EXAMPLE, tmp_path / "decision")


@pytest.fixture
def home(tmp_path: Path, decision_bundle: Path, monkeypatch: pytest.MonkeyPatch) -> LessonStore:
    """A store holding the published example; also the store the CLI uses."""
    store = LessonStore(tmp_path / "home")
    monkeypatch.setenv("SYNAPTO_HOME", str(store.home))
    store.publish(decision_bundle, Lesson.model_validate_json((decision_bundle / "lesson.json").read_bytes()))
    return store


@pytest.fixture
def client(home: LessonStore, tmp_path: Path) -> TestClient:
    return TestClient(create_app(home, tmp_path / "no-web"), base_url="http://127.0.0.1")


def set_mode(store: LessonStore, mode: str) -> None:
    edit_json(store.lesson_dir(LESSON_ID) / "lesson.json", lambda d: d.update(mode=mode))


def write_verdict(tmp_path: Path, verdict: dict = VERDICT) -> Path:
    path = tmp_path / "verdict.json"
    path.write_text(json.dumps(verdict))
    return path


# --- the bundle ------------------------------------------------------------------


def test_example_decision_bundle_is_valid(decision_bundle: Path) -> None:
    result = CliRunner().invoke(cli, ["validate", str(decision_bundle)])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == f"{decision_bundle}: valid"


def test_decision_parts_default_to_explain_options_quiz(decision_bundle: Path) -> None:
    edit_json(decision_bundle / "lesson.json", lambda d: d.pop("parts"))
    lesson = Lesson.model_validate_json((decision_bundle / "lesson.json").read_bytes())
    assert lesson.parts == ["explain", "options", "quiz"]
    assert messages(decision_bundle) == []


VARIANTS: dict[str, tuple[Callable[[Path], object], str]] = {
    "no options part": (
        lambda b: (edit_json(b / "lesson.json", lambda d: d.update(parts=["explain", "quiz"])),
                   (b / "options.json").unlink()),
        "lesson.json: a decision lesson needs the 'options' part",
    ),
    "debrief part": (
        lambda b: edit_json(b / "lesson.json", lambda d: d.update(parts=["options", "notebook"])),
        "lesson.json: a decision lesson can't have the part(s) notebook",
    ),
    "no mode": (
        lambda b: edit_json(b / "lesson.json", lambda d: d.pop("mode")),
        "lesson.json: a decision lesson needs mode",
    ),
    "missing options.json": (
        lambda b: (b / "options.json").unlink(),
        "options.json: required file is missing; lesson.json parts lists 'options'",
    ),
    "unknown recommendation": (
        lambda b: edit_json(b / "options.json", lambda d: d["recommendation"].update(option="mysql")),
        "options.json: recommendation.option 'mysql' is not one of the option ids (sqlite, postgis, duckdb)",
    ),
    "missing score": (
        lambda b: edit_json(b / "options.json", lambda d: d["options"][1]["scores"].pop("ops")),
        "options.json: option 'postgis' has no score for: ops",
    ),
    "score out of range": (
        lambda b: edit_json(b / "options.json", lambda d: d["options"][0]["scores"].update(ops=6)),
        "options.json:options[0].scores.ops: Input should be less than or equal to 5 (got 6)",
    ),
    "one option": (
        lambda b: edit_json(b / "options.json", lambda d: d.update(options=d["options"][:1])),
        "options.json:options: List should have at least 2 items",
    ),
}


@pytest.mark.parametrize("name", VARIANTS)
def test_broken_decision_bundle(decision_bundle: Path, name: str) -> None:
    breaks, expected = VARIANTS[name]
    breaks(decision_bundle)
    found = messages(decision_bundle)
    assert any(m.startswith(expected) for m in found), found


def test_debrief_lesson_rejects_decision_fields(bundle: Path) -> None:
    edit_json(bundle / "lesson.json", lambda d: d.update(mode="open"))
    assert any("question and mode belong to decision lessons" in m for m in messages(bundle))


def test_debrief_lesson_needs_source(bundle: Path) -> None:
    edit_json(bundle / "lesson.json", lambda d: d.pop("source"))
    assert any(m.startswith("lesson.json: a debrief lesson needs source") for m in messages(bundle))


def test_environment_required_only_with_runnable_parts(partial_bundle: Path) -> None:
    edit_json(partial_bundle / "lesson.json", lambda d: d.pop("environment"))
    assert validate_bundle(partial_bundle, execute=False).ok


# --- the hub ---------------------------------------------------------------------


def test_summary_of_a_lesson_without_repo(client: TestClient) -> None:
    [lesson] = client.get("/api/lessons").json()
    assert (lesson["kind"], lesson["mode"], lesson["repo_path"]) == ("decision", "open", None)
    assert lesson["staleness"] == {"stale": False, "repo_missing": False, "changed": []}
    assert lesson["progress"]["review"] == {"reviewed": 0, "total": 1}


def test_open_lesson_hides_the_recommendation(client: TestClient) -> None:
    state = client.get(f"/api/lessons/{LESSON_ID}/decision").json()
    assert state["recommendation"] is None
    assert state["mode"] == "open"
    assert [o["id"] for o in state["options"]] == ["sqlite", "postgis", "duckdb"]
    assert state["choice"] is None and state["review"] is None


def test_guided_lesson_shows_the_recommendation(client: TestClient, home: LessonStore) -> None:
    set_mode(home, "guided")
    state = client.get(f"/api/lessons/{LESSON_ID}/decision").json()
    assert state["recommendation"]["option"] == "sqlite"
    response = client.put(f"/api/lessons/{LESSON_ID}/choice", json={"option_id": "sqlite", "reasoning": "x"})
    assert response.status_code == 409
    [lesson] = client.get("/api/lessons").json()
    assert lesson["progress"]["review"] == {"reviewed": 0, "total": 0}


def test_choice_can_change_until_reviewed(client: TestClient) -> None:
    url = f"/api/lessons/{LESSON_ID}/choice"
    assert client.put(url, json={"option_id": "mysql", "reasoning": "x"}).status_code == 409
    assert client.put(url, json={"option_id": "duckdb", "reasoning": "  "}).status_code == 409

    assert client.put(url, json={"option_id": "duckdb", "reasoning": "fast scans"}).status_code == 200
    response = client.put(url, json={"option_id": "postgis", "reasoning": "two writers soon"})
    assert response.json()["option_id"] == "postgis"
    assert client.get(f"/api/lessons/{LESSON_ID}/decision").json()["choice"]["reasoning"] == "two writers soon"


def test_debrief_lesson_has_no_decision(bundle: Path, tmp_path: Path) -> None:
    store = LessonStore(tmp_path / "debrief-home")
    lesson = Lesson.model_validate_json((bundle / "lesson.json").read_bytes())
    store.publish(bundle, lesson)
    client = TestClient(create_app(store, tmp_path / "no-web"), base_url="http://127.0.0.1")
    assert client.get(f"/api/lessons/{lesson.id}/decision").status_code == 404


# --- the review round trip (CLI) ---------------------------------------------------


def test_verdict_needs_a_choice_first(home: LessonStore, tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["decision", "verdict", LESSON_ID, str(write_verdict(tmp_path))])
    assert result.exit_code == 1
    assert "hasn't recorded a choice yet" in result.output


def test_review_round_trip(client: TestClient, home: LessonStore, tmp_path: Path) -> None:
    client.put(f"/api/lessons/{LESSON_ID}/choice", json={"option_id": "postgis", "reasoning": "two writers"})

    shown = CliRunner().invoke(cli, ["decision", "show", LESSON_ID])
    assert shown.exit_code == 0, shown.output
    state = json.loads(shown.output)
    assert state["recommendation"]["option"] == "sqlite"  # the agent always sees it
    assert state["choice"]["option_id"] == "postgis"

    result = CliRunner().invoke(cli, ["decision", "verdict", LESSON_ID, str(write_verdict(tmp_path)),
                                      "--adr", "docs/adr/0003-storage.md"])
    assert result.exit_code == 0, result.output
    assert "postgis differs from the recommendation" in result.output

    state = client.get(f"/api/lessons/{LESSON_ID}/decision").json()
    assert state["recommendation"]["option"] == "sqlite"  # revealed after the review
    assert state["review"]["agrees"] is False
    assert state["review"]["adr_path"] == "docs/adr/0003-storage.md"
    assert state["review"]["verdict"]["final_option"] == "postgis"

    locked = client.put(f"/api/lessons/{LESSON_ID}/choice", json={"option_id": "sqlite", "reasoning": "x"})
    assert locked.status_code == 409

    [lesson] = client.get("/api/lessons").json()
    assert lesson["progress"]["review"] == {"reviewed": 1, "total": 1}


def test_bad_verdict_file(client: TestClient, tmp_path: Path) -> None:
    client.put(f"/api/lessons/{LESSON_ID}/choice", json={"option_id": "postgis", "reasoning": "two writers"})
    verdict = write_verdict(tmp_path, {**VERDICT, "final_option": "mysql", "agrees": True})
    result = CliRunner().invoke(cli, ["decision", "verdict", LESSON_ID, str(verdict)])
    assert result.exit_code == 1
    assert f"{verdict}:agrees: unknown field" in result.output

    verdict = write_verdict(tmp_path, {**VERDICT, "final_option": "mysql"})
    result = CliRunner().invoke(cli, ["decision", "verdict", LESSON_ID, str(verdict)])
    assert result.exit_code == 1
    assert "final_option 'mysql' is not one of the options" in result.output


def test_removing_a_lesson_drops_its_decision(client: TestClient, home: LessonStore) -> None:
    client.put(f"/api/lessons/{LESSON_ID}/choice", json={"option_id": "postgis", "reasoning": "two writers"})
    home.remove(LESSON_ID)
    assert home.choice(LESSON_ID) is None
