# Copilot Instructions

## Project Overview

This is a lightweight, web-based **Taekwondo Competition Manager** built with Python (Flask) and HTMX. It handles tournament bracket generation, ring management, match scheduling, and live scoring for Taekwondo competitions.

## Tech Stack

- **Language**: Python 3.13
- **Package Manager**: [uv](https://docs.astral.sh/uv/)
- **Backend**: Flask, SQLAlchemy (ORM)
- **Database**: PostgreSQL (via `psycopg2-binary`) in production; connection details loaded from `.env`
- **Frontend**: HTML templates (Jinja2), [HTMX](https://htmx.org/) for dynamic interactions (no JavaScript framework)
- **Deployment**: AWS Lambda via [Zappa](https://github.com/zappa/Zappa)

## Project Structure

**Three-file split** (no circular imports):
- `models.py` — `db = SQLAlchemy()` (unbound), `VALID_EVENT_TYPES`, `COMPLETED_MATCH_STATUSES` constants, all SQLAlchemy models
- `api.py` — `api_v1` Blueprint (`/api/v1` routes), token helpers (`_generate_raw_token`, `_hash_token`), `api_login_required` decorator, REST API endpoints
- `app.py` — Flask app initialization, `db.init_app(app)`, CSRF protection, Supabase auth, UI/HTMX routes, page routes, imports from both `models` and `api`

**Supporting files:**
- `templates/` — Jinja2 HTML templates
- `tests/conftest.py` — Pytest fixtures; imports from `models`, `api`, and `app`
- `tests/test_app.py` — Test suite (484 tests, all passing)
- `scripts/` — Utility scripts (seed_dev_db, init_db, reset_db, etc.)
- `pyproject.toml` — Dependencies (managed with `uv`)
- `zappa_settings.json` — AWS Lambda deployment config

## Database Models

- **Ring** — Physical competition ring (e.g., "Ring 1"); has many matches and divisions
- **Division** — Category of competition (e.g., "Male - Black Belt - Under 70kg"); includes `event_type` (kyorugi/poomsae), `poomsae_style` (bracket/group), `ring_id` (for poomsae events)
- **Competitor** — Athlete belonging to a division; includes `position` (seed/roster order)
- **Match** — Links competitors, tracks winner, round, ring, and bracket tree via `next_match_id`
- **Score** — Scorekeeper results for a match (kyorugi-specific)
- **ApiToken** — Bearer tokens for `/api/v1` access; stored as SHA-256 hash

## Development Practices

**Running locally:**
- `uv run flask run` — Start dev server
- `uv sync` — Install/sync dependencies
- `uv run pytest tests/ -x -q` — Run test suite (fast; uses SQLite in-memory)

**Environment variables** (loaded from `.env`):
- `SECRET_KEY` — Flask session secret (required at startup)
- `SUPABASE_URL`, `SUPABASE_KEY` — Supabase Auth (required at startup)
- `DATABASE_URL` — PostgreSQL URI (optional; takes precedence); set to `sqlite:///:memory:` for tests
- `user`, `password`, `host`, `port`, `dbname` — Fallback PostgreSQL components (when `DATABASE_URL` not set)
- `APP_ENV=dev` — Optional; some scripts (e.g., seed_dev_db) check this

**Route patterns:**
- `/ui/...` — HTMX fragments returning partial HTML
- `/admin/...` — Full HTML page templates
- `/api/v1/...` — JSON API endpoints (Bearer token auth)
- Legacy routes (deprecated) return `Deprecation: true` header + `Link` to successor

**Key files for common tasks:**
- Adding a new model: edit `models.py`, add to `db.Model`
- Adding API endpoints: edit `api.py`, add routes to `api_v1` Blueprint
- UI routes & Supabase auth: edit `app.py`
- Test fixtures: `tests/conftest.py`; import models/helpers as needed
- Scripts: use `from app import app` + `from models import db` pattern

## REST API Documentation

See [README.md](../../README.md) for complete `/api/v1` endpoint documentation, including:
- Response envelope format (`{"data": ..., "error": {...}}`)
- Bearer token authentication
- All resource endpoints (Rings, Divisions, Competitors, Matches, Bracket, etc.)
- Legacy endpoints and deprecation info

## Coding Conventions

**Import order & dependencies:**
- `models.py` ← `api.py` ← `app.py` (unidirectional; no circular imports)
- `api.py` imports from `models` (models, constants, db instance)
- `app.py` imports from both `api` (Blueprint, token helpers) and `models` (models, constants, db instance)
- Tests import from all three files as needed

**Database & ORM:**
- Use `db.init_app(app)` in `app.py` (not `SQLAlchemy(app)`)
- Use `Model.query.get_or_404(id)` for fetching by primary key
- Use `db.session.add()`, `db.session.commit()`, `db.session.flush()` for writes
- Avoid raw SQL; use SQLAlchemy ORM patterns

**Constants (from `models.py`):**
- `VALID_EVENT_TYPES = {"poomsae", "kyorugi"}`
- `COMPLETED_MATCH_STATUSES = {"Completed", "Completed (Bye)", "Disqualification"}`
- Match status values: `"Pending"`, `"In Progress"`, `"Completed"`, `"Disqualification"`, `"Completed (Bye)"`
- Round name values: `"Round 1"`, `"Round {n}"`, `"Quarter-Final"`, `"Semi-Final"`, `"Final"`

**API conventions (`/api/v1`):**
- Use `success_response(data, status_code)` and `error_response(code, message, details, status_code)` helpers
- All responses use `{"data": ..., "error": null}` or `{"data": null, "error": {...}}` envelope
- Protect routes with `@api_login_required` decorator (Bearer token auth, returns 401 JSON)
- Exempt `api_v1` Blueprint from CSRF: `csrf.exempt(api_v1)` is set in `app.py`

**HTML & templates:**
- Always render templates from `templates/` directory; avoid inline HTML in route handlers
- HTMX fragment routes (`/ui/...`) return partial HTML; full page routes return complete templates
- Use Jinja2 template syntax; templates have access to Flask context

**Authentication:**
- UI routes use `@login_required` (checks `session.get("user")`); redirects to `/login` on failure
- HTMX requests that fail auth get `HX-Redirect` header pointing to login
- API routes use `@api_login_required` (Bearer token); returns JSON 401
- Supabase Auth is handled via `supabase_client` (created from env vars `SUPABASE_URL`, `SUPABASE_KEY`)

**Testing:**
- Run with `uv run pytest tests/ -x -q` (SQLite in-memory, no PostgreSQL needed)
- Tests set `WTF_CSRF_ENABLED = False` globally
- Import fixtures from `tests/conftest.py`; import helpers from `api` as needed
