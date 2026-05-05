# Claude Instructions — TKD Competition Manager

## Quick Context

Flask + HTMX app for Taekwondo tournament management: bracket generation, scoring, ring scheduling. **Python 3.13, `uv` package manager. 484 passing tests. Three-file architecture (models / api / app) — no circular imports.**

## Structure

- `models.py` — SQLAlchemy models, constants
- `api.py` — `/api/v1` routes (Bearer auth)
- `app.py` — Flask init, UI routes, Supabase auth
- `tests/test_app.py` — 484 tests (pytest)

## Setup & Run

```bash
uv sync                        # Install dependencies
uv run flask run               # Dev server (http://localhost:5000)
uv run pytest tests/ -x -q     # Run tests (in-memory SQLite)
```

**Required env vars:** `SECRET_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`

## Key Conventions

**Import order:** `models.py` ← `api.py` ← `app.py` (never reverse)

**Routes:**
- `/api/v1/...` — JSON API (Bearer token + `@api_login_required`)
- `/admin/...` — Full page (session + `@login_required`)
- `/ui/...` — HTMX fragments (partial HTML)

**Response envelope:** `{"data": ..., "error": null}` or `{"data": null, "error": {...}}`

**Constants:** `VALID_EVENT_TYPES`, `COMPLETED_MATCH_STATUSES` (from `models.py`)

**Database:** `db.session.add()` + `db.session.commit()`

## Documentation

- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** — Models, auth, design patterns
- **[DEVELOPMENT.md](docs/DEVELOPMENT.md)** — Code examples, testing, debugging
- **[README.md](README.md)** — API endpoints, legacy routes
