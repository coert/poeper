"""State and rules for the daily word-ladder game."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date as Date, timedelta
from hashlib import sha256
import json
import logging
from pathlib import Path
from threading import RLock, Thread
import unicodedata

from .common_word import ASSESSMENT_VERSION, CommonWordAssessment
from .word_filter import (
    has_no_letters_in_same_position,
    is_one_character_different,
    select_four_letter_words,
)
from .word_ladder import reachable_words_with_steps, shortest_word_ladder

logger = logging.getLogger(__name__)


class InvalidMoveError(ValueError):
    """Raised when a submitted word is not a valid next move."""


class GameAlreadyCompletedError(ValueError):
    """Raised when a user submits a move after completing today's game."""


@dataclass(frozen=True, slots=True)
class GameState:
    date: Date
    start_word: str
    target_word: str
    current_word: str
    entries: tuple[str, ...]
    attempts: int
    minimum_attempts: int | None
    completed: bool


@dataclass(frozen=True, slots=True)
class ScheduledWord:
    date: Date
    word: str
    minimum_attempts: int
    overridden: bool
    common: bool | None
    warning: str | None


@dataclass(slots=True)
class _UserState:
    date: Date
    start_word: str
    current_word: str
    entries: list[str] = field(default_factory=list)
    attempts: int = 0
    completed: bool = False


def _normalize_word(word: str) -> str:
    normalized_word = unicodedata.normalize("NFKD", word.strip().casefold())
    return "".join(
        character
        for character in normalized_word
        if character.isascii() and character.isalpha()
    )


class DailyWordGame:
    """Manage deterministic daily games and per-user progress in memory."""

    def __init__(
        self,
        words: list[str],
        target_word: str,
        *,
        minimum_steps: int = 3,
        maximum_steps: int = 5,
        today: Callable[[], Date] = Date.today,
        schedule_path: Path | None = None,
        word_assessor: Callable[[str], CommonWordAssessment] | None = None,
    ) -> None:
        if minimum_steps < 1 or maximum_steps < minimum_steps:
            raise ValueError("step limits must satisfy 1 <= minimum <= maximum")

        self.target_word = _normalize_word(target_word)
        if not self.target_word:
            raise ValueError("target_word must contain letters")

        self.words = select_four_letter_words(words, self.target_word)
        self._allowed_words = set(self.words)
        distances = reachable_words_with_steps(
            self.words, self.target_word, maximum_steps
        )
        eligible_words = [
            word
            for word, steps in distances.items()
            if steps >= minimum_steps
            and has_no_letters_in_same_position(word, self.target_word)
        ]
        if len(eligible_words) < 2:
            raise ValueError("at least two eligible start words are required")

        self._minimum_attempts = {word: distances[word] for word in eligible_words}
        self._eligible_words = sorted(
            eligible_words,
            key=lambda word: sha256(f"{self.target_word}:{word}".encode()).digest(),
        )
        self._today = today
        self._user_states: dict[str, _UserState] = {}
        self._lock = RLock()
        self._schedule_path = schedule_path
        self._word_assessor = word_assessor
        (
            self._scheduled_words,
            self._played_words,
            self._overridden_dates,
            self._assessments,
            self._assessment_warnings,
        ) = self._load_schedule()
        self._schedule_dirty = False
        self._verification_thread: Thread | None = None

    def daily_start_word(self, day: Date | None = None) -> str:
        """Return the shared start word for a date."""
        selected_day = day or self._today()
        with self._lock:
            schedule_changed = self._archive_played_words()
            day_key = selected_day.isoformat()
            if selected_day <= self._today():
                word = self._played_words.get(day_key)
                if word is None:
                    word = self._scheduled_words.pop(day_key, None)
                    if word is None:
                        word = self._next_unused_word(selected_day)
                    self._played_words[day_key] = word
                    schedule_changed = True
            else:
                word, word_was_added = self._ensure_scheduled(selected_day)
                schedule_changed = schedule_changed or word_was_added

            if schedule_changed or self._schedule_dirty:
                self._save_schedule()
            return word

    def upcoming_words(self, days: int = 14) -> list[ScheduledWord]:
        """Return the scheduled start words after today."""
        if not 1 <= days <= 30:
            raise ValueError("Het aantal dagen moet tussen 1 en 30 liggen.")

        with self._lock:
            schedule_changed = self._archive_played_words()
            first_day = self._today() + timedelta(days=1)
            scheduled_days = [
                first_day + timedelta(days=offset) for offset in range(days)
            ]
            for scheduled_day in scheduled_days:
                _, word_was_added = self._ensure_scheduled(scheduled_day)
                schedule_changed = schedule_changed or word_was_added
            if schedule_changed or self._schedule_dirty:
                self._save_schedule()
            return [self._scheduled_word(day) for day in scheduled_days]

    def rotate_daily_word(self, day: Date) -> ScheduledWord:
        """Replace a future day's word with the next eligible candidate."""
        if day <= self._today():
            raise ValueError("Alleen toekomstige dagwoorden kunnen worden gewisseld.")

        with self._lock:
            self._archive_played_words()
            first_day = self._today() + timedelta(days=1)
            for offset in range(30):
                self._ensure_scheduled(first_day + timedelta(days=offset))

            day_key = day.isoformat()
            current_word, _ = self._ensure_scheduled(day)
            current_index = self._eligible_words.index(current_word)
            used_words = set(self._played_words.values()) | {
                word
                for scheduled_date, word in self._scheduled_words.items()
                if scheduled_date != day_key
            }
            for offset in range(1, len(self._eligible_words)):
                candidate_index = (current_index + offset) % len(self._eligible_words)
                candidate = self._eligible_words[candidate_index]
                if (
                    candidate not in used_words
                    and self._assessments.get(candidate) is not False
                ):
                    self._scheduled_words[day_key] = candidate
                    self._overridden_dates.add(day_key)
                    self._save_schedule()
                    return self._scheduled_word(day)

        raise ValueError("Er is geen ongebruikt alternatief dagwoord beschikbaar.")

    def start_word_verification(self, days: int = 30) -> bool:
        """Start non-blocking verification in a daemon thread if not running."""
        if not 1 <= days <= 30:
            raise ValueError("Het aantal dagen moet tussen 1 en 30 liggen.")
        if self._word_assessor is None:
            return False

        with self._lock:
            if (
                self._verification_thread is not None
                and self._verification_thread.is_alive()
            ):
                return False
            self._verification_thread = Thread(
                target=self._verify_words_safely,
                args=(days,),
                name="poeper-word-verification",
                daemon=True,
            )
            self._verification_thread.start()
            return True

    def verify_upcoming_words(self, days: int = 30) -> None:
        """Verify scheduled words, replacing uncommon ones until all are checked."""
        if not 1 <= days <= 30:
            raise ValueError("Het aantal dagen moet tussen 1 en 30 liggen.")
        if self._word_assessor is None:
            return

        first_day = self._today() + timedelta(days=1)
        for offset in range(days):
            day = first_day + timedelta(days=offset)
            day_key = day.isoformat()
            while True:
                with self._lock:
                    word, schedule_changed = self._ensure_scheduled(day)
                    if schedule_changed:
                        self._save_schedule()
                    stored_assessment = self._assessments.get(word)
                    if stored_assessment is not None:
                        break
                    self._assessment_warnings.pop(word, None)

                assessment = self._word_assessor(word)

                with self._lock:
                    if self._scheduled_words.get(day_key) != word:
                        continue
                    self._assessments[word] = assessment.common
                    if assessment.warning is not None:
                        self._assessment_warnings[word] = assessment.warning
                    else:
                        self._assessment_warnings.pop(word, None)
                    if assessment.common is False:
                        del self._scheduled_words[day_key]
                    self._save_schedule()
                    if assessment.common is not False:
                        break

    def get_state(self, user_id: str) -> GameState:
        """Return a user's state, creating or resetting today's game as needed."""
        normalized_user_id = user_id.strip()
        if not normalized_user_id:
            raise ValueError("user_id cannot be empty")

        with self._lock:
            user_state = self._state_for_today(normalized_user_id)
            return self._snapshot(user_state)

    def submit_word(self, user_id: str, word: str) -> GameState:
        """Apply one valid letter change and return the updated user state."""
        normalized_word = _normalize_word(word)

        with self._lock:
            user_state = self._state_for_today(user_id.strip())
            if user_state.completed:
                raise GameAlreadyCompletedError(
                    "Je hebt het doel van vandaag al bereikt."
                )
            if normalized_word not in self._allowed_words | {self.target_word}:
                raise InvalidMoveError(
                    "Dit woord staat niet in de toegestane woordenlijst."
                )
            if not is_one_character_different(user_state.current_word, normalized_word):
                raise InvalidMoveError(
                    "Verander precies één letter ten opzichte van het huidige woord."
                )

            user_state.current_word = normalized_word
            user_state.entries.append(normalized_word)
            user_state.attempts += 1
            user_state.completed = normalized_word == self.target_word
            return self._snapshot(user_state)

    def complete_with_shortest_route(self, user_id: str) -> GameState:
        """Complete a user's current game using a shortest remaining route."""
        normalized_user_id = user_id.strip()
        if not normalized_user_id:
            raise ValueError("user_id cannot be empty")

        with self._lock:
            user_state = self._state_for_today(normalized_user_id)
            if user_state.completed:
                return self._snapshot(user_state)

            route = shortest_word_ladder(
                self.words,
                user_state.current_word,
                self.target_word,
            )
            if route is None:
                raise ValueError("Er is geen route naar het doel gevonden.")

            for word in route[1:]:
                user_state.current_word = word
                user_state.entries.append(word)
                user_state.attempts += 1
            user_state.completed = True
            return self._snapshot(user_state)

    def _state_for_today(self, user_id: str) -> _UserState:
        if not user_id:
            raise ValueError("user_id cannot be empty")

        today = self._today()
        user_state = self._user_states.get(user_id)
        if user_state is None or user_state.date != today:
            start_word = self.daily_start_word(today)
            user_state = _UserState(today, start_word, start_word)
            self._user_states[user_id] = user_state
        return user_state

    def _scheduled_word(self, day: Date) -> ScheduledWord:
        word = self.daily_start_word(day)
        return ScheduledWord(
            date=day,
            word=word.upper(),
            minimum_attempts=self._minimum_attempts[word],
            overridden=day.isoformat() in self._overridden_dates,
            common=self._assessments.get(word),
            warning=self._assessment_warnings.get(word),
        )

    def _ensure_scheduled(self, day: Date) -> tuple[str, bool]:
        day_key = day.isoformat()
        word = self._scheduled_words.get(day_key)
        if word is not None and self._assessments.get(word) is not False:
            return word, False
        if word is not None:
            del self._scheduled_words[day_key]

        word = self._next_unused_word(day)
        self._scheduled_words[day_key] = word
        return word, True

    def _next_unused_word(self, day: Date) -> str:
        used_words = set(self._played_words.values()) | set(
            self._scheduled_words.values()
        )
        start_index = day.toordinal() % len(self._eligible_words)
        for offset in range(len(self._eligible_words)):
            candidate_index = (start_index + offset) % len(self._eligible_words)
            candidate = self._eligible_words[candidate_index]
            if (
                candidate not in used_words
                and self._assessments.get(candidate) is not False
            ):
                return candidate
        raise ValueError("Alle geschikte dagwoorden zijn al gebruikt of ingepland.")

    def _verify_words_safely(self, days: int) -> None:
        try:
            self.verify_upcoming_words(days)
        except Exception:
            logger.exception("Asynchrone dagwoordverificatie is mislukt.")

    def _archive_played_words(self) -> bool:
        today_key = self._today().isoformat()
        due_dates = [day for day in self._scheduled_words if day <= today_key]
        for day in due_dates:
            self._played_words[day] = self._scheduled_words.pop(day)
            self._overridden_dates.discard(day)
        return bool(due_dates)

    def _load_schedule(
        self,
    ) -> tuple[
        dict[str, str],
        dict[str, str],
        set[str],
        dict[str, bool | None],
        dict[str, str],
    ]:
        if self._schedule_path is None or not self._schedule_path.exists():
            return {}, {}, set(), {}, {}

        try:
            stored_schedule = json.loads(
                self._schedule_path.read_text(encoding="utf-8")
            )
        except OSError, json.JSONDecodeError:
            return {}, {}, set(), {}, {}
        if not isinstance(stored_schedule, dict):
            return {}, {}, set(), {}, {}

        if "scheduled" not in stored_schedule and "played" not in stored_schedule:
            scheduled_source = stored_schedule
            played_source: object = {}
            overridden_source: object = list(stored_schedule)
            assessments_source: object = {}
            warnings_source: object = {}
            stored_assessment_version: object = None
        else:
            scheduled_source = stored_schedule.get("scheduled", {})
            played_source = stored_schedule.get("played", {})
            overridden_source = stored_schedule.get("overridden", [])
            assessments_source = stored_schedule.get("assessments", {})
            warnings_source = stored_schedule.get("assessment_warnings", {})
            stored_assessment_version = stored_schedule.get("assessment_version")

        if stored_assessment_version != ASSESSMENT_VERSION:
            assessments_source = {}
            warnings_source = {}

        scheduled_words = self._valid_word_mapping(scheduled_source)
        played_words = self._valid_word_mapping(played_source)
        played_values = set(played_words.values())
        scheduled_words = {
            day: word
            for day, word in scheduled_words.items()
            if word not in played_values
        }
        overridden_dates = (
            {
                day
                for day in overridden_source
                if isinstance(day, str) and day in scheduled_words
            }
            if isinstance(overridden_source, list)
            else set()
        )
        assessments = (
            {
                word: assessment
                for word, assessment in assessments_source.items()
                if isinstance(word, str)
                and word in self._minimum_attempts
                and (isinstance(assessment, bool) or assessment is None)
            }
            if isinstance(assessments_source, dict)
            else {}
        )
        assessment_warnings = (
            {
                word: warning
                for word, warning in warnings_source.items()
                if isinstance(word, str)
                and word in self._minimum_attempts
                and isinstance(warning, str)
            }
            if isinstance(warnings_source, dict)
            else {}
        )
        return (
            scheduled_words,
            played_words,
            overridden_dates,
            assessments,
            assessment_warnings,
        )

    def _valid_word_mapping(self, source: object) -> dict[str, str]:
        if not isinstance(source, dict):
            return {}

        valid_mapping: dict[str, str] = {}
        used_words: set[str] = set()
        for day, word in sorted(source.items()):
            try:
                Date.fromisoformat(day)
            except TypeError, ValueError:
                continue
            if (
                isinstance(word, str)
                and word in self._minimum_attempts
                and word not in used_words
            ):
                valid_mapping[day] = word
                used_words.add(word)
        return valid_mapping

    def _save_schedule(self) -> None:
        if self._schedule_path is None:
            self._schedule_dirty = False
            return

        self._schedule_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._schedule_path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(
                {
                    "scheduled": self._scheduled_words,
                    "played": self._played_words,
                    "overridden": sorted(self._overridden_dates),
                    "assessments": self._assessments,
                    "assessment_warnings": self._assessment_warnings,
                    "assessment_version": ASSESSMENT_VERSION,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(self._schedule_path)
        self._schedule_dirty = False

    def _snapshot(self, state: _UserState) -> GameState:
        return GameState(
            date=state.date,
            start_word=state.start_word.upper(),
            target_word=self.target_word.upper(),
            current_word=state.current_word.upper(),
            entries=tuple(word.upper() for word in state.entries),
            attempts=state.attempts,
            minimum_attempts=(
                self._minimum_attempts[state.start_word] if state.completed else None
            ),
            completed=state.completed,
        )
