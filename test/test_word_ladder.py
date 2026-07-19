import pytest

from libs import word_ladder
from libs.word_ladder import (
    choose_reachable_word,
    has_minimum_letter_changes,
    minimum_letter_changes,
)


def test_has_minimum_letter_changes_defaults_to_three() -> None:
    words = ["HuIs", "muis", "MuTs"]

    assert has_minimum_letter_changes(words, "HUIS", "PUTS") is True
    assert has_minimum_letter_changes(words, "HUIS", "PUTS", minimum_steps=4) is False


def test_has_minimum_letter_changes_returns_false_when_unreachable() -> None:
    assert has_minimum_letter_changes(["huis", "boom"], "huis", "poep") is False


def test_has_minimum_letter_changes_rejects_negative_minimum() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        has_minimum_letter_changes(["huis"], "huis", "huis", minimum_steps=-1)


def test_choose_reachable_word_only_chooses_words_within_max_steps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates: list[str] = []

    def choose_first(words: list[str]) -> str:
        candidates.extend(words)
        return words[0]

    monkeypatch.setattr(word_ladder, "choice", choose_first)

    selected_word = choose_reachable_word(
        ["HUIS", "muis", "MuTs", "puts"], "PUTS", max_steps=2
    )

    assert selected_word == "muis"
    assert candidates == ["muis", "MuTs"]


def test_choose_reachable_word_defaults_to_five_steps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(word_ladder, "choice", lambda words: words[0])

    assert choose_reachable_word(["huis", "muis", "muts", "puts"], "puts") == "huis"


@pytest.mark.parametrize("max_steps", [0, -1])
def test_choose_reachable_word_requires_positive_max_steps(max_steps: int) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        choose_reachable_word(["huis"], "muis", max_steps)


def test_choose_reachable_word_raises_when_no_word_is_reachable() -> None:
    with pytest.raises(ValueError, match="no words can reach"):
        choose_reachable_word(["huis", "boom"], "poep")


@pytest.mark.parametrize(
    ("words", "start_word", "target_word", "expected"),
    [
        (["HuIs", "MUIS", "MuTs", "pUtS"], "HUIS", "PUTS", 3),
        (["huis", "muis"], "huis", "muts", 2),
        (["huis"], "huis", "HUIS", 0),
        (["huis", "muis", "puts"], "huis", "puts", None),
        (["huis", "muis"], "huis", "poep", None),
        (["kat", "kast"], "kat", "kast", None),
    ],
)
def test_minimum_letter_changes(
    words: list[str],
    start_word: str,
    target_word: str,
    expected: int | None,
) -> None:
    assert minimum_letter_changes(words, start_word, target_word) == expected
