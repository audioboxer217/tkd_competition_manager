"""Migration: create the api_token table if it does not already exist.

Safe to run against existing databases — uses ``CREATE TABLE IF NOT EXISTS``
so it is idempotent.

Usage::

    uv run scripts/migrate_add_api_token_table.py
"""

try:
    from scripts._bootstrap import add_repo_root_to_path
except ModuleNotFoundError:  # Allows `python scripts/migrate_add_api_token_table.py`
    from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from sqlalchemy import inspect, text

from app import ApiToken, app, db


def main() -> None:
    with app.app_context():
        inspector = inspect(db.engine)
        if "api_token" in inspector.get_table_names():
            print("Table 'api_token' already exists — nothing to do.")
            return

        # Create only the new table, leaving all others untouched.
        ApiToken.__table__.create(db.engine)
        print("Table 'api_token' created successfully.")


if __name__ == "__main__":
    main()
