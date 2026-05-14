"""
core/activity_store.py — SQLite activity log for PAW book access tracking.

Schema:
  sessions — one row per detected user session (login proxy)
  hits     — one row per book open within a session
  snapshot — last known used_date per book (for change detection)

A session starts when a user's book activity is detected and there is no
existing session for that user within SESSION_GAP_HOURS. Multiple book opens
in the same sitting are grouped under one session.
"""

import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta

DB_PATH          = Path(__file__).parent.parent / 'activity' / 'activity.db'
SESSION_GAP_HOURS = 2


def _conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                user        TEXT NOT NULL,
                started_at  TEXT NOT NULL,
                last_seen   TEXT NOT NULL,
                book_count  INTEGER DEFAULT 0
            )
        ''')
        conn.execute('''
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
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS snapshot (
                book_id    TEXT PRIMARY KEY,
                used_date  TEXT,
                updated_at TEXT NOT NULL
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_hits_book    ON hits(book_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_hits_session ON hits(session_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user)')
        conn.commit()


def get_snapshot():
    with _conn() as conn:
        rows = conn.execute('SELECT book_id, used_date FROM snapshot').fetchall()
        return {r['book_id']: r['used_date'] for r in rows}


def process_books(books):
    """
    Diff books against snapshot. For each changed book:
    - Find or create a session for that user within SESSION_GAP_HOURS
    - Record the book open as a hit under that session
    Returns (new_sessions, new_hits).
    """
    now     = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    cutoff  = (now - timedelta(hours=SESSION_GAP_HOURS)).isoformat()
    snapshot = get_snapshot()

    new_sessions = 0
    new_hits     = 0

    with _conn() as conn:
        for book in books:
            book_id   = book.get('id', '')
            used_date = book.get('usedDate') or ''
            used_by   = book.get('usedBy') or ''

            if not used_date:
                continue
            prev = snapshot.get(book_id)
            if prev is None or used_date == prev:
                # First time seeing this book: seed snapshot, don't record a hit.
                # No change: nothing to do.
                continue

            # Find open session for this user within the gap window
            session_row = conn.execute('''
                SELECT id FROM sessions
                WHERE user = ? AND last_seen >= ?
                ORDER BY last_seen DESC LIMIT 1
            ''', (used_by, cutoff)).fetchone()

            if session_row:
                session_id = session_row['id']
                conn.execute('''
                    UPDATE sessions SET last_seen = ?, book_count = book_count + 1 WHERE id = ?
                ''', (now_iso, session_id))
            else:
                session_id = str(uuid.uuid4())
                conn.execute('''
                    INSERT INTO sessions (id, user, started_at, last_seen, book_count)
                    VALUES (?, ?, ?, ?, 1)
                ''', (session_id, used_by, now_iso, now_iso))
                new_sessions += 1

            conn.execute('''
                INSERT INTO hits (session_id, book_id, book_name, book_path, used_date, captured_at, private, owner)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                book_id,
                book.get('name', ''),
                book.get('path', ''),
                used_date,
                now_iso,
                1 if book.get('private') else 0,
                book.get('owner') or book.get('createdBy') or '',
            ))
            new_hits += 1

        # Update snapshot for all books
        conn.executemany('''
            INSERT INTO snapshot (book_id, used_date, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(book_id) DO UPDATE
                SET used_date=excluded.used_date, updated_at=excluded.updated_at
        ''', [(b.get('id', ''), b.get('usedDate') or '', now_iso) for b in books])

        conn.commit()

    return new_sessions, new_hits


def get_stats(days=90):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    with _conn() as conn:
        total_sessions = conn.execute(
            'SELECT COUNT(*) FROM sessions WHERE started_at >= ?', (since,)
        ).fetchone()[0]

        total_hits = conn.execute(
            'SELECT COUNT(*) FROM hits WHERE captured_at >= ?', (since,)
        ).fetchone()[0]

        # Sessions per user — with avg duration and book count
        user_sessions = conn.execute('''
            SELECT user,
                   COUNT(*)                                        AS session_count,
                   SUM(book_count)                                 AS total_books,
                   ROUND(AVG(
                     (JULIANDAY(last_seen) - JULIANDAY(started_at)) * 1440
                   ), 0)                                           AS avg_duration_mins,
                   MAX(last_seen)                                  AS last_seen
            FROM sessions
            WHERE started_at >= ?
            GROUP BY user
            ORDER BY session_count DESC
        ''', (since,)).fetchall()

        # Most opened books
        book_hits = conn.execute('''
            SELECT h.book_id, h.book_name, h.book_path, h.private, h.owner,
                   COUNT(*)                    AS open_count,
                   COUNT(DISTINCT s.user)      AS unique_users,
                   MAX(h.used_date)            AS last_opened,
                   GROUP_CONCAT(DISTINCT s.user) AS users
            FROM hits h
            JOIN sessions s ON h.session_id = s.id
            WHERE h.captured_at >= ?
            GROUP BY h.book_id
            ORDER BY open_count DESC
        ''', (since,)).fetchall()

        # Recent sessions (last 20)
        recent_sessions = conn.execute('''
            SELECT s.id, s.user, s.started_at, s.last_seen, s.book_count,
                   ROUND((JULIANDAY(s.last_seen) - JULIANDAY(s.started_at)) * 1440, 0) AS duration_mins,
                   GROUP_CONCAT(DISTINCT h.book_name, ' · ') AS books_opened
            FROM sessions s
            LEFT JOIN hits h ON h.session_id = s.id
            WHERE s.started_at >= ?
            GROUP BY s.id
            ORDER BY s.started_at DESC
            LIMIT 20
        ''', (since,)).fetchall()

        # Daily activity (sessions + hits per day)
        daily = conn.execute('''
            SELECT DATE(started_at) AS day,
                   COUNT(*)         AS sessions
            FROM sessions
            WHERE started_at >= ?
            GROUP BY DATE(started_at)
            ORDER BY day DESC
            LIMIT 30
        ''', (since,)).fetchall()

    return {
        'totalSessions':  total_sessions,
        'totalHits':      total_hits,
        'userSessions':   [dict(r) for r in user_sessions],
        'bookHits':       [dict(r) for r in book_hits],
        'recentSessions': [dict(r) for r in recent_sessions],
        'dailyActivity':  [dict(r) for r in daily],
        'days':           days,
        'since':          since,
    }


def process_log_entries(entries, book_cache):
    """
    Record activity from wa-proxy log entries.
    entries:    list of (iso_timestamp_str, book_id, login_id)
    book_cache: dict of book_id → {name, path, private, owner}
    Deduplicates: same (user, book) within 60 s = single hit (browser double-fetch).
    Returns (new_sessions, new_hits).
    """
    new_sessions = 0
    new_hits = 0
    seen = {}  # (login_id, book_id) → last datetime

    with _conn() as conn:
        for ts_str, book_id, login_id in entries:
            try:
                ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            except ValueError:
                continue

            key = (login_id, book_id)
            if key in seen and (ts - seen[key]).total_seconds() < 60:
                continue
            seen[key] = ts

            ts_iso = ts.isoformat()
            cutoff = (ts - timedelta(hours=SESSION_GAP_HOURS)).isoformat()

            session_row = conn.execute('''
                SELECT id FROM sessions
                WHERE user = ? AND last_seen >= ?
                ORDER BY last_seen DESC LIMIT 1
            ''', (login_id, cutoff)).fetchone()

            if session_row:
                session_id = session_row['id']
                conn.execute('''
                    UPDATE sessions SET last_seen = ?, book_count = book_count + 1 WHERE id = ?
                ''', (ts_iso, session_id))
            else:
                session_id = str(uuid.uuid4())
                conn.execute('''
                    INSERT INTO sessions (id, user, started_at, last_seen, book_count)
                    VALUES (?, ?, ?, ?, 1)
                ''', (session_id, login_id, ts_iso, ts_iso))
                new_sessions += 1

            book = book_cache.get(book_id, {})
            conn.execute('''
                INSERT INTO hits
                    (session_id, book_id, book_name, book_path, used_date, captured_at, private, owner)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id, book_id,
                book.get('name', book_id),
                book.get('path', ''),
                ts_iso, ts_iso,
                1 if book.get('private') else 0,
                book.get('owner', ''),
            ))
            new_hits += 1

        conn.commit()

    return new_sessions, new_hits


def purge_old(days=90):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _conn() as conn:
        conn.execute('DELETE FROM hits WHERE captured_at < ?', (cutoff,))
        conn.execute('DELETE FROM sessions WHERE started_at < ?', (cutoff,))
        conn.commit()
