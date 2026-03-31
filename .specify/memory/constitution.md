<!--
SYNC IMPACT REPORT
==================
Version change: (unversioned template) → 1.0.0
Modified principles: None (initial ratification)
Added sections:
  - Core Principles (I–V)
  - Technology Stack & Constraints
  - Development Workflow
  - Governance
Removed sections: None (template placeholders replaced)
Templates requiring updates:
  ✅ .specify/templates/plan-template.md — Constitution Check updated with project-specific gates
  ✅ .specify/templates/spec-template.md — No changes required; template is project-agnostic
  ✅ .specify/templates/tasks-template.md — No changes required; template is project-agnostic
Follow-up TODOs: None
-->

# TKD Competition Manager Constitution

## Core Principles

### I. Single-File Flask App

All SQLAlchemy models and Flask route handlers MUST reside in `app.py`. Supporting
utilities (management scripts, migrations) belong under `scripts/`; HTML rendering belongs
in `templates/`. No additional Python packages or sub-modules may be introduced without
explicit justification and a constitution amendment.

**Rationale**: Keeps the project navigable for a single-developer context; avoids
premature abstraction in a tournament-scoped application.

### II. HTMX-Driven Frontend

All dynamic UI interactions MUST be implemented with HTMX. JavaScript frameworks (React,
Vue, Alpine, etc.) are prohibited. Route conventions:

- `/ui/...` routes MUST return HTML fragments (no JSON).
- `/admin/...` routes MUST return full-page templates rendered from `templates/`.
- JSON API routes (`/divisions/...`, `/rings/...`, `/matches/...`) MAY return JSON for
  programmatic consumers.
- Inline HTML in route handlers is prohibited; all rendering MUST use template files.
- HTMX requests that fail authentication MUST receive a `401` + `HX-Redirect` response
  header, not a redirect status code.

**Rationale**: HTMX keeps the frontend thin, eliminates a build toolchain, and is
appropriate for a real-time competition dashboard with modest interactivity requirements.

### III. Test-Every-Feature (NON-NEGOTIABLE)

Every new page route or functional behaviour change MUST be accompanied by pytest tests.
Tests MUST:

- Use the in-memory SQLite fixture (`DATABASE_URL=sqlite:///:memory:`).
- Set `WTF_CSRF_ENABLED = False` in the test configuration.
- Require no live PostgreSQL connection.

**Rationale**: Ensures correctness of bracket logic, scoring, and ring assignment without
requiring tournament infrastructure at test time.

### IV. ORM-Only Data Access

All database reads and writes MUST use the Flask-SQLAlchemy ORM:

- Writes: `db.session.add()`, `db.session.commit()`, `db.session.flush()`.
- Reads: `Model.query.get_or_404(id)`, `Model.query.filter_by(...)`, etc.
- Raw SQL in `app.py` or templates is prohibited.
- Schema changes MUST be implemented as idempotent standalone migration scripts under
  `scripts/`, following the `migrate_add_*.py` pattern (check column existence before
  `ALTER TABLE`).

**Rationale**: Keeps database interaction consistent and prevents SQL injection; idempotent
migrations allow safe re-runs against any environment.

### V. Secure by Default

- Every admin and scorekeeper route MUST be protected with the `@login_required` decorator.
- CSRF protection is enabled globally via Flask-WTF and MUST NOT be disabled in production.
- Authentication MUST delegate to Supabase Auth; credentials are never stored locally.
- Secrets (`SECRET_KEY`, `SUPABASE_KEY`, database credentials) MUST NOT be committed to
  source control; they are loaded from `.env` (local) or S3 `secrets.json` (deployed via
  Zappa `remote_env`).

**Rationale**: Competition data and scorekeeping access must be protected against
unauthorized modification during live events.

## Technology Stack & Constraints

- **Language**: Python 3.13 — no older versions.
- **Package manager**: `uv`; dependencies declared in `pyproject.toml` and locked in
  `uv.lock`. New dependencies MUST be added with `uv add`.
- **Backend framework**: Flask with Flask-SQLAlchemy and Flask-WTF (CSRF).
- **Database**: PostgreSQL via `psycopg2-binary` in production; SQLite in-memory for tests.
  Connection configured via `DATABASE_URL` (preferred) or individual `user`/`password`/
  `host`/`port`/`dbname` env vars.
- **Auth**: Supabase Auth (`SUPABASE_URL` + `SUPABASE_KEY`). Required at startup.
- **Frontend**: Jinja2 templates + HTMX. All HTML MUST be rendered from files in
  `templates/`.
- **Deployment**: AWS Lambda via Zappa. Two stages: `dev` (profile `personal`) and `prod`
  (profile `gdtkd`). Remote env loaded from `secrets.json` stored in S3.

## Development Workflow

1. **Install dependencies**: `uv sync`.
2. **Run locally**: `uv run flask run` (requires `.env` with all required vars).
3. **Run tests**: `SECRET_KEY=test SUPABASE_URL=https://test.supabase.co SUPABASE_KEY=test uv run pytest tests/ -x -q`.
4. **Schema migrations**: write an idempotent script in `scripts/migrate_<description>.py`
   and run it manually against each target environment.
5. **Deploy**: `uv run zappa update <stage>` after ensuring `zappa_settings.json` and S3
   secrets are current.
6. **Code review gate**: All PRs MUST pass the full pytest suite and satisfy the
   Constitution Check in the feature plan before merge.

## Governance

This constitution supersedes all other documented practices. Any amendment requires:

1. A pull request updating `.specify/memory/constitution.md` with an incremented version
   number following semantic versioning:
   - **MAJOR**: Backward-incompatible principle removal or redefinition.
   - **MINOR**: New principle or section added.
   - **PATCH**: Clarifications, wording fixes, non-semantic refinements.
2. Version bump rationale documented in the Sync Impact Report (HTML comment at top of
   this file).
3. Propagation of changes to affected templates under `.specify/templates/`.
4. All active feature plans MUST be reviewed for constitution compliance after a MAJOR
   version bump.

Compliance is verified during code review using the Constitution Check section in each
feature's `plan.md`. Complexity violations MUST be justified in the Complexity Tracking
table of the relevant plan.

**Version**: 1.0.0 | **Ratified**: 2026-03-31 | **Last Amended**: 2026-03-31
