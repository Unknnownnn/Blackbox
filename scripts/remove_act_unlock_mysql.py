#!/usr/bin/env python3
"""
Standalone script to preview and delete rows from the `act_unlocks` table using direct MySQL connection.
This script does NOT import the Flask app and therefore avoids dependencies like eventlet.

Usage examples (PowerShell):

# Show matching rows (no deletion):
python .\scripts\remove_act_unlock_mysql.py --act "ACT II" --user 5 --host 127.0.0.1 --port 3306 --db ctf_platform --db-user ctf_user --db-pass "ctf_password"

# Delete matching rows after confirmation:
python .\scripts\remove_act_unlock_mysql.py --act "ACT II" --user 5 --all --host 127.0.0.1 --port 3306 --db ctf_platform --db-user ctf_user --db-pass "ctf_password"

# Delete everything (dangerous):
python .\scripts\remove_act_unlock_mysql.py --all --yes-delete-all --host 127.0.0.1 --port 3306 --db ctf_platform --db-user ctf_user --db-pass "ctf_password"

If you run the DB inside Docker and want to execute SQL directly from host without installing Python dependencies, see the docker/mysql CLI examples in the README below.
"""

import argparse
import os
import sys
import pymysql
from pymysql.cursors import DictCursor


def parse_args():
    p = argparse.ArgumentParser(description='Preview and optionally delete act_unlock records via direct MySQL connection')
    p.add_argument('--act', help='ACT name to filter, e.g. "ACT II"', default=None)
    p.add_argument('--user', type=int, help='User id to filter', default=None)
    p.add_argument('--team', type=int, help='Team id to filter', default=None)
    p.add_argument('--all', action='store_true', help='Delete all matching rows (default is preview only)')
    p.add_argument('--yes-delete-all', action='store_true', help='When used with --all, skip confirmation')
    p.add_argument('--host', default=os.getenv('DATABASE_HOST', '127.0.0.1'))
    p.add_argument('--port', type=int, default=int(os.getenv('DATABASE_PORT', 3306)))
    p.add_argument('--db', default=os.getenv('DATABASE_NAME', 'ctf_platform'))
    p.add_argument('--db-user', default=os.getenv('DATABASE_USER', 'ctf_user'))
    p.add_argument('--db-pass', default=os.getenv('DATABASE_PASSWORD'))
    return p.parse_args()


def build_where_clause(args, params):
    where = []
    if args.act:
        where.append('act = %s')
        params.append(args.act)
    if args.user is not None:
        where.append('user_id = %s')
        params.append(args.user)
    if args.team is not None:
        where.append('team_id = %s')
        params.append(args.team)
    if where:
        return 'WHERE ' + ' AND '.join(where)
    return ''


def main():
    args = parse_args()

    if args.db_pass is None:
        # Prompt for password if not provided
        import getpass
        args.db_pass = getpass.getpass(prompt='MySQL password for user %s: ' % args.db_user)

    try:
        conn = pymysql.connect(
            host=args.host,
            port=args.port,
            user=args.db_user,
            password=args.db_pass,
            database=args.db,
            charset='utf8mb4',
            cursorclass=DictCursor,
            autocommit=False
        )
    except Exception as e:
        print('Could not connect to database:', e)
        sys.exit(2)

    try:
        params = []
        where_clause = build_where_clause(args, params)
        select_sql = f"SELECT id, act, user_id, team_id, unlocked_by_challenge_id, unlocked_at FROM act_unlocks {where_clause} ORDER BY unlocked_at;"

        with conn.cursor() as cur:
            cur.execute(select_sql, params)
            rows = cur.fetchall()

        if not rows:
            print('No matching act_unlock records found.')
            return

        print(f'Found {len(rows)} record(s):')
        for r in rows:
            print(f" - id={r['id']} act={r['act']} user_id={r['user_id']} team_id={r['team_id']} unlocked_by_challenge_id={r['unlocked_by_challenge_id']} unlocked_at={r['unlocked_at']}")

        if not args.all:
            print('\nPreview only. Re-run with --all to remove these records.')
            return

        if not args.yes_delete_all:
            confirm = input('\nType DELETE to permanently remove the above rows: ')
            if confirm != 'DELETE':
                print('Aborted. No changes made.')
                return

        # Build delete
        params = []
        where_clause = build_where_clause(args, params)
        if not where_clause and not args.all:
            print('Refusing to delete all rows without --all.')
            return

        delete_sql = f"DELETE FROM act_unlocks {where_clause};"
        with conn.cursor() as cur:
            affected = cur.execute(delete_sql, params)
        conn.commit()
        print(f'Deleted {affected} row(s).')

    except Exception as e:
        conn.rollback()
        print('Error:', e)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
