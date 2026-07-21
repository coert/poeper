"""Persistent, privacy-preserving daily game performance statistics."""

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
import sqlite3


@dataclass(frozen=True, slots=True)
class DailyPerformance:
    """Aggregated performance for one puzzle date."""

    date: date
    players: int
    solved: int
    average_steps: float | None
    average_above_par: float | None


class PerformanceStore:
    """Store one anonymous result per player and puzzle date in SQLite."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_player_performance (
                    game_date TEXT NOT NULL,
                    player_key TEXT NOT NULL,
                    attempts INTEGER NOT NULL CHECK (attempts >= 1),
                    minimum_attempts INTEGER NOT NULL CHECK (minimum_attempts >= 1),
                    completed INTEGER NOT NULL CHECK (completed IN (0, 1)),
                    PRIMARY KEY (game_date, player_key)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=10)

    def record(
        self,
        game_date: date,
        user_id: str,
        attempts: int,
        minimum_attempts: int,
        completed: bool,
    ) -> None:
        """Upsert a player's progress, preserving a result once completed."""
        player_key = sha256(
            f"{game_date.isoformat()}:{user_id}".encode("utf-8")
        ).hexdigest()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO daily_player_performance (
                    game_date,
                    player_key,
                    attempts,
                    minimum_attempts,
                    completed
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (game_date, player_key) DO UPDATE SET
                    attempts = CASE
                        WHEN daily_player_performance.completed = 1
                        THEN daily_player_performance.attempts
                        ELSE excluded.attempts
                    END,
                    minimum_attempts = CASE
                        WHEN daily_player_performance.completed = 1
                        THEN daily_player_performance.minimum_attempts
                        ELSE excluded.minimum_attempts
                    END,
                    completed = MAX(
                        daily_player_performance.completed,
                        excluded.completed
                    )
                """,
                (
                    game_date.isoformat(),
                    player_key,
                    attempts,
                    minimum_attempts,
                    int(completed),
                ),
            )

    def results_before(self, before: date) -> list[DailyPerformance]:
        """Return newest-first aggregates strictly before the supplied date."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    game_date,
                    COUNT(*) AS players,
                    SUM(completed) AS solved,
                    AVG(CASE WHEN completed = 1 THEN attempts END) AS average_steps,
                    AVG(
                        CASE WHEN completed = 1
                        THEN attempts - minimum_attempts END
                    ) AS average_above_par
                FROM daily_player_performance
                WHERE game_date < ?
                GROUP BY game_date
                ORDER BY game_date DESC
                """,
                (before.isoformat(),),
            ).fetchall()

        return [
            DailyPerformance(
                date=date.fromisoformat(game_date),
                players=players,
                solved=solved,
                average_steps=average_steps,
                average_above_par=average_above_par,
            )
            for game_date, players, solved, average_steps, average_above_par in rows
        ]
