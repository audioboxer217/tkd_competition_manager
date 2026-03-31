"""Generate a new API bearer token and store its hash in the database.

Usage::

    uv run scripts/generate_api_token.py --name "My CI pipeline"

The plaintext token is printed **once** to stdout and never stored.  Only the
SHA-256 hash is persisted in the ``api_token`` table.
"""

import argparse

try:
    from scripts._bootstrap import add_repo_root_to_path
except ModuleNotFoundError:  # Allows `python scripts/generate_api_token.py`
    from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from api import _generate_raw_token, _hash_token
from app import app
from models import ApiToken, db


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a new API bearer token.")
    parser.add_argument("--name", required=True, help="Human-readable label for this token.")
    parser.add_argument("--user-id", default=None, help="Optional Supabase user ID to associate with this token.")
    args = parser.parse_args()

    raw_token = _generate_raw_token()
    token_hash = _hash_token(raw_token)

    with app.app_context():
        token = ApiToken(name=args.name, token_hash=token_hash, user_id=args.user_id)
        db.session.add(token)
        db.session.commit()
        print(f"Token '{args.name}' created (id={token.id}).")
        print()
        print("Bearer token (copy now — will NOT be shown again):")
        print()
        print(f"  {raw_token}")
        print()


if __name__ == "__main__":
    main()
