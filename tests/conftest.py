import os

# Must be set before app.py is imported so the SQLite URI is used instead of PostgreSQL
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest

from app import app as flask_app
from app import db as _db


@pytest.fixture(scope="session")
def app():
    flask_app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
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
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_db(app):
    """Truncate all tables between tests to ensure isolation."""
    yield
    _db.session.rollback()
    for table in reversed(_db.metadata.sorted_tables):
        _db.session.execute(table.delete())
    _db.session.commit()
    _db.session.remove()
