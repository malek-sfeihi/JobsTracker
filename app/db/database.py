import sqlite3

from app.core.config import settings

# One row per downloaded email. We keep the raw content (subject, body...) so that when
# the rules improve we can re-classify everything without downloading from Gmail again.
SCHEMA = """
CREATE TABLE IF NOT EXISTS emails (
    id          TEXT PRIMARY KEY,   -- Gmail message id
    thread_id   TEXT NOT NULL,
    sender      TEXT NOT NULL,
    subject     TEXT NOT NULL,
    received_at TEXT NOT NULL,      -- ISO date, e.g. 2026-09-23T14:02:11+00:00
    body        TEXT NOT NULL,
    category    TEXT,               -- confirmation / rejection / ... or NULL if not a job email
    kind        TEXT                -- job / program
);

-- One row per application (company + position), built from the emails above.
CREATE TABLE IF NOT EXISTS applications (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    company  TEXT NOT NULL,
    position TEXT,                  -- NULL when no email mentions the job title
    kind     TEXT NOT NULL,
    status   TEXT,                  -- action_needed / in_progress / ghosted / expired / rejected / offer
    last_activity TEXT,             -- date of the most recent email
    first_activity TEXT,            -- date of the first email (~ when you applied)
    anchor_email_id TEXT,           -- id of the first email: stable across rebuilds, unlike `id`
    rejection_reason TEXT,          -- why they said no (see app/filters/reasons.py)
    rejection_quote TEXT            -- the sentence of the email that says it
);

-- Your manual corrections from the dashboard. Applications are rebuilt from scratch on
-- every sync, so corrections live here and are re-applied each time (NULL = no correction).
CREATE TABLE IF NOT EXISTS overrides (
    anchor_email_id TEXT PRIMARY KEY,
    company  TEXT,
    position TEXT,
    status   TEXT
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row  # lets us read columns by name: row["subject"]
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Upgrade databases created by older versions of the code (a "migration")."""
    _add_column_if_missing(conn, "emails", "application_id", "INTEGER REFERENCES applications(id)")
    _add_column_if_missing(conn, "applications", "status", "TEXT")
    _add_column_if_missing(conn, "applications", "last_activity", "TEXT")
    _add_column_if_missing(conn, "applications", "first_activity", "TEXT")
    _add_column_if_missing(conn, "applications", "anchor_email_id", "TEXT")
    _add_column_if_missing(conn, "applications", "rejection_reason", "TEXT")
    _add_column_if_missing(conn, "applications", "rejection_quote", "TEXT")


def save_override(conn: sqlite3.Connection, anchor_email_id: str, company: str | None,
                  position: str | None, status: str | None) -> None:
    # "Upsert": insert, or if a correction already exists, only overwrite the fields given now
    # (NULL keeps the previous correction - renaming today won't erase yesterday's status fix)
    conn.execute(
        """INSERT INTO overrides (anchor_email_id, company, position, status) VALUES (?, ?, ?, ?)
           ON CONFLICT(anchor_email_id) DO UPDATE SET
               company  = COALESCE(excluded.company, overrides.company),
               position = COALESCE(excluded.position, overrides.position),
               status   = COALESCE(excluded.status, overrides.status)""",
        (anchor_email_id, company, position, status),
    )


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        conn.commit()


def known_email_ids(conn: sqlite3.Connection) -> set[str]:
    return {row["id"] for row in conn.execute("SELECT id FROM emails")}


def save_email(conn: sqlite3.Connection, email: dict, category: str | None, kind: str) -> None:
    # The "?" placeholders let sqlite insert the values safely (never build SQL with f-strings:
    # an email subject containing a quote would break the query, or worse - SQL injection)
    conn.execute(
        """INSERT OR REPLACE INTO emails
           (id, thread_id, sender, subject, received_at, body, category, kind)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (email["id"], email["thread_id"], email["sender"], email["subject"],
         email["received_at"], email["body"], category, kind),
    )
