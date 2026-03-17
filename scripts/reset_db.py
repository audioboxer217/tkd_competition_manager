try:
    from scripts._bootstrap import add_repo_root_to_path
except ModuleNotFoundError:  # Allows `python scripts/reset_db.py`
    from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from app import app, db

# Create an application context
with app.app_context():
    db.drop_all()
    print("Database tables dropped in Supabase.")
    db.create_all()
    print("Database tables created in Supabase.")
