import hashlib
import hmac
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .paths import DB_PATH, ensure_app_dirs


DEFAULT_OPERATOR_PASSWORD = "1234"
PASSWORD_ITERATIONS = 120_000


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS elections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS polls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    election_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    vote_type TEXT NOT NULL DEFAULT 'single',
    sort_order INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (election_id) REFERENCES elections(id) ON DELETE CASCADE,
    UNIQUE (election_id, name)
);

CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    photo_path TEXT DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS voting_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    election_id INTEGER NOT NULL,
    operator_name TEXT DEFAULT '',
    session_date TEXT NOT NULL,
    FOREIGN KEY (election_id) REFERENCES elections(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    election_id INTEGER NOT NULL,
    poll_id INTEGER NOT NULL,
    candidate_id INTEGER NOT NULL,
    voting_session_id INTEGER,
    cast_at TEXT NOT NULL,
    FOREIGN KEY (election_id) REFERENCES elections(id) ON DELETE CASCADE,
    FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
    FOREIGN KEY (voting_session_id) REFERENCES voting_sessions(id) ON DELETE SET NULL
);
"""


def dict_factory(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict:
    return {column[0]: row[index] for index, column in enumerate(cursor.description)}


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    ensure_app_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    ensure_app_dirs()
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
        ensure_default_operator_password(conn)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_default_operator_password(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'operator_password_hash'"
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            ("operator_password_hash", hash_password(DEFAULT_OPERATOR_PASSWORD)),
        )


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        PASSWORD_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        int(iterations),
    ).hex()
    return hmac.compare_digest(digest, expected)


def get_setting(key: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_setting(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def verify_operator_password(password: str) -> bool:
    stored_hash = get_setting("operator_password_hash")
    if not stored_hash:
        set_operator_password(DEFAULT_OPERATOR_PASSWORD)
        stored_hash = get_setting("operator_password_hash")
    return bool(stored_hash and verify_password(password, stored_hash))


def set_operator_password(password: str) -> None:
    set_setting("operator_password_hash", hash_password(password))


def create_election(name: str, description: str = "") -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO elections (name, description, created_at) VALUES (?, ?, ?)",
            (name.strip(), description.strip(), now_iso()),
        )
        return int(cur.lastrowid)


def update_election_status(election_id: int, status: str) -> None:
    if status not in {"draft", "active", "closed"}:
        raise ValueError("Invalid election status")
    with connect() as conn:
        conn.execute("UPDATE elections SET status = ? WHERE id = ?", (status, election_id))


def list_elections() -> list[dict]:
    with connect() as conn:
        return conn.execute("SELECT * FROM elections ORDER BY created_at DESC").fetchall()


def create_poll(election_id: int, name: str) -> int:
    ensure_election_draft(election_id)
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO polls (election_id, name, sort_order) VALUES (?, ?, ?)",
            (election_id, name.strip(), next_sort_order(conn, "polls", "election_id", election_id)),
        )
        return int(cur.lastrowid)


def list_polls(election_id: int) -> list[dict]:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM polls WHERE election_id = ? ORDER BY sort_order, id",
            (election_id,),
        ).fetchall()


def get_poll(poll_id: int) -> dict | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM polls WHERE id = ?", (poll_id,)).fetchone()


def create_candidate(poll_id: int, name: str, description: str, photo_path: str = "") -> int:
    poll = get_poll(poll_id)
    if not poll:
        raise ValueError("Poll not found")
    ensure_election_draft(poll["election_id"])
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO candidates (poll_id, name, description, photo_path, sort_order)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                poll_id,
                name.strip(),
                description.strip(),
                photo_path,
                next_sort_order(conn, "candidates", "poll_id", poll_id),
            ),
        )
        return int(cur.lastrowid)


def list_candidates(poll_id: int) -> list[dict]:
    with connect() as conn:
        return conn.execute(
            """
            SELECT * FROM candidates
            WHERE poll_id = ? AND active = 1
            ORDER BY sort_order, id
            """,
            (poll_id,),
        ).fetchall()


def list_candidates_for_election(election_id: int) -> list[dict]:
    with connect() as conn:
        return conn.execute(
            """
            SELECT c.*, p.name AS poll_name
            FROM candidates c
            JOIN polls p ON p.id = c.poll_id
            WHERE p.election_id = ? AND c.active = 1
            ORDER BY p.sort_order, c.sort_order, c.id
            """,
            (election_id,),
        ).fetchall()


def start_voting_session(election_id: int, operator_name: str = "") -> int:
    ensure_election_active(election_id)
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO voting_sessions (election_id, operator_name, session_date)
            VALUES (?, ?, ?)
            """,
            (election_id, operator_name.strip(), now_iso()),
        )
        return int(cur.lastrowid)


def cast_vote(election_id: int, poll_id: int, candidate_id: int, session_id: int | None) -> None:
    cast_votes(election_id, [(poll_id, candidate_id)], session_id)


def cast_votes(election_id: int, selections: list[tuple[int, int]], session_id: int | None) -> None:
    with connect() as conn:
        status = get_election_status_for_connection(conn, election_id)
        if status != "active":
            label = status or "missing"
            raise ValueError(f"Voting is allowed only for active elections. Current status: {label}.")
        cast_at = now_iso()
        conn.executemany(
            """
            INSERT INTO votes (election_id, poll_id, candidate_id, voting_session_id, cast_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (election_id, poll_id, candidate_id, session_id, cast_at)
                for poll_id, candidate_id in selections
            ],
        )


def get_results(election_id: int) -> list[dict]:
    with connect() as conn:
        return conn.execute(
            """
            SELECT
                p.id AS poll_id,
                p.name AS poll_name,
                c.id AS candidate_id,
                c.name AS candidate_name,
                c.description AS candidate_description,
                COUNT(v.id) AS votes
            FROM polls p
            JOIN candidates c ON c.poll_id = p.id AND c.active = 1
            LEFT JOIN votes v ON v.candidate_id = c.id AND v.poll_id = p.id
            WHERE p.election_id = ?
            GROUP BY p.id, c.id
            ORDER BY p.sort_order, p.id, votes DESC, c.sort_order, c.id
            """,
            (election_id,),
        ).fetchall()


def get_election(election_id: int) -> dict | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM elections WHERE id = ?", (election_id,)).fetchone()


def get_election_status(election_id: int) -> str | None:
    election = get_election(election_id)
    return election["status"] if election else None


def get_election_status_for_connection(conn: sqlite3.Connection, election_id: int) -> str | None:
    row = conn.execute("SELECT status FROM elections WHERE id = ?", (election_id,)).fetchone()
    if not row:
        return None
    return row["status"] if isinstance(row, dict) else row[0]


def is_election_active(election_id: int) -> bool:
    return get_election_status(election_id) == "active"


def ensure_election_active(election_id: int) -> None:
    status = get_election_status(election_id)
    if status != "active":
        label = status or "missing"
        raise ValueError(f"Voting is allowed only for active elections. Current status: {label}.")


def ensure_election_draft(election_id: int) -> None:
    status = get_election_status(election_id)
    if status != "draft":
        label = status or "missing"
        raise ValueError(f"Setup changes are allowed only while an election is Draft. Current status: {label}.")


def copy_photo_to_store(source: str, candidate_id_hint: str) -> str:
    from shutil import copy2

    if not source:
        return ""
    src = Path(source)
    if not src.exists():
        return ""
    from .paths import PHOTOS_DIR

    suffix = src.suffix.lower() or ".jpg"
    target = PHOTOS_DIR / f"candidate_{candidate_id_hint}_{int(datetime.now().timestamp())}{suffix}"
    copy2(src, target)
    return str(target)


def next_sort_order(conn: sqlite3.Connection, table: str, column: str, value: int) -> int:
    row = conn.execute(
        f"SELECT COALESCE(MAX(sort_order), 0) + 1 AS next_order FROM {table} WHERE {column} = ?",
        (value,),
    ).fetchone()
    return int(row["next_order"] if isinstance(row, dict) else row[0])
