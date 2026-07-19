from datetime import date
from uuid import UUID

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
    assert stylesheet.status_code == 200
    assert script.status_code == 200
    assert 'requestGame("game")' in script.text
    assert "Die boodschap kwam er vlot uit." in script.text
    assert "Je hebt ’m eruit geperst." in script.text
    assert "launchPoopExplosion" in script.text
    assert 'context.fillText("💩", 0, 0)' in script.text


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
