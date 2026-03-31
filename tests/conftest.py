import os

# Must be set before app.py is imported so the SQLite URI is used instead of PostgreSQL
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest

from app import app as flask_app
from app import db as _db

# Test user shared by both the session-based and Bearer-token test clients.
_TEST_USER_EMAIL = "test@example.com"
_TEST_USER_ID = "test-user-id"


@pytest.fixture(scope="session")
def app():
    flask_app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": os.environ.get("DATABASE_URL", "sqlite:///:memory:"),
            "WTF_CSRF_ENABLED": False,
        }
    )
    ctx = flask_app.app_context()
    ctx.push()
    _db.create_all()
    yield flask_app
    _db.drop_all()
    ctx.pop()


@pytest.fixture
def client(app):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user"] = {"email": _TEST_USER_EMAIL, "id": _TEST_USER_ID}
    return c


@pytest.fixture
def api_client(app, monkeypatch):
    """Test client for /api/v1 endpoints.

    Patches Supabase ``get_user`` to accept any token and pre-configures
    ``Authorization: Bearer test-token``.  Also carries a Flask session so
    that legacy helper routes (competitor/bracket setup) still pass
    ``login_required``.
    """
    from types import SimpleNamespace

    mock_result = SimpleNamespace(user=SimpleNamespace(email=_TEST_USER_EMAIL, id=_TEST_USER_ID))
    monkeypatch.setattr("app.supabase_client.auth.get_user", lambda _token: mock_result)

    c = app.test_client()
    c.environ_base["HTTP_AUTHORIZATION"] = "Bearer test-token"
    with c.session_transaction() as sess:
        sess["user"] = {"email": _TEST_USER_EMAIL, "id": _TEST_USER_ID}
    return c


@pytest.fixture(autouse=True)
def clean_db(app):
    """Truncate all tables between tests to ensure isolation."""
    yield
    _db.session.rollback()
    for table in reversed(_db.metadata.sorted_tables):
        _db.session.execute(table.delete())
    _db.session.commit()
    _db.session.remove()
