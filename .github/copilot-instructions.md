# Copilot Instructions

## Project Overview

This is a lightweight, web-based **Taekwondo Competition Manager** built with Python (Flask) and HTMX. It handles tournament bracket generation, ring management, match scheduling, and live scoring for Taekwondo competitions.

## Tech Stack

- **Language**: Python 3.13
- **Package Manager**: [uv](https://docs.astral.sh/uv/)
- **Backend**: Flask, SQLAlchemy (ORM)
- **Database**: PostgreSQL (via `psycopg2-binary`) in production; connection details loaded from `.env`
- **Frontend**: HTML templates (Jinja2), [HTMX](https://htmx.org/) for dynamic interactions (no JavaScript framework)
- **Deployment**: AWS Lambda via [Zappa](https://github.com/zappa/Zappa) or container (Containerfile)

## Project Structure

- `app.py` — Main application: Flask app, SQLAlchemy models, all route handlers
- `templates/` — Jinja2 HTML templates
- `init_db.py` — Script to initialize the database schema
- `reset_db.py` — Script to reset the database
- `test_db.py` — Script to test the database connection
- `pyproject.toml` — Project dependencies (managed with `uv`)
- `zappa_settings.json` — AWS Lambda deployment configuration
- `Containerfile` — Container image definition

## Database Models

- **Ring** — Physical competition ring (e.g., "Ring 1")
- **Division** — Category of competition (e.g., "Male - Black Belt - Under 70kg")
- **Competitor** — Athlete belonging to a division
- **Match** — Links two competitors, tracks winner, round name, ring assignment, and bracket tree via `next_match_id`

## Development Practices

- Run the app locally with `uv run flask run`
- Install dependencies with `uv sync`
- Environment variables (`user`, `password`, `host`, `port`, `dbname`) are loaded from a `.env` file using `python-dotenv`
- Routes follow a pattern:
  - `/ui/...` — HTMX fragment routes that return partial HTML
  - `/admin/...` — Admin page routes that return full HTML templates
  - `/divisions/...`, `/rings/...`, `/matches/...` — JSON API routes
- HTMX responses return HTML fragments (not JSON); use `render_template_string` or f-strings for simple fragments
- Use Flask-SQLAlchemy ORM patterns; avoid raw SQL

## Coding Conventions

- Keep all models and routes in `app.py` (single-file Flask app pattern)
- Use `db.session.add()`, `db.session.commit()`, and `db.session.flush()` for database writes
- Use `Model.query.get_or_404(id)` for fetching records by primary key
- Match status values: `"Pending"`, `"In Progress"`, `"Completed"`, `"Disqualification"`, `"Completed (Bye)"`
- Round name values: `"Round 1"`, `"Round {n}"`, `"Quarter-Final"`, `"Semi-Final"`, `"Final"`
