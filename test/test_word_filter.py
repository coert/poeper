import pytest

from libs.word_filter import (
    has_no_letters_in_same_position,
    is_one_character_different,
    select_four_letter_words,
)


@pytest.mark.parametrize(
    ("start_word", "target_word", "expected"),
    [
        ("HUIS", "mOuT", True),
        ("huis", "muts", False),
        ("huis", "HOND", False),
        ("kat", "kast", False),
    ],
)
def test_has_no_letters_in_same_position(
    start_word: str, target_word: str, expected: bool
) -> None:
    assert has_no_letters_in_same_position(start_word, target_word) is expected


def test_select_four_letter_words_returns_only_four_letter_words() -> None:
    words = [
        "huis",
        "kat",
        "tafel",
        "café",
        "a4bc",
        "ab-c",
        " abc",
        "boom",
        "huis",
        "brrr",
        "BRTV",
        "lynx",
        "VIII",
        "xxiv",
        "mild",
        "CAFE",
        "PoEp",
        "Tijn",
        "Nina",
        "Mars",
        "mars",
    ]

    assert select_four_letter_words(words, target_word="poep") == [
        "huis",
        "cafe",
        "boom",
        "lynx",
        "mild",
        "mars",
    ]


@pytest.mark.parametrize(
    ("first_word", "second_word", "expected"),
    [
        ("huis", "muis", True),
        ("huis", "huil", True),
        ("huis", "huis", False),
        ("huis", "haas", False),
        ("kat", "kast", False),
        ("", "", False),
    ],
)
def test_is_one_character_different(
    first_word: str, second_word: str, expected: bool
) -> None:
    assert is_one_character_different(first_word, second_word) is expected
