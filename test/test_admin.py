from datetime import date

from fastapi.testclient import TestClient

import main
from libs.common_word import CommonWordAssessment
from libs.game import DailyWordGame
from test.test_game import TEST_WORDS


def test_admin_page_is_served() -> None:
    client = TestClient(main.app)

    page = client.get("/admin")

    assert page.status_code == 200
    assert "Komende dagwoorden" in page.text
    assert "Roteer verificatie" in page.text
    assert client.get("/static/admin.css").status_code == 200
    script = client.get("/static/admin.js")
    assert script.status_code == 200
    assert "Geverifieerd" in script.text
    assert "Niet geverifieerd" in script.text
    assert "Wordt geverifieerd…" in script.text
    assert "rotate-verification" in script.text
    assert "Blokkeer" in script.text
    assert "/blacklist" in script.text
    assert "setTimeout(loadSchedule, 2000)" in script.text


def test_admin_api_requires_the_configured_token(monkeypatch) -> None:
    monkeypatch.setattr(main, "ADMIN_TOKEN", "test-secret")
    client = TestClient(main.app)

    response = client.get("/admin/api/daily-words")

    assert response.status_code == 401
    assert response.json()["detail"] == "De beheersleutel is ongeldig."


def test_admin_can_list_and_rotate_future_words(monkeypatch) -> None:
    today = date(2026, 7, 19)
    game = DailyWordGame(TEST_WORDS, "bbbb", today=lambda: today)
    monkeypatch.setattr(main, "game", game)
    monkeypatch.setattr(main, "ADMIN_TOKEN", "test-secret")
    client = TestClient(main.app)
    headers = {"X-Admin-Token": "test-secret"}

    list_response = client.get(
        "/admin/api/daily-words?days=7",
        headers=headers,
    )
    assert list_response.status_code == 200
    schedule = list_response.json()
    assert len(schedule) == 7
    assert schedule[0]["date"] == "2026-07-20"
    original_word = schedule[0]["word"]

    rotate_response = client.post(
        "/admin/api/daily-words/2026-07-20/rotate",
        headers=headers,
    )
    assert rotate_response.status_code == 200
    rotated = rotate_response.json()
    assert rotated["word"] != original_word
    assert rotated["overridden"] is True


def test_admin_cannot_rotate_today(monkeypatch) -> None:
    today = date(2026, 7, 19)
    monkeypatch.setattr(
        main,
        "game",
        DailyWordGame(TEST_WORDS, "bbbb", today=lambda: today),
    )
    monkeypatch.setattr(main, "ADMIN_TOKEN", "test-secret")
    client = TestClient(main.app)

    response = client.post(
        "/admin/api/daily-words/2026-07-19/rotate",
        headers={"X-Admin-Token": "test-secret"},
    )

    assert response.status_code == 400


def test_admin_can_blacklist_and_replace_a_future_word(monkeypatch, tmp_path) -> None:
    today = date(2026, 7, 19)
    game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: today,
        schedule_path=tmp_path / "daily-words.json",
    )
    monkeypatch.setattr(main, "game", game)
    monkeypatch.setattr(main, "ADMIN_TOKEN", "test-secret")
    client = TestClient(main.app)
    headers = {"X-Admin-Token": "test-secret"}
    original = client.get(
        "/admin/api/daily-words?days=7", headers=headers
    ).json()[0]

    response = client.post(
        "/admin/api/daily-words/2026-07-20/blacklist",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["word"] != original["word"]
    refreshed_words = client.get(
        "/admin/api/daily-words?days=7", headers=headers
    ).json()
    assert original["word"] not in {item["word"] for item in refreshed_words}
    rejected_entry = client.post("/game/entries", json={"word": original["word"]})
    assert rejected_entry.status_code == 400
    assert rejected_entry.json()["detail"] == "Dit woord staat op de zwarte lijst."


def test_admin_can_rotate_verification_in_bulk(monkeypatch) -> None:
    today = date(2026, 7, 19)
    assessed_words: list[str] = []

    def assess(word: str):
        assessed_words.append(word)
        return CommonWordAssessment(
            common=len(assessed_words) > 1,
            reason="testbeoordeling",
        )

    game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: today,
        word_assessor=assess,
    )
    monkeypatch.setattr(main, "game", game)
    monkeypatch.setattr(main, "ADMIN_TOKEN", "test-secret")
    client = TestClient(main.app)
    headers = {"X-Admin-Token": "test-secret"}

    before_words = [item.word for item in game.upcoming_words(7)]

    response = client.post(
        "/admin/api/daily-words/rotate-verification?days=7",
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["days"] == 7
    assert payload["rotated_days"] >= 1
    assert payload["failed_days"] == 0
    assert payload["verification_completed"] is True

    after = client.get("/admin/api/daily-words?days=7", headers=headers)
    assert after.status_code == 200
    after_words = [item["word"] for item in after.json()]
    assert before_words != after_words
