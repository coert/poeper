from datetime import date

from fastapi.testclient import TestClient

import main
from libs.game import DailyWordGame
from test.test_game import TEST_WORDS


def test_admin_page_is_served() -> None:
    client = TestClient(main.app)

    page = client.get("/admin")

    assert page.status_code == 200
    assert "Komende dagwoorden" in page.text
    assert client.get("/static/admin.css").status_code == 200
    script = client.get("/static/admin.js")
    assert script.status_code == 200
    assert "Geverifieerd" in script.text
    assert "Niet geverifieerd" in script.text
    assert "Wordt geverifieerd…" in script.text
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
