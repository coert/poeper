from datetime import date
import sqlite3

from libs.game import DailyWordGame
from libs.performance import PerformanceStore
from test.test_game import TEST_WORDS, ladder_moves


def solve_game(
    game: DailyWordGame,
    user_id: str,
    day: date,
    *, detour: bool = False,
) -> None:
    state = game.get_state(user_id, day)
    moves = ladder_moves(state.start_word)
    if detour:
        game.submit_word(user_id, moves[0], day)
        game.submit_word(user_id, state.start_word, day)
    for word in [*moves, "bbbb"]:
        game.submit_word(user_id, word, day)


def test_performance_aggregates_unique_players_and_solver_results(tmp_path) -> None:
    current_day = date(2026, 7, 21)
    game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: current_day,
        performance_path=tmp_path / "performance.sqlite3",
    )
    first_day = date(2026, 7, 19)
    second_day = date(2026, 7, 20)

    incomplete = game.get_state("incomplete", first_day)
    first_moves = ladder_moves(incomplete.start_word)
    game.submit_word("incomplete", first_moves[0], first_day)
    game.submit_word("incomplete", first_moves[1], first_day)
    solve_game(game, "shortest", first_day)
    solve_game(game, "detour", first_day, detour=True)

    second_state = game.get_state("second-day-player", second_day)
    game.submit_word(
        "second-day-player",
        ladder_moves(second_state.start_word)[0],
        second_day,
    )

    results = game.performance_results()

    assert [result.date for result in results] == [second_day, first_day]
    assert results[0].players == 1
    assert results[0].solved == 0
    assert results[0].average_steps is None
    assert results[0].average_above_par is None
    assert results[1].players == 3
    assert results[1].solved == 2
    assert results[1].average_steps == 5
    assert results[1].average_above_par == 1


def test_performance_excludes_today_and_future_dates(tmp_path) -> None:
    current_day = date(2026, 7, 20)
    game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: current_day,
        performance_path=tmp_path / "performance.sqlite3",
    )

    for offset_day, user in [
        (date(2026, 7, 19), "past"),
        (date(2026, 7, 20), "today"),
        (date(2026, 7, 21), "future"),
    ]:
        state = game.get_state(user, offset_day)
        game.submit_word(user, ladder_moves(state.start_word)[0], offset_day)

    assert [result.date for result in game.performance_results()] == [
        date(2026, 7, 19)
    ]


def test_completed_performance_survives_reopening_and_cannot_be_downgraded(
    tmp_path,
) -> None:
    path = tmp_path / "performance.sqlite3"
    played_day = date(2026, 7, 19)
    PerformanceStore(path).record(played_day, "user-id", 6, 4, True)

    reopened_store = PerformanceStore(path)
    reopened_store.record(played_day, "user-id", 1, 4, False)
    result = reopened_store.results_before(date(2026, 7, 20))[0]

    assert result.players == 1
    assert result.solved == 1
    assert result.average_steps == 6
    assert result.average_above_par == 2
    with sqlite3.connect(path) as connection:
        stored_key = connection.execute(
            "SELECT player_key FROM daily_player_performance"
        ).fetchone()[0]
    assert stored_key != "user-id"
    assert len(stored_key) == 64
