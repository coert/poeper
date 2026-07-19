from datetime import date, datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

import main
from libs.game import DailyWordGame
from test.test_game import TEST_WORDS, ladder_moves


def test_frontend_is_served() -> None:
    client = TestClient(main.app)

    page = client.get("/")
    stylesheet = client.get("/static/styles.css")
    script = client.get("/static/app.js")

    assert page.status_code == 200
    assert "<title>POEPER 💩" in page.text
    assert ">💩</span>" in page.text
    assert (
        page.text.casefold().count("zelfs een grote boodschap houd je het best kort.")
        == 2
    )
    assert "onafhankelijke Nederlandstalige variant" in page.text
    assert 'href="https://poople.io/"' in page.text
    assert "OpenTaal-woordenlijst" in page.text
    assert 'href="https://github.com/OpenTaal/opentaal-wordlist"' in page.text
    assert stylesheet.status_code == 200
    assert script.status_code == 200
    assert 'requestGame("game")' in script.text
    assert "Die boodschap kwam er vlot uit." in script.text
    assert "Je hebt ’m eruit geperst." in script.text
    assert "launchPoopExplosion" in script.text
    assert 'context.fillText("💩", 0, 0)' in script.text
    assert 'id="share-button"' in page.text
    assert 'id="share-dialog"' in page.text
    assert 'id="share-preview"' in page.text
    assert 'id="share-copy-button"' in page.text
    assert 'id="statistics-button"' in page.text
    assert 'id="statistics-dialog"' in page.text
    assert 'id="statistics-histogram"' in page.text
    assert 'id="statistics-above-par"' in page.text
    assert 'id="countdown-timer"' in page.text
    assert "createShareText" in script.text
    assert 'statisticsCookieName = "poeper_results"' in script.text
    assert "recordCompletedGame(state)" in script.text
    assert "aboveParTotal" in script.text
    assert "function renderStatistics()" in script.text
    assert "function updateCountdown()" in script.text
    assert 'cache: "no-store"' in script.text
    assert 'headers["X-Client-Time-Zone"] = clientTimeZone' in script.text
    assert 'return "🟩"' in script.text
    assert 'return "🟨"' in script.text
    assert 'return "⬜"' in script.text
    assert "navigator.clipboard.writeText" in script.text
    assert "van par" in script.text


def test_game_date_uses_the_requested_time_zone() -> None:
    instant = datetime(2026, 7, 20, 1, 0, tzinfo=timezone.utc)

    assert main.game_date_at(instant, ZoneInfo("Europe/Amsterdam")) == date(
        2026, 7, 20
    )
    assert main.game_date_at(instant, ZoneInfo("America/New_York")) == date(
        2026, 7, 19
    )


def test_invalid_client_time_zone_is_rejected() -> None:
    response = TestClient(main.app).get(
        "/game", headers={"X-Client-Time-Zone": "Not/A-Time-Zone"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "De tijdzone van je browser wordt niet herkend."


def test_game_response_is_not_cached(monkeypatch) -> None:
    game = DailyWordGame(TEST_WORDS, "bbbb", today=lambda: date(2026, 7, 19))
    monkeypatch.setattr(main, "game", game)

    response = TestClient(main.app).get("/game")

    assert response.headers["cache-control"] == "no-store"


def test_game_api_tracks_a_user_until_completion(monkeypatch) -> None:
    game = DailyWordGame(TEST_WORDS, "bbbb", today=lambda: date(2026, 7, 19))
    monkeypatch.setattr(main, "game", game)
    client = TestClient(main.app)

    initial_response = client.get("/game")
    assert initial_response.status_code == 200
    user_id = UUID(client.cookies[main.USER_COOKIE_NAME])
    assert user_id.version == 4
    initial_state = initial_response.json()
    assert initial_state["attempts"] == 0
    assert initial_state["minimum_attempts"] is None
    assert initial_state["completed"] is False

    moves = ladder_moves(initial_state["start_word"])
    invalid_response = client.post("/game/entries", json={"word": moves[1]})
    assert invalid_response.status_code == 400
    assert invalid_response.json()["detail"].startswith("Verander precies één letter")

    detour = [moves[0], initial_state["start_word"]]
    for move in [*detour, *moves, "bbbb"]:
        response = client.post("/game/entries", json={"word": move})
        assert response.status_code == 200

    completed_state = response.json()
    assert completed_state["attempts"] == 6
    assert len(completed_state["entries"]) == 6
    assert completed_state["minimum_attempts"] == 4
    assert completed_state["completed"] is True
    assert completed_state["current_word"] == "BBBB"

    completed_response = client.post("/game/entries", json={"word": moves[-1]})
    assert completed_response.status_code == 409


def test_game_api_replaces_an_invalid_user_cookie(monkeypatch) -> None:
    game = DailyWordGame(TEST_WORDS, "bbbb", today=lambda: date(2026, 7, 19))
    monkeypatch.setattr(main, "game", game)
    client = TestClient(main.app)
    client.cookies.set(main.USER_COOKIE_NAME, "guessable-user-name")

    response = client.get("/game")

    assert response.status_code == 200
    replacement_user_id = UUID(response.cookies[main.USER_COOKIE_NAME])
    assert replacement_user_id.version == 4


def test_game_api_cookie_restores_user_state(monkeypatch) -> None:
    game = DailyWordGame(TEST_WORDS, "bbbb", today=lambda: date(2026, 7, 19))
    monkeypatch.setattr(main, "game", game)
    client = TestClient(main.app)
    initial_state = client.get("/game").json()
    first_move = ladder_moves(initial_state["start_word"])[0]
    client.post("/game/entries", json={"word": first_move})

    returned_state = client.get("/game").json()

    assert returned_state["attempts"] == 1
    assert returned_state["current_word"] == first_move.upper()


def test_development_cheat_completes_the_shortest_route(monkeypatch) -> None:
    monkeypatch.setenv("POEPER_ENV", "development")
    game = DailyWordGame(TEST_WORDS, "bbbb", today=lambda: date(2026, 7, 19))
    monkeypatch.setattr(main, "game", game)
    client = TestClient(main.app)

    completed_state = client.post("/game/cheat").json()

    assert completed_state["completed"] is True
    assert completed_state["attempts"] == completed_state["minimum_attempts"]
    assert completed_state["current_word"] == "BBBB"


def test_development_cheat_is_unavailable_in_production(monkeypatch) -> None:
    monkeypatch.setenv("POEPER_ENV", "production")
    client = TestClient(main.app)

    response = client.post("/game/cheat")

    assert response.status_code == 404
