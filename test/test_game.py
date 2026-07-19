from datetime import date
import json
from threading import Event

import pytest

from libs.common_word import CommonWordAssessment
from libs.game import DailyWordGame, GameAlreadyCompletedError, InvalidMoveError

_TEST_START_WORDS = [
    f"{first}{second}aa"
    for first in "acdefghjkl"
    for second in "mnopqrstuv"
]
_TEST_WORD_SET = {"bbbb"}
for _start_word in _TEST_START_WORDS:
    _TEST_WORD_SET.update(
        {
            _start_word,
            f"b{_start_word[1:]}",
            f"bb{_start_word[2:]}",
            f"bbb{_start_word[3]}",
        }
    )
TEST_WORDS = sorted(_TEST_WORD_SET)


def ladder_moves(start_word: str) -> list[str]:
    word = start_word.casefold()
    return [f"b{word[1:]}", f"bb{word[2:]}", f"bbb{word[3]}"]


def test_daily_start_is_shared_and_changes_the_next_day() -> None:
    current_day = date(2026, 7, 19)
    game = DailyWordGame(TEST_WORDS, "BBBB", today=lambda: current_day)

    first_user = game.get_state("user-one")
    second_user = game.get_state("user-two")
    next_start = game.daily_start_word(date(2026, 7, 20)).upper()

    assert first_user.start_word == second_user.start_word
    assert first_user.start_word != next_start


def test_game_tracks_valid_moves_and_completion() -> None:
    game = DailyWordGame(TEST_WORDS, "bbbb", today=lambda: date(2026, 7, 19))
    state = game.get_state("player")
    moves = ladder_moves(state.start_word)

    with pytest.raises(InvalidMoveError, match="Verander precies één letter"):
        game.submit_word("player", moves[1])
    assert game.get_state("player").attempts == 0

    for expected_attempts, move in enumerate([*moves, "BBBB"], start=1):
        state = game.submit_word("player", move.upper())
        assert state.attempts == expected_attempts

    assert state.completed is True
    assert state.current_word == "BBBB"
    assert state.entries == tuple(move.upper() for move in [*moves, "BBBB"])
    assert state.minimum_attempts == 4
    with pytest.raises(GameAlreadyCompletedError):
        game.submit_word("player", moves[-1])


def test_game_rejects_words_outside_the_filtered_list() -> None:
    game = DailyWordGame(TEST_WORDS, "bbbb", today=lambda: date(2026, 7, 19))

    with pytest.raises(InvalidMoveError, match="toegestane woordenlijst"):
        game.submit_word("player", "zzzz")


def test_user_state_resets_on_a_new_day() -> None:
    current_day = date(2026, 7, 19)
    game = DailyWordGame(TEST_WORDS, "bbbb", today=lambda: current_day)
    original_state = game.get_state("player")
    game.submit_word("player", ladder_moves(original_state.start_word)[0])

    current_day = date(2026, 7, 20)
    reset_state = game.get_state("player")

    assert reset_state.attempts == 0
    assert reset_state.completed is False
    assert reset_state.current_word == reset_state.start_word
    assert reset_state.entries == ()
    assert reset_state.start_word != original_state.start_word


def test_future_daily_word_can_be_rotated_and_persisted(tmp_path) -> None:
    schedule_path = tmp_path / "daily-words.json"
    today = date(2026, 7, 19)
    game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: today,
        schedule_path=schedule_path,
    )
    future_day = date(2026, 7, 20)
    original_word = game.daily_start_word(future_day)

    rotated = game.rotate_daily_word(future_day)

    assert rotated.word.casefold() != original_word
    assert rotated.overridden is True
    restored_game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: today,
        schedule_path=schedule_path,
    )
    assert restored_game.daily_start_word(future_day).upper() == rotated.word


def test_upcoming_and_played_words_never_repeat(tmp_path) -> None:
    current_day = date(2026, 7, 19)
    game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: current_day,
        schedule_path=tmp_path / "daily-words.json",
    )
    played_word = game.get_state("player").start_word

    current_day = date(2026, 7, 20)
    schedule = game.upcoming_words(30)
    scheduled_words = [item.word for item in schedule]

    assert len(scheduled_words) == len(set(scheduled_words))
    assert played_word not in scheduled_words


def test_today_word_cannot_be_rotated() -> None:
    today = date(2026, 7, 19)
    game = DailyWordGame(TEST_WORDS, "bbbb", today=lambda: today)

    with pytest.raises(ValueError, match="toekomstige dagwoorden"):
        game.rotate_daily_word(today)


def test_uncommon_future_word_is_skipped_and_next_candidate_is_retested() -> None:
    assessed_words: list[str] = []

    def assess(word: str) -> CommonWordAssessment:
        assessed_words.append(word)
        return CommonWordAssessment(
            common=len(assessed_words) > 1,
            reason="testbeoordeling",
        )

    game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: date(2026, 7, 19),
        word_assessor=assess,
    )

    assert game.upcoming_words(1)[0].common is None
    game.verify_upcoming_words(1)
    scheduled = game.upcoming_words(1)[0]

    assert len(assessed_words) == 2
    assert scheduled.word.casefold() == assessed_words[1]
    assert scheduled.common is True


def test_unreachable_assessor_warns_but_keeps_the_word() -> None:
    warning = "Taalmodel niet bereikbaar; woord zonder controle ingepland."

    def assess(word: str) -> CommonWordAssessment:
        return CommonWordAssessment(None, "Geen beoordeling.", warning)

    game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: date(2026, 7, 19),
        word_assessor=assess,
    )

    game.upcoming_words(1)
    game.verify_upcoming_words(1)
    scheduled = game.upcoming_words(1)[0]

    assert scheduled.common is None
    assert scheduled.warning == warning


def test_word_verification_runs_in_a_daemon_thread() -> None:
    assessment_started = Event()
    allow_assessment_to_finish = Event()

    def assess(word: str) -> CommonWordAssessment:
        assessment_started.set()
        allow_assessment_to_finish.wait(timeout=2)
        return CommonWordAssessment(True, "Gangbaar woord.")

    game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: date(2026, 7, 19),
        word_assessor=assess,
    )
    game.upcoming_words(1)

    assert game.start_word_verification(1) is True
    assert assessment_started.wait(timeout=1)
    assert game._verification_thread is not None
    assert game._verification_thread.daemon is True
    assert game.upcoming_words(1)[0].common is None

    allow_assessment_to_finish.set()
    game._verification_thread.join(timeout=1)
    assert game.upcoming_words(1)[0].common is True


def test_old_assessment_cache_is_invalidated(tmp_path) -> None:
    schedule_path = tmp_path / "daily-words.json"
    today = date(2026, 7, 19)
    game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: today,
        schedule_path=schedule_path,
    )
    scheduled = game.upcoming_words(1)[0]
    stored_schedule = json.loads(schedule_path.read_text())
    stored_schedule["assessment_version"] = 1
    stored_schedule["assessments"] = {scheduled.word.casefold(): False}
    schedule_path.write_text(json.dumps(stored_schedule))

    restored_game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: today,
        schedule_path=schedule_path,
    )

    restored = restored_game.upcoming_words(1)[0]
    assert restored.word == scheduled.word
    assert restored.common is None
