"""Migration: add start_time and end_time columns to the match table.

Run this script once against an existing database that was created before the
``start_time`` / ``end_time`` columns were added to the ``Match`` model.
It is safe to run multiple times – it checks whether each column already
exists before applying any changes.

Usage::

    python scripts/migrate_add_match_times.py
"""

from sqlalchemy import text

try:
    from scripts._bootstrap import add_repo_root_to_path
except ModuleNotFoundError:  # Allows `python scripts/migrate_add_match_times.py`
    from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from app import app, db


def column_exists(conn, table: str, column: str) -> bool:
    """Return True if *column* exists in *table* for the current database."""
    import re

    # Validate table name to prevent SQL injection in the SQLite PRAGMA path.
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        raise ValueError(f"Unsafe table name: {table!r}")

    dialect = conn.dialect.name
    if dialect == "postgresql":
        result = conn.execute(
            text("SELECT 1 FROM information_schema.columns WHERE table_name = :t AND column_name = :c"),
            {"t": table, "c": column},
        )
    else:
        # SQLite – use PRAGMA (table name cannot be parameterised in PRAGMA)
        result = conn.execute(text(f"PRAGMA table_info({table})"))
        return any(row[1] == column for row in result.fetchall())
    return result.fetchone() is not None


with app.app_context():
    with db.engine.connect() as conn:
        dialect = conn.dialect.name
        col_type = "TIMESTAMP WITH TIME ZONE" if dialect == "postgresql" else "DATETIME"

        for col in ("start_time", "end_time"):
            if column_exists(conn, "match", col):
                print(f"Column '{col}' already exists – nothing to do.")
            else:
                print(f"Adding '{col}' column to match table…")
                conn.execute(text(f"ALTER TABLE match ADD COLUMN {col} {col_type}"))
                conn.commit()
                print(f"Column '{col}' added.")

    print("Migration complete.")
