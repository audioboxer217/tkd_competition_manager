"""Migration: add position column to competitor table.

Run this script once against an existing database that was created before the
``position`` column was added to the ``Competitor`` model.  It is safe to run
multiple times – it checks whether the column already exists before applying
any changes.

Usage::

    python migrate_add_position.py
"""

from sqlalchemy import text

try:
    from scripts._bootstrap import add_repo_root_to_path
except ModuleNotFoundError:  # Allows `python scripts/migrate_add_position.py`
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
        if column_exists(conn, "competitor", "position"):
            print("Column 'position' already exists – nothing to do.")
        else:
            print("Adding 'position' column to competitor table…")
            conn.execute(text("ALTER TABLE competitor ADD COLUMN position INTEGER"))
            conn.commit()
            print("Column added.")

        # Populate position for any rows where it is NULL, ordered by id
        # within each division so existing data gets a stable ordering.
        print("Populating NULL position values…")
        if db.engine.dialect.name == "postgresql":
            conn.execute(
                text(
                    """
                    UPDATE competitor
                    SET position = sub.rn
                    FROM (
                        SELECT id,
                               ROW_NUMBER() OVER (
                                   PARTITION BY division_id ORDER BY id
                               ) AS rn
                        FROM competitor
                        WHERE position IS NULL
                    ) sub
                    WHERE competitor.id = sub.id
                    """
                )
            )
        else:
            # SQLite doesn't support the UPDATE … FROM syntax used above;
            # fall back to a Python-level update instead.
            from app import Competitor

            rows = (
                db.session.query(Competitor)
                .filter(Competitor.position.is_(None))
                .order_by(Competitor.division_id, Competitor.id)
                .all()
            )
            counters: dict[int, int] = {}
            for comp in rows:
                counters[comp.division_id] = counters.get(comp.division_id, 0) + 1
                comp.position = counters[comp.division_id]
            db.session.commit()

        conn.commit()
        print("Migration complete.")
