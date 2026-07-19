from datetime import date
import json
from pathlib import Path
from threading import Event

import pytest

from libs.common_word import CommonWordAssessment
from libs.game import (
    SELECTION_VERSION,
    DailyWordGame,
    GameAlreadyCompletedError,
    InvalidMoveError,
)
from libs.word_filter import select_four_letter_words

_TEST_START_WORDS = [
    f"{first}{second}aa" for first in "acdefghjkl" for second in "mnopqrstuv"
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


def test_curated_start_words_do_not_restrict_intermediate_moves() -> None:
    curated_starts = _TEST_START_WORDS[:2]
    game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        start_words=curated_starts,
        today=lambda: date(2026, 7, 19),
    )

    state = game.get_state("player")
    intermediate_word = ladder_moves(state.start_word)[0]
    moved_state = game.submit_word("player", intermediate_word)

    assert state.start_word.casefold() in curated_starts
    assert intermediate_word not in curated_starts
    assert moved_state.current_word == intermediate_word.upper()


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


def test_future_daily_word_is_randomly_rotated_and_persisted(
    monkeypatch, tmp_path
) -> None:
    schedule_path = tmp_path / "daily-words.json"
    today = date(2026, 7, 19)
    game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: today,
        schedule_path=schedule_path,
    )
    future_day = date(2026, 7, 20)
    game.upcoming_words(30)
    original_word = game.daily_start_word(future_day)
    used_words = set(game._played_words.values()) | {
        word
        for scheduled_date, word in game._scheduled_words.items()
        if scheduled_date != future_day.isoformat()
    }
    candidates = [
        candidate
        for candidate in game._eligible_words
        if candidate != original_word
        and candidate not in used_words
        and game._assessments.get(candidate) is not False
    ]
    expected_total_weight = sum(game._minimum_attempts[word] for word in candidates)
    offered_totals: list[int] = []

    def pick_last_ticket(total_weight: int) -> int:
        offered_totals.append(total_weight)
        return total_weight - 1

    monkeypatch.setattr("libs.game.secrets.randbelow", pick_last_ticket)

    rotated = game.rotate_daily_word(future_day)

    assert offered_totals == [expected_total_weight]
    assert rotated.word.casefold() == candidates[-1]
    assert rotated.word.casefold() != original_word
    assert rotated.overridden is True
    restored_game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: today,
        schedule_path=schedule_path,
    )
    assert restored_game.daily_start_word(future_day).upper() == rotated.word


def test_future_word_can_be_blacklisted_persisted_and_removed_from_play(tmp_path) -> None:
    schedule_path = tmp_path / "daily-words.json"
    today = date(2026, 7, 19)
    future_day = date(2026, 7, 20)
    game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: today,
        schedule_path=schedule_path,
    )
    blocked_word = game.daily_start_word(future_day)

    replacement = game.blacklist_daily_word(future_day)

    assert replacement.word.casefold() != blocked_word
    assert blocked_word not in game.words
    with pytest.raises(InvalidMoveError, match="zwarte lijst"):
        game.submit_word("player", blocked_word)

    stored_schedule = json.loads(schedule_path.read_text())
    assert blocked_word in stored_schedule["blacklist"]
    assert blocked_word not in stored_schedule["scheduled"].values()

    restored_game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: today,
        schedule_path=schedule_path,
    )
    assert blocked_word not in restored_game.words
    assert restored_game.daily_start_word(future_day).upper() == replacement.word


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


def test_weighted_candidate_gives_harder_words_larger_ticket_ranges() -> None:
    game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: date(2026, 7, 19),
    )
    easier_word, harder_word = game._eligible_words[:2]
    game._minimum_attempts[easier_word] = 4
    game._minimum_attempts[harder_word] = 8

    assert game._weighted_candidate([easier_word, harder_word], 0) == easier_word
    assert game._weighted_candidate([easier_word, harder_word], 3) == easier_word
    assert game._weighted_candidate([easier_word, harder_word], 4) == harder_word
    assert game._weighted_candidate([easier_word, harder_word], 11) == harder_word


def test_curated_eight_step_schedule_contains_harder_games() -> None:
    project_root = Path(__file__).parent.parent
    words = (project_root / "assets/wordlist.txt").read_text().splitlines()
    curated_words = (project_root / "assets/basiswoorden.txt").read_text().splitlines()
    game = DailyWordGame(
        words,
        "poep",
        start_words=curated_words,
        maximum_steps=8,
        today=lambda: date(2026, 7, 19),
    )

    first_pick = game._next_unused_word(date(2026, 7, 20))
    schedule = game.upcoming_words(30)
    curated_four_letter_words = set(select_four_letter_words(curated_words, "poep"))
    difficulties = [item.minimum_attempts for item in schedule]

    assert first_pick == schedule[0].word.casefold()
    assert set(game._minimum_attempts.values()) == {4, 5, 6, 7, 8}
    assert set(game._eligible_words) <= curated_four_letter_words
    assert all(4 <= difficulty <= 8 for difficulty in difficulties)
    assert any(difficulty >= 6 for difficulty in difficulties)


def test_selection_version_regenerates_future_words_but_preserves_history(
    tmp_path,
) -> None:
    schedule_path = tmp_path / "daily-words.json"
    today = date(2026, 7, 19)
    game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: today,
        schedule_path=schedule_path,
    )
    played_word = game.daily_start_word(today)
    game.daily_start_word(date(2026, 7, 20))
    metadata_word = ladder_moves(played_word)[0]
    stored_schedule = json.loads(schedule_path.read_text())
    stored_schedule["selection_version"] = SELECTION_VERSION - 1
    stored_schedule["overridden"] = ["2026-07-20"]
    stored_schedule["assessments"] = {metadata_word: True}
    stored_schedule["assessment_warnings"] = {metadata_word: "Stored warning"}
    schedule_path.write_text(json.dumps(stored_schedule))

    restored_game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: today,
        schedule_path=schedule_path,
    )

    assert restored_game._scheduled_words == {}
    assert restored_game._played_words == {today.isoformat(): played_word}
    assert restored_game._assessments == {metadata_word: True}
    assert restored_game._assessment_warnings == {metadata_word: "Stored warning"}
    assert restored_game._overridden_dates == set()

    regenerated = restored_game.upcoming_words(30)
    persisted = json.loads(schedule_path.read_text())

    assert len({item.word for item in regenerated}) == 30
    assert persisted["selection_version"] == SELECTION_VERSION
    assert persisted["played"] == {today.isoformat(): played_word}
    assert persisted["overridden"] == []


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


def test_warning_assessments_are_retried_on_later_verification_passes() -> None:
    calls: list[str] = []

    def assess(word: str) -> CommonWordAssessment:
        calls.append(word)
        if len(calls) == 1:
            return CommonWordAssessment(
                common=None,
                reason="Geen beoordeling.",
                warning="Taalmodel niet bereikbaar; woord zonder controle ingepland.",
            )
        return CommonWordAssessment(common=True, reason="Gangbaar woord.")

    game = DailyWordGame(
        TEST_WORDS,
        "bbbb",
        today=lambda: date(2026, 7, 19),
        word_assessor=assess,
    )

    game.upcoming_words(1)
    game.verify_upcoming_words(1)
    first_pass = game.upcoming_words(1)[0]
    assert first_pass.common is None
    assert first_pass.warning is not None

    game.verify_upcoming_words(1)
    second_pass = game.upcoming_words(1)[0]

    assert len(calls) == 2
    assert second_pass.common is True
    assert second_pass.warning is None


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
