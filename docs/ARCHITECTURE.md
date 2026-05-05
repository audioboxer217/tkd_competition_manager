# Architecture

## Overview

TKD Competition Manager is a three-layer web application:

1. **Data layer** (`models.py`) — SQLAlchemy ORM models, constants
2. **API layer** (`api.py`) — REST endpoints, token auth, response helpers
3. **App layer** (`app.py`) — Flask setup, UI routes, Supabase auth

This split keeps concerns separated and eliminates circular imports.

## Data Models

### Ring

```python
class Ring(db.Model):
    id: int (PK)
    name: str                          # "Ring 1", "Ring 2", etc.
    matches: List[Match] (backref)
    divisions: List[Division] (backref)
```

Physical location where matches occur.

### Division

```python
class Division(db.Model):
    id: int (PK)
    name: str                          # "Male - Black Belt - Under 70kg"
    event_type: str                    # "kyorugi" or "poomsae"
    poomsae_style: Optional[str]       # "bracket", "group", or None
    ring_id: Optional[int] (FK Ring)   # For poomsae: which ring hosts this
    ring_sequence: Optional[int]       # For poomsae: display order (1, 2, 3, ...)
    event_status: str                  # "Pending", "In Progress", "Completed"
    start_time: Optional[datetime]     # Poomsae timing
    end_time: Optional[datetime]
    competitors: List[Competitor] (backref)
    matches: List[Match] (backref)
```

Category of competition (weight class, belt, event type). For poomsae, tracks which ring and order it appears in.

### Competitor

```python
class Competitor(db.Model):
    id: int (PK)
    name: str
    division_id: int (FK Division)
    position: Optional[int]            # Seed/roster order
    division: Division (backref)
    matches_as_c1: List[Match] (backref)
    matches_as_c2: List[Match] (backref)
```

Athlete in a division.

### Match

```python
class Match(db.Model):
    id: int (PK)
    division_id: int (FK Division)
    competitor1_id: Optional[int] (FK Competitor)
    competitor2_id: Optional[int] (FK Competitor)
    ring_id: Optional[int] (FK Ring)
    round_name: Optional[str]          # "Round 1", "Semi-Final", "Final"
    status: str                        # "Pending", "In Progress", "Completed", ...
    winner_id: Optional[int] (FK Competitor)
    next_match_id: Optional[int] (FK Match)  # Bracket tree link
    match_number: Optional[int]        # Scheduling number (e.g., 101)
    division: Division (backref)
    ring: Ring (backref)
    next_match: Match (backref)        # Single winner advances here
    scores: List[Score] (backref)
```

Links two competitors, tracks bracket progression. The `next_match_id` forms a binary tree structure for single-elimination brackets.

### Score

```python
class Score(db.Model):
    id: int (PK)
    competitor_id: int (FK Competitor)
    division_id: int (FK Division)
    score_value: float
    competitor: Competitor (backref)
```

Poomsae score for an individual competitor in a division. Each competitor may have at most one score per division (enforced by a unique constraint on `competitor_id` + `division_id`).

### ApiToken

```python
class ApiToken(db.Model):
    id: int (PK)
    name: str
    token_hash: str                    # SHA-256 of the raw token (never store raw)
    is_active: bool                    # False = revoked
    created_at: datetime
    last_used_at: Optional[datetime]
    user_id: Optional[str]             # Optional owner reference (e.g. Supabase user id)
```

Bearer token for `/api/v1` access. Token is shown only once at creation; thereafter, only the hash is stored.

## Import Dependency Graph

```
models.py              ← Core models & constants
  ↑
api.py                 ← REST routes (imports models, db, constants)
  ↑
app.py                 ← Flask init, UI routes (imports api, models)
```

**Rule:** Never have downward dependencies (e.g., `models.py` must not import from `api.py` or `app.py`).

This is enforced by:
- `conftest.py` imports in order: models → api → app
- Tests run successfully without circular import errors

## Route Patterns

### `/api/v1/...` — REST API

- **Auth:** Bearer token (`@api_login_required` decorator)
- **Response:** JSON envelope (`{"data": ..., "error": ...}`)
- **Status codes:** 200 (OK), 201 (Created), 400 (Bad Request), 401 (Unauthorized), 404 (Not Found), 409 (Conflict), 422 (Unprocessable Entity), 500 (Server Error)
- **Examples:** `GET /api/v1/rings`, `POST /api/v1/divisions`, `PATCH /api/v1/matches/<id>`, etc.

See [README.md](../README.md) for full endpoint listing.

### `/ui/...` — HTMX Fragments

- **Auth:** Session cookie (`@login_required` or no auth)
- **Response:** Partial HTML (no `<html>` tag; returned via HTMX `hx-swap`)
- **CSRF:** Token included in form data or headers
- **Examples:** `GET /ui/divisions/<id>/bracket` (returns match tree as HTML fragment)

### `/admin/...` — Admin Pages

- **Auth:** Session cookie (`@login_required`)
- **Response:** Full HTML page (with `<html>`, `<head>`, `<body>`)
- **Examples:** `/admin` (dashboard), `/admin/api-tokens` (token management)

### Legacy Routes (Deprecated)

Routes like `GET /divisions`, `POST /matches/<id>/result` pre-date `/api/v1`. Still functional but marked deprecated:
- Response includes `Deprecation: true` header
- Response includes `Link: </api/v1>; rel="successor-version"` header

Clients should migrate to `/api/v1` equivalents.

## Authentication & Authorization

### Session-based (UI)

1. User visits `/login`
2. Form posts to `/auth/login` (Supabase)
3. Supabase returns session token
4. Token stored in Flask `session`
5. Protected routes check `session.get("user")`; redirect to `/login` if missing
6. HTMX requests that fail auth get `HX-Redirect` header

### Bearer token (API)

1. Admin generates token via `/admin/api-tokens`
2. Token shown once; user copies and stores securely
3. Client includes `Authorization: Bearer <token>` in requests
4. `@api_login_required` decorator:
   - Extracts token from header
   - Hashes it (SHA-256)
   - Checks if hash exists in `ApiToken` table
   - Returns 401 JSON if missing/revoked

**Why hash tokens?** If the database is leaked, raw tokens remain secret (attacker would need to reverse a SHA-256 hash).

## Constants

**From `models.py`:**

```python
VALID_EVENT_TYPES = {"poomsae", "kyorugi"}

COMPLETED_MATCH_STATUSES = {"Completed", "Completed (Bye)", "Disqualification"}

# Match status progression:
# "Pending" → "In Progress" → "Completed" (or "Disqualification", "Completed (Bye)")

# Round name values:
# "Round 1", "Round 2", ..., "Quarter-Final", "Semi-Final", "Final"
```

Use these constants when validating user input or querying.

## Database Schema Notes

### Indexing

- `Division` has an index on `ring_id` for quick poomsae lookups by ring

### Nullable Columns

- `Competitor.position` — nullable (position/seed is optional)
- `Match.next_match_id` — nullable (final match has no next match)
- `Match.ring_id` — nullable (match can be unscheduled)
- `Division.poomsae_style` — nullable (not set until poomsae division is started)

### Foreign Keys

- Child records are **not** deleted automatically by cascades. The SQLAlchemy relationships do not define `cascade="all, delete-orphan"`. Delete routes (e.g., `ui_delete_division`) manually delete child scores, matches, and competitors before deleting the parent record.

## Environment Configuration

**Development:**
- `DATABASE_URL` or individual components (`user`, `password`, `host`, `port`, `dbname`)
- `SECRET_KEY` — random string for session signing
- `SUPABASE_URL`, `SUPABASE_KEY` — for Supabase Auth
- `APP_ENV=dev` — optional; some scripts check this

**Testing:**
- SQLite in-memory database (`sqlite:///:memory:`)
- `WTF_CSRF_ENABLED = False` in `conftest.py`
- Fixtures clean/reset database between tests

## Deployment

**Target:** AWS Lambda via Zappa (`zappa_settings.json`)

- Database: PostgreSQL via Supabase
- Secrets: Uploaded to S3 as `secrets.json` via `scripts/update_secrets.py` (reads from a `<env>.env` file and writes to the Zappa S3 bucket)
- Environment variables: Loaded from the S3 `secrets.json` at Lambda startup

## Design Patterns Used

### Repository-ish

`models.py` defines all queries via SQLAlchemy ORM; `api.py` and `app.py` use those models without direct SQL.

### Blueprint

`api.py` defines a Flask Blueprint (`api_v1`), which `app.py` registers. Keeps API routes isolated.

### Decorator

`@api_login_required` and `@login_required` decorators enforce auth; `@csrf.exempt` exempts API from CSRF.

### Response Envelope

All JSON responses wrap data in `{"data": ..., "error": ...}`. Clients can always check `response.error` for errors.

## Common Pitfalls

1. **Circular imports:** Don't import from `api.py` or `app.py` in `models.py`.
2. **Raw tokens:** Never print or log raw API tokens; only the hash is safe.
3. **CSRF on HTMX:** Remember to include `{{ csrf_token() }}` in forms.
4. **Bracket queries:** Match tree queries need careful `next_match_id` handling; use `joinedload()` to avoid N+1.
5. **Status validation:** Always check status against `COMPLETED_MATCH_STATUSES` before allowing updates.
