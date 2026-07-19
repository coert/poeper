"""FastAPI application for the daily word-ladder game."""

from datetime import date
import os
from pathlib import Path
from secrets import compare_digest
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from libs.common_word import assess_common_dutch_word
from libs.game import DailyWordGame, GameAlreadyCompletedError, InvalidMoveError

TARGET_WORD = "POEP"
WORD_LIST_PATH = Path(__file__).parent / "assets" / "wordlist.txt"
STATIC_PATH = Path(__file__).parent / "static"
SCHEDULE_PATH = Path(__file__).parent / "data" / "daily-words.json"
ADMIN_TOKEN = os.environ.get("POEPER_ADMIN_TOKEN")
ROOT_PATH = os.environ.get("POEPER_ROOT_PATH", "")
USER_COOKIE_NAME = "word_ladder_user_id"
USER_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def environment_flag(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.casefold() in {"1", "true", "yes", "on"}


COOKIE_SECURE = environment_flag(
    "POEPER_COOKIE_SECURE",
    default=os.environ.get("POEPER_ENV") == "production",
)


def is_development_mode() -> bool:
    """Return whether local development-only conveniences may run."""
    return os.environ.get("POEPER_ENV", "development").casefold() == "development"


class WordEntry(BaseModel):
    word: str = Field(min_length=1, max_length=32)


class GameResponse(BaseModel):
    date: date
    start_word: str
    target_word: str
    current_word: str
    entries: list[str]
    attempts: int
    minimum_attempts: int | None
    completed: bool


class ScheduledWordResponse(BaseModel):
    date: date
    word: str
    minimum_attempts: int
    overridden: bool
    common: bool | None
    warning: str | None


class RotateVerificationResponse(BaseModel):
    days: int
    rotated_days: int
    failed_days: int
    verification_completed: bool


word_list = WORD_LIST_PATH.read_text(encoding="utf-8").splitlines()
game = DailyWordGame(
    word_list,
    TARGET_WORD,
    schedule_path=SCHEDULE_PATH,
    word_assessor=assess_common_dutch_word,
)

app = FastAPI(title="Daily Dutch Word Ladder", root_path=ROOT_PATH)
app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    """Serve the browser game."""
    return FileResponse(STATIC_PATH / "index.html")


@app.get("/admin", include_in_schema=False)
def admin_frontend() -> FileResponse:
    """Serve the daily-word curation dashboard."""
    return FileResponse(STATIC_PATH / "admin.html")


def require_admin_token(token: str | None) -> None:
    """Reject requests that do not contain the configured admin secret."""
    if not ADMIN_TOKEN:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Stel POEPER_ADMIN_TOKEN in om het beheer te activeren.",
        )
    if token is None or not compare_digest(token, ADMIN_TOKEN):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "De beheersleutel is ongeldig.",
        )


@app.get(
    "/admin/api/daily-words",
    response_model=list[ScheduledWordResponse],
)
def list_daily_words(
    days: int = Query(30, ge=1, le=30),
    x_admin_token: str | None = Header(None),
):
    """List future daily words for curation."""
    require_admin_token(x_admin_token)
    schedule = game.upcoming_words(days)
    game.start_word_verification(days)
    return schedule


@app.post(
    "/admin/api/daily-words/{scheduled_date}/rotate",
    response_model=ScheduledWordResponse,
)
def rotate_daily_word(
    scheduled_date: date,
    x_admin_token: str | None = Header(None),
):
    """Rotate one future date to another eligible start word."""
    require_admin_token(x_admin_token)
    try:
        scheduled_word = game.rotate_daily_word(scheduled_date)
        game.start_word_verification(30)
        return scheduled_word
    except ValueError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error


@app.post(
    "/admin/api/daily-words/rotate-verification",
    response_model=RotateVerificationResponse,
)
def rotate_word_verification(
    days: int = Query(30, ge=1, le=30),
    x_admin_token: str | None = Header(None),
):
    """Rotate upcoming words in bulk, then start background verification."""
    require_admin_token(x_admin_token)

    before_schedule = game.upcoming_words(days)
    game.verify_upcoming_words(days)
    after_schedule = game.upcoming_words(days)

    rotated_days = sum(
        1
        for before, after in zip(before_schedule, after_schedule)
        if before.word != after.word
    )
    failed_days = sum(1 for item in after_schedule if item.warning)
    return RotateVerificationResponse(
        days=days,
        rotated_days=rotated_days,
        failed_days=failed_days,
        verification_completed=True,
    )


def get_or_create_user_id(request: Request, response: Response) -> str:
    """Return the UUID4 session ID, setting a new cookie when necessary."""
    cookie_value = request.cookies.get(USER_COOKIE_NAME)
    try:
        user_uuid = UUID(cookie_value) if cookie_value else None
        if user_uuid is None or user_uuid.version != 4:
            raise ValueError
    except ValueError, AttributeError:
        user_uuid = uuid4()
        response.set_cookie(
            USER_COOKIE_NAME,
            str(user_uuid),
            max_age=USER_COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=COOKIE_SECURE,
        )
    return str(user_uuid)


@app.get("/game", response_model=GameResponse)
def get_game(request: Request, response: Response):
    """Get or start today's game for a user."""
    try:
        user_id = get_or_create_user_id(request, response)
        return game.get_state(user_id)
    except ValueError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error


@app.post("/game/entries", response_model=GameResponse)
def submit_entry(entry: WordEntry, request: Request, response: Response):
    """Submit a word that differs by one character from the current word."""
    try:
        user_id = get_or_create_user_id(request, response)
        return game.submit_word(user_id, entry.word)
    except GameAlreadyCompletedError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except (InvalidMoveError, ValueError) as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error


@app.post("/game/cheat", response_model=GameResponse, include_in_schema=False)
def complete_game_for_development(request: Request, response: Response):
    """Complete the game by a shortest route during local development only."""
    if not is_development_mode():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Niet beschikbaar.")
    try:
        user_id = get_or_create_user_id(request, response)
        return game.complete_with_shortest_route(user_id)
    except ValueError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
