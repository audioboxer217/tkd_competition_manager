# Development Guide

## Setup

### Prerequisites

- Python 3.13
- `uv` (package manager; install from https://docs.astral.sh/uv/getting-started/installation/)
- PostgreSQL (production) or use SQLite (dev/test)

### First-time setup

```bash
# Clone repo
git clone <repo-url>
cd tkd_competition_manager

# Install dependencies
uv sync

# Create .env file (see README.md for required vars)
# Copy example or create with:
#   SECRET_KEY=<random-string>
#   SUPABASE_URL=https://<project>.supabase.co
#   SUPABASE_KEY=<your-key>

# Initialize database (if needed)
uv run scripts/init_db.py

# Run tests to verify setup
uv run pytest tests/ -x -q
```

### Seed development data

```bash
APP_ENV=dev uv run scripts/seed_dev_db.py
```

This creates sample rings, divisions, competitors, and matches for testing.

## Testing

### Run all tests

```bash
uv run pytest tests/ -x -q
```

- `-x` — Stop at first failure
- `-q` — Quiet (summary only)
- Uses in-memory SQLite; no PostgreSQL needed

### Run specific test

```bash
uv run pytest tests/test_app.py::test_name -vvs
```

- `-vvs` — Verbose output with print statements
- Useful for debugging

### Run tests for a route

```bash
uv run pytest tests/test_app.py -k "ring" -vvs
```

Runs all tests matching "ring" in the name.

### Check test coverage

```bash
uv run pytest tests/ --cov=. --cov-report=term-missing
```

(Optional; requires `pytest-cov` in dependencies.)

## Coding Patterns

### Adding a model

**In `models.py`:**

```python
class MyModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    division_id = db.Column(db.Integer, db.ForeignKey("division.id"), nullable=False)
    
    division = db.relationship("Division", backref="my_models")
```

**In `app.py` or `api.py`:**

```python
from models import MyModel

# Query
model = MyModel.query.get_or_404(id)

# Create
new_model = MyModel(name="...", division_id=1)
db.session.add(new_model)
db.session.commit()

# Update
model.name = "..."
db.session.commit()

# Delete
db.session.delete(model)
db.session.commit()
```

**In tests (`tests/test_app.py`):**

```python
def test_my_model(client, app):
    with app.app_context():
        model = MyModel(name="Test", division_id=1)
        db.session.add(model)
        db.session.commit()
        
        fetched = MyModel.query.get(model.id)
        assert fetched.name == "Test"
```

### Adding an API endpoint

**In `api.py`:**

```python
@api_v1.route("/my-resource", methods=["GET"])
@api_login_required
def get_my_resource():
    resources = MyModel.query.all()
    return success_response([{"id": r.id, "name": r.name} for r in resources])

@api_v1.route("/my-resource", methods=["POST"])
@api_login_required
def create_my_resource():
    data = request.get_json() or {}
    
    if not data.get("name"):
        return error_response("BAD_REQUEST", "name is required", {"field": "name"}, 400)
    
    model = MyModel(name=data["name"])
    db.session.add(model)
    db.session.commit()
    
    return success_response({"id": model.id, "name": model.name}, 201)
```

**Response helpers (in `api.py`):**

```python
def success_response(data, status_code=200):
    return jsonify({"data": data, "error": None}), status_code

def error_response(code, message, details=None, status_code=400):
    return jsonify({"data": None, "error": {"code": code, "message": message, "details": details or {}}}), status_code
```

**In tests:**

```python
def test_create_my_resource(client, token):
    resp = client.post(
        "/api/v1/my-resource",
        json={"name": "Test Resource"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201
    assert resp.json["data"]["name"] == "Test Resource"

def test_create_my_resource_missing_name(client, token):
    resp = client.post(
        "/api/v1/my-resource",
        json={},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 400
    assert resp.json["error"]["code"] == "BAD_REQUEST"
    assert resp.json["error"]["details"]["field"] == "name"
```

### Adding a UI route and template

**In `app.py`:**

```python
@app.route("/admin/my-page")
@login_required
def my_page():
    resources = MyModel.query.all()
    return render_template("my_page.html", resources=resources)

@app.route("/ui/my-resource/<int:id>", methods=["GET"])
@login_required
def my_resource_fragment(id):
    resource = MyModel.query.get_or_404(id)
    return render_template("fragments/my_resource.html", resource=resource)
```

**In `templates/my_page.html`:**

```html
{% extends "base.html" %}

{% block content %}
<h1>My Page</h1>
<div id="resources">
  {% for resource in resources %}
    {% include "fragments/my_resource.html" %}
  {% endfor %}
</div>
{% endblock %}
```

**In `templates/fragments/my_resource.html`:**

```html
<div class="resource" id="resource-{{ resource.id }}">
  <h3>{{ resource.name }}</h3>
  <button hx-delete="/ui/my-resource/{{ resource.id }}" hx-target="#resource-{{ resource.id }}" hx-swap="outerHTML">
    Delete
  </button>
</div>
```

**In tests:**

```python
def test_my_page(client):
    resp = client.get("/admin/my-page")
    assert resp.status_code == 200
    assert b"My Page" in resp.data

def test_my_resource_fragment(client):
    # Create a test resource
    with client.application.app_context():
        r = MyModel(name="Test")
        db.session.add(r)
        db.session.commit()
        resource_id = r.id
    
    resp = client.get(f"/ui/my-resource/{resource_id}")
    assert resp.status_code == 200
    assert b"Test" in resp.data
```

## Import Guidelines

### Correct import order

```python
# ✓ In api.py:
from models import MyModel, db, VALID_EVENT_TYPES
from flask import Blueprint

# ✓ In app.py:
from api import api_v1, success_response
from models import MyModel, db
from flask import Flask

# ✗ In models.py:
# from api import something        ← WRONG
# from app import something        ← WRONG
```

### Fixture imports in tests

```python
# In tests/conftest.py:
from models import db, MyModel
from api import _generate_raw_token, _hash_token
from app import app

# Then use them in tests:
def test_something(client, app):
    with app.app_context():
        model = MyModel(...)
        db.session.add(model)
        db.session.commit()
```

## CSRF Protection

### Form templates

```html
<form method="POST" action="/admin/my-resource">
  {{ csrf_token() }}
  <input type="text" name="name" />
  <button type="submit">Save</button>
</form>
```

### AJAX requests

```javascript
// Fetch the CSRF token
const token = document.querySelector('meta[name="csrf-token"]').content;

fetch("/admin/my-resource", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-CSRFToken": token
  },
  body: JSON.stringify({ name: "..." })
});
```

### HTMX requests

HTMX includes CSRF token automatically if it's in a `<meta>` or `<input>` tag.

### API routes

API routes (in `api.py`) are exempt from CSRF:
```python
csrf.exempt(api_v1)  # Set in app.py
```

Because API uses Bearer token auth, not session cookies, CSRF isn't needed.

## Database Transactions

### Single operations

```python
model = MyModel(name="...")
db.session.add(model)
db.session.commit()  # Explicit commit
```

### Multiple operations (atomic)

```python
try:
    model1 = MyModel(name="A")
    model2 = MyModel(name="B")
    db.session.add_all([model1, model2])
    db.session.commit()
except Exception:
    db.session.rollback()
    raise
```

### Flushing (for immediate ID access)

```python
model = MyModel(name="...")
db.session.add(model)
db.session.flush()        # Get auto-generated ID without committing
print(model.id)           # ID is now available
db.session.commit()
```

## Common Tasks

### Query with relationships

```python
# Avoid N+1: use joinedload
from sqlalchemy.orm import joinedload

matches = Match.query.options(
    joinedload(Match.division),
    joinedload(Match.ring)
).all()

for match in matches:
    print(match.division.name)  # No extra queries
```

### Validate status before updating

```python
# Match status validation
from models import COMPLETED_MATCH_STATUSES

if match.status in COMPLETED_MATCH_STATUSES:
    return error_response("CONFLICT", "Cannot update a completed match", {}, 409)

match.status = "In Progress"
db.session.commit()
```

### Check for deprecation on legacy routes

Legacy routes (`/divisions`, `/matches/<id>/result`, etc.) return:
```python
resp = make_response(success_response(...))
resp.headers["Deprecation"] = "true"
resp.headers["Link"] = "</api/v1>; rel=\"successor-version\""
return resp
```

Clients should migrate to `/api/v1`.

### Generate API tokens

**For testing:**
```python
from api import _generate_raw_token, _hash_token

raw = _generate_raw_token()  # 43-char string
hashed = _hash_token(raw)
token = ApiToken(name="Test", token_hash=hashed, created_by_user="test@example.com")
db.session.add(token)
db.session.commit()
```

**For users:**
- Use `/admin/api-tokens` UI page
- Token is shown only once; user must copy/save it
- Only hash is stored in database

## Debugging

### Print debugging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug(f"Value: {my_var}")
```

Or use `print()` with `-vvs`:
```bash
uv run pytest tests/test_app.py::test_name -vvs
```

### Database inspection

```bash
# Reset to clean state (dev only)
uv run scripts/reset_db.py

# Re-seed
APP_ENV=dev uv run scripts/seed_dev_db.py
```

### Test a single route

```python
def test_debug_route(client):
    resp = client.get("/admin")
    print(resp.data.decode())  # See full HTML
    assert resp.status_code == 200
```

Run with `-vvs` to see print output:
```bash
uv run pytest tests/test_app.py::test_debug_route -vvs
```

## Common Mistakes to Avoid

1. **Forgetting `db.session.commit()`** — Changes are queued but not saved
2. **Importing from `models.py` in `api.py` correctly** — It's OK; just don't do the reverse
3. **Returning plain dicts instead of `success_response()`** — Always use the envelope
4. **Not validating input** — Always check `request.get_json()`, strip/validate strings
5. **Async routes without proper handling** — This app is synchronous; no `await` needed
6. **Missing CSRF token in forms** — Template should include `{{ csrf_token() }}`
7. **Hardcoding status/event_type strings** — Use constants: `COMPLETED_MATCH_STATUSES`, `VALID_EVENT_TYPES`
