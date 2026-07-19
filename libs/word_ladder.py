"""Find shortest routes between words."""

from collections import defaultdict, deque
from random import choice


def choose_reachable_word(
    words: list[str], target_word: str, max_steps: int = 5
) -> str:
    """Randomly choose a word that can reach the target within ``max_steps``."""
    candidates = list(reachable_words_with_steps(words, target_word, max_steps))
    if not candidates:
        raise ValueError(f"no words can reach {target_word!r} within {max_steps} steps")

    return choice(candidates)


def reachable_words_with_steps(
    words: list[str], target_word: str, max_steps: int = 5
) -> dict[str, int]:
    """Return words reachable from the target and their shortest distances."""
    if max_steps < 1:
        raise ValueError("max_steps must be at least 1")

    target = target_word.casefold()
    available_words: dict[str, str] = {}
    for word in words:
        normalized_word = word.casefold()
        if len(normalized_word) == len(target) and normalized_word != target:
            available_words.setdefault(normalized_word, word)

    search_words = set(available_words)
    search_words.add(target)

    words_by_pattern: dict[str, list[str]] = defaultdict(list)
    for word in search_words:
        for index in range(len(word)):
            pattern = f"{word[:index]}*{word[index + 1:]}"
            words_by_pattern[pattern].append(word)

    queue = deque([(target, 0)])
    visited = {target}
    distances: dict[str, int] = {}

    while queue:
        word, steps = queue.popleft()
        if steps == max_steps:
            continue

        for index in range(len(word)):
            pattern = f"{word[:index]}*{word[index + 1:]}"
            for next_word in words_by_pattern.pop(pattern, []):
                if next_word in visited:
                    continue
                visited.add(next_word)
                next_steps = steps + 1
                distances[next_word] = next_steps
                queue.append((next_word, next_steps))

    return {
        original_word: distances[normalized_word]
        for normalized_word, original_word in available_words.items()
        if normalized_word in distances
    }


def minimum_letter_changes(
    words: list[str], start_word: str, target_word: str
) -> int | None:
    """Return the fewest one-letter changes needed to reach the target word.

    The start and intermediate words must occur in ``words``; the target may
    be excluded from it. Comparisons are case-insensitive. ``None`` is returned
    when no route exists.
    """
    start = start_word.casefold()
    target = target_word.casefold()

    if start == target:
        return 0
    if len(start) != len(target):
        return None

    available_words = {
        word.casefold() for word in words if len(word.casefold()) == len(start)
    }
    if start not in available_words:
        return None
    available_words.add(target)

    words_by_pattern: dict[str, list[str]] = defaultdict(list)
    for word in available_words:
        for index in range(len(word)):
            pattern = f"{word[:index]}*{word[index + 1:]}"
            words_by_pattern[pattern].append(word)

    queue = deque([(start, 0)])
    visited = {start}

    while queue:
        word, changes = queue.popleft()
        for index in range(len(word)):
            pattern = f"{word[:index]}*{word[index + 1:]}"
            for next_word in words_by_pattern.pop(pattern, []):
                if next_word == target:
                    return changes + 1
                if next_word not in visited:
                    visited.add(next_word)
                    queue.append((next_word, changes + 1))

    return None


def shortest_word_ladder(
    words: list[str], start_word: str, target_word: str
) -> list[str] | None:
    """Return a shortest word ladder, including its start and target words."""
    start = start_word.casefold()
    target = target_word.casefold()

    if start == target:
        return [start]
    if len(start) != len(target):
        return None

    available_words = {
        word.casefold() for word in words if len(word.casefold()) == len(start)
    }
    if start not in available_words:
        return None
    available_words.add(target)

    words_by_pattern: dict[str, list[str]] = defaultdict(list)
    for word in available_words:
        for index in range(len(word)):
            pattern = f"{word[:index]}*{word[index + 1:]}"
            words_by_pattern[pattern].append(word)

    queue = deque([start])
    previous_words: dict[str, str | None] = {start: None}

    while queue:
        word = queue.popleft()
        for index in range(len(word)):
            pattern = f"{word[:index]}*{word[index + 1:]}"
            for next_word in words_by_pattern.pop(pattern, []):
                if next_word in previous_words:
                    continue
                previous_words[next_word] = word
                if next_word == target:
                    ladder = [target]
                    while previous_words[ladder[-1]] is not None:
                        ladder.append(previous_words[ladder[-1]])
                    return list(reversed(ladder))
                queue.append(next_word)

    return None


def has_minimum_letter_changes(
    words: list[str],
    start_word: str,
    target_word: str,
    minimum_steps: int = 3,
) -> bool:
    """Return whether the shortest route requires at least ``minimum_steps``."""
    if minimum_steps < 0:
        raise ValueError("minimum_steps cannot be negative")

    required_steps = minimum_letter_changes(words, start_word, target_word)
    return required_steps is not None and required_steps >= minimum_steps
