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

- `app.py` — Main application: Flask app, SQLAlchemy models, all route handlers
- `templates/` — Jinja2 HTML templates
- `tests/` — Pytest test suite (`conftest.py` fixtures + `test_app.py`)
- `scripts/init_db.py` — Script to initialize the database schema
- `scripts/reset_db.py` — Script to reset the database
- `scripts/test_db.py` — Script to test the database connection
- `scripts/update_secrets.py` — Script to upload `secrets.json` configuration to an S3 bucket
- `scripts/migrate_add_event_type.py` — Migration script to add `event_type` to Division
- `scripts/migrate_add_poomsae_style.py` — Migration script to add `poomsae_style` to Division
- `scripts/migrate_add_position.py` — Migration script to add `position` to Competitor
- `pyproject.toml` — Project dependencies (managed with `uv`)
- `zappa_settings.json` — AWS Lambda deployment configuration

## Database Models

- **Ring** — Physical competition ring (e.g., "Ring 1")
- **Division** — Category of competition (e.g., "Male - Black Belt - Under 70kg")
- **Competitor** — Athlete belonging to a division
- **Match** — Links two competitors, tracks winner, round name, ring assignment, and bracket tree via `next_match_id`

## Development Practices

- Run the app locally with `uv run flask run`
- Install dependencies with `uv sync`
- Run tests with `uv run pytest` (uses SQLite in-memory; no PostgreSQL needed for tests)
- Environment variables (`user`, `password`, `host`, `port`, `dbname`) are loaded from a `.env` file using `python-dotenv`
- Required environment variables:
  - `SECRET_KEY` — Flask session secret key (required at startup)
  - `SUPABASE_URL` — URL of the Supabase project used for authentication (required at startup)
  - `SUPABASE_KEY` — Supabase anonymous/service key (required at startup)
  - `DATABASE_URL` — Full PostgreSQL URI (optional; takes precedence over individual `user`/`password`/`host`/`port`/`dbname` vars); set to `sqlite:///:memory:` for tests
  - `user`, `password`, `host`, `port`, `dbname` — Individual PostgreSQL connection components (used when `DATABASE_URL` is not set)
- Routes follow a pattern:
  - `/ui/...` — HTMX fragment routes that return partial HTML
  - `/admin/...` — Admin page routes that return full HTML templates
  - `/divisions/...`, `/rings/...`, `/matches/...` — JSON API routes
- HTMX responses return HTML fragments (not JSON)
- Always use template files from the `templates/` directory for rendering HTML; avoid inline HTML in route handlers
- Use Flask-SQLAlchemy ORM patterns; avoid raw SQL

## Authentication

- Authentication is handled by [Supabase Auth](https://supabase.com/docs/guides/auth)
- The `supabase_client` (created from `SUPABASE_URL` + `SUPABASE_KEY`) is used for user sign-in; sign-out currently only clears the Flask session in the `/logout` route (no Supabase `sign_out` call)
- Protected routes use the `@login_required` decorator, which checks `session.get("user")`
- HTMX requests that fail authentication receive an `HX-Redirect` response header pointing to `/login`
- CSRF protection is enabled globally via Flask-WTF (`CSRFProtect`); tests set `WTF_CSRF_ENABLED = False`

## Coding Conventions

- Keep all models and routes in `app.py` (single-file Flask app pattern)
- Use `db.session.add()`, `db.session.commit()`, and `db.session.flush()` for database writes
- Use `Model.query.get_or_404(id)` for fetching records by primary key
- Match status values: `"Pending"`, `"In Progress"`, `"Completed"`, `"Disqualification"`, `"Completed (Bye)"`
- Round name values: `"Round 1"`, `"Round {n}"`, `"Quarter-Final"`, `"Semi-Final"`, `"Final"`
- Always write tests for any new page or functionality update
