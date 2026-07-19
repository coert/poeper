"""Functions for filtering word lists."""

import re
import unicodedata

_ROMAN_NUMERAL_PATTERN = re.compile(
    r"M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})",
    re.IGNORECASE,
)


def _contains_vowel(word: str) -> bool:
    normalized_word = unicodedata.normalize("NFD", word.casefold())
    return any(character in "aeiouy" for character in normalized_word)


def _is_roman_numeral(word: str) -> bool:
    return bool(word) and _ROMAN_NUMERAL_PATTERN.fullmatch(word) is not None


def _slugify(word: str) -> str:
    normalized_word = unicodedata.normalize("NFKD", word.casefold())
    return "".join(
        character
        for character in normalized_word
        if character.isascii() and character.isalpha()
    )


def select_four_letter_words(words: list[str], target_word: str) -> list[str]:
    """Return unique four-letter slugs, excluding the supplied target word."""
    target_slug = _slugify(target_word)
    lowercase_slugs = {
        _slugify(word)
        for word in words
        if word and word[0].islower()
    }
    selected_words: list[str] = []
    seen: set[str] = set()

    for word in words:
        if len(word) != 4 or not word.isalpha():
            continue

        slug = _slugify(word)
        if (
            len(slug) != 4
            or not _contains_vowel(slug)
            or _is_roman_numeral(slug)
            or (word[0].isupper() and slug not in lowercase_slugs)
            or slug == target_slug
            or slug in seen
        ):
            continue

        seen.add(slug)
        selected_words.append(slug)

    return selected_words


def is_one_character_different(first_word: str, second_word: str) -> bool:
    """Return whether two equally long words differ at exactly one position."""
    if len(first_word) != len(second_word):
        return False

    return sum(first != second for first, second in zip(first_word, second_word)) == 1


def has_no_letters_in_same_position(start_word: str, target_word: str) -> bool:
    """Return whether equal-length words have no matching character positions."""
    start = start_word.casefold()
    target = target_word.casefold()
    if len(start) != len(target):
        return False

    return all(
        start_letter != target_letter
        for start_letter, target_letter in zip(start, target)
    )
