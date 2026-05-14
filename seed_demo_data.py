"""
seed_demo_data.py — Insert realistic fake activity into activity.db for demo/video.

Usage:
    python3 seed_demo_data.py [--db PATH] [--days 30] [--clear]

Flags:
    --db PATH   Path to activity.db (default: activity/activity.db beside this script)
    --days N    Spread activity over N days (default: 30)
    --clear     Wipe sessions/hits/snapshot before seeding (keeps schema)
"""

import sqlite3
import uuid
import random
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Real book IDs from V11 PAW instance ─────────────────────────────────────
BOOKS = [
    {
        'id':      'df156fc8-957f-4c88-9620-6475d65b512f',
        'name':    'JDLove Test 24Retail',
        'path':    '/shared/JDLove Test 24Retail',
        'private': 0,
        'owner':   'admin',
    },
    {
        'id':      '357b1abb-a595-4a24-b4d4-27db22e8743c',
        'name':    'JDLove Test 2 24Retail',
        'path':    '/shared/JDLove Test 2 24Retail',
        'private': 0,
        'owner':   'admin',
    },
]

# ── Simulated TM1 users ──────────────────────────────────────────────────────
USERS = ['jsmith', 'mwilliams', 'rbrown', 'ljones', 'dchen', 'kpatel', 'admin']

# Per-user activity weight (higher = opens more books)
USER_WEIGHT = {
    'jsmith':     5,
    'mwilliams':  4,
    'rbrown':     3,
    'ljones':     2,
    'dchen':      3,
    'kpatel':     2,
    'admin':      1,
}

# Per-book popularity weight
BOOK_WEIGHT = {
    'df156fc8-957f-4c88-9620-6475d65b512f': 7,   # more popular
    '357b1abb-a595-4a24-b4d4-27db22e8743c': 3,
}

SESSION_GAP_HOURS = 2


def _weighted_choice(items, weight_fn):
    weights = [weight_fn(i) for i in items]
    return random.choices(items, weights=weights, k=1)[0]


def _business_hour_offset():
    """Return a random offset in seconds that falls within 8am–6pm."""
    hour  = random.randint(8, 17)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return timedelta(hours=hour, minutes=minute, seconds=second)


def _gen_sessions(days: int):
    """
    Generate a list of (user, book_id, ts) tuples spread over `days` days.
    Weekdays get more activity; weekends get very little.
    """
    now   = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = now - timedelta(days=days)

    events = []
    day = start
    while day < now:
        weekday = day.weekday()  # 0=Mon, 6=Sun
        if weekday < 5:          # weekday
            sessions_today = random.randint(3, 9)
        elif weekday == 5:       # Saturday
            sessions_today = random.randint(0, 2)
        else:                    # Sunday
            sessions_today = random.randint(0, 1)

        for _ in range(sessions_today):
            user    = _weighted_choice(USERS, lambda u: USER_WEIGHT[u])
            book    = _weighted_choice(BOOKS, lambda b: BOOK_WEIGHT[b['id']])
            ts      = day + _business_hour_offset()
            events.append((user, book, ts))

            # ~40 % chance of opening a second book in same session (5–25 min later)
            if random.random() < 0.4:
                second_book = random.choice(BOOKS)
                ts2 = ts + timedelta(minutes=random.randint(5, 25))
                events.append((user, second_book, ts2))

        day += timedelta(days=1)

    events.sort(key=lambda e: e[2])
    return events


def seed(db_path: Path, days: int, clear: bool):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Ensure schema exists
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            user        TEXT NOT NULL,
            started_at  TEXT NOT NULL,
            last_seen   TEXT NOT NULL,
            book_count  INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS hits (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT NOT NULL REFERENCES sessions(id),
            book_id     TEXT NOT NULL,
            book_name   TEXT NOT NULL,
            book_path   TEXT NOT NULL,
            used_date   TEXT,
            captured_at TEXT NOT NULL,
            private     INTEGER DEFAULT 0,
            owner       TEXT
        );
        CREATE TABLE IF NOT EXISTS snapshot (
            book_id    TEXT PRIMARY KEY,
            used_date  TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_hits_book     ON hits(book_id);
        CREATE INDEX IF NOT EXISTS idx_hits_session  ON hits(session_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user);
    ''')

    if clear:
        conn.executescript('DELETE FROM hits; DELETE FROM sessions; DELETE FROM snapshot;')
        print('Cleared existing activity data.')

    events = _gen_sessions(days)
    print(f'Generated {len(events)} events over {days} days.')

    # Track open sessions per user for gap grouping
    open_sessions = {}   # user → (session_id, last_ts)
    new_sessions  = 0
    new_hits      = 0

    for user, book, ts in events:
        ts_iso = ts.isoformat()

        # Check for open session within gap window
        if user in open_sessions:
            sid, last_ts = open_sessions[user]
            if (ts - last_ts).total_seconds() <= SESSION_GAP_HOURS * 3600:
                # Extend existing session
                conn.execute(
                    'UPDATE sessions SET last_seen = ?, book_count = book_count + 1 WHERE id = ?',
                    (ts_iso, sid)
                )
                open_sessions[user] = (sid, ts)
            else:
                # Gap too large — start new session
                sid = str(uuid.uuid4())
                conn.execute(
                    'INSERT INTO sessions (id, user, started_at, last_seen, book_count) VALUES (?, ?, ?, ?, 1)',
                    (sid, user, ts_iso, ts_iso)
                )
                open_sessions[user] = (sid, ts)
                new_sessions += 1
        else:
            sid = str(uuid.uuid4())
            conn.execute(
                'INSERT INTO sessions (id, user, started_at, last_seen, book_count) VALUES (?, ?, ?, ?, 1)',
                (sid, user, ts_iso, ts_iso)
            )
            open_sessions[user] = (sid, ts)
            new_sessions += 1

        conn.execute(
            '''INSERT INTO hits
               (session_id, book_id, book_name, book_path, used_date, captured_at, private, owner)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (sid, book['id'], book['name'], book['path'], ts_iso, ts_iso,
             book['private'], book['owner'])
        )
        new_hits += 1

    # Seed snapshot so real poll mode doesn't re-record these as new
    now_iso = datetime.now(timezone.utc).isoformat()
    for book in BOOKS:
        conn.execute(
            '''INSERT INTO snapshot (book_id, used_date, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(book_id) DO UPDATE
                   SET used_date=excluded.used_date, updated_at=excluded.updated_at''',
            (book['id'], now_iso, now_iso)
        )

    conn.commit()
    conn.close()

    print(f'Seeded: {new_sessions} sessions, {new_hits} hits → {db_path}')


def main():
    parser = argparse.ArgumentParser(description='Seed demo activity data')
    parser.add_argument('--db',    default=None,  help='Path to activity.db')
    parser.add_argument('--days',  type=int, default=30, help='Days of history')
    parser.add_argument('--clear', action='store_true', help='Wipe before seeding')
    args = parser.parse_args()

    if args.db:
        db_path = Path(args.db)
    else:
        db_path = Path(__file__).parent / 'activity' / 'activity.db'

    seed(db_path, args.days, args.clear)


if __name__ == '__main__':
    main()
