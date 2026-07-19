## Daily word-ladder API

Clone this repository together with the OpenTaal word-list submodule:

```bash
git clone --recurse-submodules <repository-url>
```

For an existing clone, initialize the word list once with
`git submodule update --init --recursive`.

Start the development server from the project root:

```bash
uv run fastapi dev main.py
```

Open the game at `http://127.0.0.1:8000/`. Interactive API documentation is
available at `http://127.0.0.1:8000/docs`.

During local development, press Ctrl+Shift+Enter (or Cmd+Shift+Enter on macOS)
to fill in a shortest solution and test the completed-game UI. This shortcut
is disabled whenever `POEPER_ENV=production`.

Get today's game. A UUID4 user ID is created automatically and stored in an
HTTP-only cookie:

```http
GET /game
```

Completed daily results are also stored as an aggregated tries distribution
in the browser cookie `poeper_results`. This powers the statistics histogram
without storing identifying information.

Submit the next word:

```http
POST /game/entries
Content-Type: application/json

{"word": "next"}
```

A valid entry must be in the filtered word list and differ from the user's
current word by exactly one character. Valid entries increase `attempts` by
one. The game is completed when `current_word` equals `target_word`. On
completion, `minimum_attempts` reports the shortest possible route from that
day's start word; it is `null` while the game is still active.

API documentation is available at `/docs` while the server is running.

## Daily-word administration

Set a private admin token when starting the API:

```bash
POEPER_ADMIN_TOKEN="choose-a-long-random-secret" uv run fastapi dev main.py
```

Then open `http://127.0.0.1:8000/admin`. The dashboard lists the upcoming
daily words and lets you rotate individual future dates. Overrides are stored
in `data/daily-words.json` and survive server restarts. This file also records
played words so they cannot be scheduled again. The upcoming 30-day schedule
contains no duplicates, including after manual rotations. The token is
retained only in the browser tab's session storage.

Future words are checked with the OpenAI-compatible vLLM server at
`http://spark-0240:8000`. Words classified as uncommon are skipped and the
next unused candidate is checked. Verification runs asynchronously in a
daemon thread, so the admin page loads immediately and server shutdown is not
held up by an active model request. The page polls while words display
`Wordt geverifieerd…`. Results are cached in the schedule file. If the model
is unavailable, the candidate remains scheduled and the admin page displays
a warning instead of failing schedule generation.

The model connection can be changed with `POEPER_VLLM_URL` and
`POEPER_VLLM_MODEL`. Schedule generation is limited to 30 future days.

## Production

The production entrypoint starts the FastAPI application with Uvicorn, uses
one worker, disables autoreload, and trusts proxy headers from localhost:

```bash
export POEPER_ADMIN_TOKEN="choose-a-long-random-secret"
./start-production.sh
```

The script can be launched from any working directory. It validates the admin
token, uses the locked `uv` environment, and forwards shutdown signals directly
to Uvicorn. The equivalent direct command is `uv run python production.py`.

It listens on `0.0.0.0:8000` by default. Configure it with `POEPER_HOST`,
`POEPER_PORT`, `POEPER_LOG_LEVEL`, `POEPER_FORWARDED_ALLOW_IPS`, and
`POEPER_ROOT_PATH`.

Production mode marks the anonymous user cookie as `Secure`, so deploy it
behind an HTTPS reverse proxy. For a trusted LAN deployment that deliberately
uses plain HTTP, explicitly set `POEPER_COOKIE_SECURE=false` before starting.

The server intentionally uses one worker because user progress is held in
memory. Moving user state to shared storage is required before increasing the
worker count or running multiple replicas.

## Docker deployment behind Apache

This repository now includes a containerized deployment for serving POEPER at
`https://bijenmeent85.ddns.net/poeper`.

1. Create runtime secrets and settings:

```bash
cp .env.production.example .env.production
chmod 600 .env.production
```

2. Start the service on localhost only:

```bash
docker compose up -d --build
```

This maps container port `8000` to `127.0.0.1:18000` and persists scheduling
state in `./data`.

3. Add Apache reverse proxy rules in
`/etc/apache2/sites-available/000-default-le-ssl.conf`:

```apache
# POEPER under /poeper
ProxyPass /poeper http://127.0.0.1:18000
ProxyPassReverse /poeper http://127.0.0.1:18000

# Optional hardening: limit admin panel and admin API to known source IPs.
<LocationMatch "^/poeper/admin(?:/api/.*)?$">
	<RequireAny>
		Require ip 203.0.113.10
		Require ip 2001:db8::/64
	</RequireAny>
</LocationMatch>

# Keep deny-by-default, but explicitly allow poeper.
<LocationMatch "^/(?!nextcloud|owncloud|poeper)(.*)$">
	Require all denied
</LocationMatch>
```

4. Validate and reload Apache:

```bash
sudo apachectl -t
sudo systemctl reload apache2
```

Use `POEPER_ROOT_PATH=/poeper` (already set in `docker-compose.yml`) so FastAPI
and browser routes behave correctly behind a path-prefix proxy.

Browsers send their IANA time-zone name with game requests, so each player's
puzzle rolls over at midnight in their own local time. Clients that do not send
a time zone fall back to `Europe/Amsterdam`; set `POEPER_TIME_ZONE` to change
that fallback.
