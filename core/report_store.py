"""
core/report_store.py — SQLite store for published report data
─────────────────────────────────────────────────────────────
Handles all data-at-rest for the report builder:
  - Dataset snapshots   (frozen TM1 data captured at publish time)
  - Publish audit log   (who published what and when)
  - Note CSV data       (finance-uploaded tables for notes pages — future)

Why SQLite and not JSON files?
  - Single file to back up (report_builder/data.db)
  - Atomic writes — SQLite uses transactions, no partial-write corruption risk
  - Audit log is a natural table — easy to query
  - chmod 600 on one file is cleaner than securing a directory tree

SQLite basics for reference:
  - sqlite3 is in Python's standard library — no install needed
  - A "connection" is your handle to the database file
  - A "cursor" executes SQL statements
  - "?" placeholders prevent SQL injection (never use f-strings in SQL)
  - Transactions: changes are batched and committed atomically
"""

import sqlite3
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

# Database file location — sibling to definitions/, drafts/ etc.
_DB_PATH = Path(__file__).parent.parent / 'report_builder' / 'data.db'


# ── Connection ────────────────────────────────────────────────────────────────

def _connect():
    """Open a connection to the database.

    check_same_thread=False is safe here because Flask handles its own
    thread safety at the request level. We open a fresh connection per
    operation rather than sharing one connection across threads.
    """
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)

    # Row factory: makes rows behave like dicts (row['column_name'])
    # instead of plain tuples (row[0]). Much easier to work with.
    conn.row_factory = sqlite3.Row

    # Enable WAL mode: Write-Ahead Logging
    # Allows reads and writes to happen concurrently without blocking each other.
    # Better for a web app where multiple requests may hit the DB at once.
    conn.execute('PRAGMA journal_mode=WAL')

    # Foreign key enforcement is off by default in SQLite — turn it on.
    conn.execute('PRAGMA foreign_keys=ON')

    return conn


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db():
    """Create tables if they don't already exist.

    Called once at app startup. Safe to call multiple times — CREATE TABLE
    IF NOT EXISTS is idempotent.
    """
    conn = _connect()
    try:
        # Use a single transaction for all DDL (schema changes)
        with conn:
            conn.executescript("""
                -- Frozen TM1 datasets captured at publish time.
                -- Each (id, version) pair is a unique snapshot.
                CREATE TABLE IF NOT EXISTS report_snapshots (
                    id           TEXT    NOT NULL,
                    version      INTEGER NOT NULL,
                    published_at TEXT    NOT NULL,
                    published_by TEXT    NOT NULL,
                    cube         TEXT    NOT NULL,
                    view         TEXT    NOT NULL,
                    selectors    TEXT,            -- JSON: {dim: member} used at snapshot
                    dataset      TEXT    NOT NULL, -- JSON: full dataset from TM1
                    PRIMARY KEY (id, version)
                );

                -- Every publish action is logged here.
                -- Append-only — rows are never updated or deleted.
                CREATE TABLE IF NOT EXISTS publish_log (
                    log_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                    def_id    TEXT    NOT NULL,
                    version   INTEGER NOT NULL,
                    action    TEXT    NOT NULL,  -- 'publish', 'republish'
                    actor     TEXT    NOT NULL,
                    timestamp TEXT    NOT NULL,
                    notes     TEXT               -- optional free text
                );

                -- Finance-uploaded CSV data for notes tables (future).
                -- Stored as parsed JSON so it can be queried and rendered.
                CREATE TABLE IF NOT EXISTS note_csv_data (
                    note_id     TEXT NOT NULL,
                    period      TEXT NOT NULL,   -- e.g. '2026-03'
                    uploaded_at TEXT NOT NULL,
                    uploaded_by TEXT NOT NULL,
                    filename    TEXT NOT NULL,
                    data        TEXT NOT NULL,   -- JSON: parsed CSV rows
                    PRIMARY KEY (note_id, period)
                );
            """)
        log.info(f'Report store initialised: {_DB_PATH}')
    finally:
        conn.close()


# ── Snapshots ─────────────────────────────────────────────────────────────────

def save_snapshot(def_id, version, published_at, published_by, cube, view, selectors, dataset):
    """Save a dataset snapshot for a published report version.

    Uses INSERT OR REPLACE so re-publishing the same version overwrites cleanly.

    Args:
        def_id       : report definition ID e.g. 'pnl'
        version      : integer version number from meta.version
        published_at : ISO timestamp string
        published_by : author name
        cube         : TM1 cube name
        view         : TM1 view name
        selectors    : dict of {dimension: member} used at snapshot time
        dataset      : full dataset dict returned by _fetch_dataset_internal()
    """
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO report_snapshots
                    (id, version, published_at, published_by, cube, view, selectors, dataset)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    def_id,
                    version,
                    published_at,
                    published_by,
                    cube,
                    view,
                    json.dumps(selectors or {}),
                    json.dumps(dataset),
                )
            )
        log.info(f'Snapshot saved: {def_id} v{version}')
    finally:
        conn.close()


def get_snapshot(def_id, version=None):
    """Retrieve a dataset snapshot.

    Args:
        def_id  : report definition ID
        version : specific version number, or None to get the latest

    Returns:
        dict with snapshot data, or None if not found
    """
    conn = _connect()
    try:
        if version is not None:
            # Fetch a specific version
            row = conn.execute(
                'SELECT * FROM report_snapshots WHERE id=? AND version=?',
                (def_id, version)
            ).fetchone()
        else:
            # Fetch the latest version (highest version number)
            row = conn.execute(
                'SELECT * FROM report_snapshots WHERE id=? ORDER BY version DESC LIMIT 1',
                (def_id,)
            ).fetchone()

        if row is None:
            return None

        # sqlite3.Row acts like a dict — convert to a plain dict for JSON serialisation
        return {
            'id':           row['id'],
            'version':      row['version'],
            'publishedAt':  row['published_at'],
            'publishedBy':  row['published_by'],
            'cube':         row['cube'],
            'view':         row['view'],
            'selectors':    json.loads(row['selectors'] or '{}'),
            'dataset':      json.loads(row['dataset']),
        }
    finally:
        conn.close()


def list_snapshots(def_id):
    """Return summary of all snapshots for a definition (no dataset payload).

    Useful for the history panel — shows what versions have frozen data.
    """
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT id, version, published_at, published_by, cube, view
            FROM report_snapshots
            WHERE id=?
            ORDER BY version DESC
            """,
            (def_id,)
        ).fetchall()
        return [
            {
                'id':          r['id'],
                'version':     r['version'],
                'publishedAt': r['published_at'],
                'publishedBy': r['published_by'],
                'cube':        r['cube'],
                'view':        r['view'],
            }
            for r in rows
        ]
    finally:
        conn.close()


# ── Audit log ─────────────────────────────────────────────────────────────────

def log_publish(def_id, version, action, actor, notes=None):
    """Append a row to the publish audit log.

    This is append-only — never update or delete rows in this table.
    """
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO publish_log (def_id, version, action, actor, timestamp, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    def_id,
                    version,
                    action,
                    actor,
                    datetime.now(timezone.utc).isoformat(),
                    notes,
                )
            )
    finally:
        conn.close()


def get_publish_log(def_id=None, limit=100):
    """Return recent publish log entries, optionally filtered by definition ID.

    Args:
        def_id : filter to a specific report, or None for all reports
        limit  : max rows to return (default 100, most recent first)

    Returns:
        list of dicts
    """
    conn = _connect()
    try:
        if def_id:
            rows = conn.execute(
                """
                SELECT * FROM publish_log
                WHERE def_id=?
                ORDER BY log_id DESC
                LIMIT ?
                """,
                (def_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM publish_log
                ORDER BY log_id DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Note CSV data (future) ────────────────────────────────────────────────────

def save_note_csv(note_id, period, uploaded_by, filename, data):
    """Save finance-uploaded CSV data for a notes table.

    Args:
        note_id     : note definition ID e.g. 'note-9-ppe'
        period      : period string e.g. '2026-03'
        uploaded_by : author name
        filename    : original filename for audit trail
        data        : list of dicts (parsed CSV rows)
    """
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO note_csv_data
                    (note_id, period, uploaded_at, uploaded_by, filename, data)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    note_id,
                    period,
                    datetime.now(timezone.utc).isoformat(),
                    uploaded_by,
                    filename,
                    json.dumps(data),
                )
            )
        log.info(f'Note CSV saved: {note_id} / {period}')
    finally:
        conn.close()


def get_note_csv(note_id, period):
    """Retrieve note CSV data for a specific note and period.

    Returns:
        dict with metadata + parsed data rows, or None if not found
    """
    conn = _connect()
    try:
        row = conn.execute(
            'SELECT * FROM note_csv_data WHERE note_id=? AND period=?',
            (note_id, period)
        ).fetchone()
        if row is None:
            return None
        return {
            'noteId':     row['note_id'],
            'period':     row['period'],
            'uploadedAt': row['uploaded_at'],
            'uploadedBy': row['uploaded_by'],
            'filename':   row['filename'],
            'data':       json.loads(row['data']),
        }
    finally:
        conn.close()
