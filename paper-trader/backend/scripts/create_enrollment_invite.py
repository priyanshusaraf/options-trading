"""Explicit local invitation delivery. Never send email or log the returned secret."""
import argparse
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, type=Path, help='Explicit existing local SQLite test/development database')
    parser.add_argument('--email', required=True)
    parser.add_argument('--minutes', type=int, default=60)
    args = parser.parse_args()
    if (os.environ.get('PT_DISABLE_DOTENV') != '1' or os.environ.get('PT_PROVIDER') != 'mock'
            or os.environ.get('PT_EXECUTION') != 'paper' or os.environ.get('PT_LIVE_ACK', '')
            or not args.database.is_absolute() or not args.database.is_file()):
        parser.error('requires disabled dotenv, mock/paper, empty live acknowledgement and explicit existing absolute database path')
    # Pin the selected local authority before any application module import.
    os.environ['PT_DATABASE_URL'] = ''
    os.environ['PT_DB_PATH'] = str(args.database)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.accounts.browser_auth import AuthRefusal, create_invite
    from app.db.migrate import head_revision, schema_version
    from app.db.session import engine
    if schema_version(engine) != head_revision():
        parser.error('database must already have the current schema; this CLI does not migrate')
    try:
        issued = create_invite(args.email, minutes=args.minutes)
    except AuthRefusal:
        parser.error('invitation refused')
    print(issued.token)  # Explicit secret delivery, not application logging or URL transport.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
