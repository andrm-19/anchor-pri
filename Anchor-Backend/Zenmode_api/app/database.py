import json
import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from app.config import DB_FILE


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return dict(row)


def _deserialize_checkin(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    data = _row_to_dict(row)
    if data is None:
        return None

    raw_completed_step_ids = data.get("completed_step_ids") or "[]"
    try:
        data["completed_step_ids"] = json.loads(raw_completed_step_ids)
    except json.JSONDecodeError:
        data["completed_step_ids"] = []

    return data


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(str(DB_FILE))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _table_columns(connection: sqlite3.Connection, table_name: str) -> Set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def init_db() -> None:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)

    with closing(get_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
            """
        )

        user_columns = _table_columns(connection, "users")
        if "created_at" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN created_at TEXT")
            connection.execute(
                "UPDATE users SET created_at = ? WHERE created_at IS NULL",
                (_utc_now(),),
            )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL,
                target_note TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS routine_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                scheduled_time TEXT,
                step_order INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE,
                UNIQUE (goal_id, step_order)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER NOT NULL,
                checkin_date TEXT NOT NULL,
                completed_step_ids TEXT NOT NULL DEFAULT '[]',
                note TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                completion_percent INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE,
                UNIQUE (goal_id, checkin_date)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_goals_user_id ON goals(user_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_steps_goal_id ON routine_steps(goal_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_checkins_goal_id ON daily_checkins(goal_id)"
        )
        connection.commit()


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT id, username, password, created_at
            FROM users
            WHERE LOWER(username) = LOWER(?)
            """,
            (username,),
        ).fetchone()
    return _row_to_dict(row)


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with closing(get_connection()) as connection:
        row = connection.execute(
            "SELECT id, username, password, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return _row_to_dict(row)


def create_user(username: str, password_hash: str) -> Dict[str, Any]:
    created_at = _utc_now()

    with closing(get_connection()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO users (username, password, created_at)
            VALUES (?, ?, ?)
            """,
            (username, password_hash, created_at),
        )
        connection.commit()
        user_id = cursor.lastrowid

    return get_user_by_id(user_id)


def list_users() -> List[Dict[str, Any]]:
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT id, username, created_at
            FROM users
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def create_goal(
    user_id: int,
    title: str,
    description: str,
    category: str,
    target_note: str,
    status: str = "active",
) -> Dict[str, Any]:
    timestamp = _utc_now()

    with closing(get_connection()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO goals (
                user_id, title, description, category, target_note, status,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                title,
                description,
                category,
                target_note,
                status,
                timestamp,
                timestamp,
            ),
        )
        connection.commit()
        goal_id = cursor.lastrowid

    return get_goal_by_id_for_user(goal_id, user_id)


def list_goals_for_user(user_id: int) -> List[Dict[str, Any]]:
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM goals
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_goal_by_id_for_user(goal_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM goals
            WHERE id = ? AND user_id = ?
            """,
            (goal_id, user_id),
        ).fetchone()
    return _row_to_dict(row)


def update_goal(goal_id: int, user_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
    if not updates:
        return get_goal_by_id_for_user(goal_id, user_id)

    fields = [f"{field} = ?" for field in updates]
    values = list(updates.values())
    values.extend([_utc_now(), goal_id, user_id])

    with closing(get_connection()) as connection:
        connection.execute(
            f"""
            UPDATE goals
            SET {", ".join(fields)}, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            values,
        )
        connection.commit()

    return get_goal_by_id_for_user(goal_id, user_id)


def create_routine_step(
    goal_id: int,
    title: str,
    scheduled_time: Optional[str],
    step_order: int,
) -> Dict[str, Any]:
    created_at = _utc_now()

    with closing(get_connection()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO routine_steps (goal_id, title, scheduled_time, step_order, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (goal_id, title, scheduled_time, step_order, created_at),
        )
        connection.commit()
        step_id = cursor.lastrowid

    return get_step_by_id(goal_id, step_id)


def list_steps_for_goal(goal_id: int) -> List[Dict[str, Any]]:
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM routine_steps
            WHERE goal_id = ?
            ORDER BY step_order ASC, id ASC
            """,
            (goal_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_step_by_id(goal_id: int, step_id: int) -> Optional[Dict[str, Any]]:
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM routine_steps
            WHERE goal_id = ? AND id = ?
            """,
            (goal_id, step_id),
        ).fetchone()
    return _row_to_dict(row)


def get_step_by_order(goal_id: int, step_order: int) -> Optional[Dict[str, Any]]:
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM routine_steps
            WHERE goal_id = ? AND step_order = ?
            """,
            (goal_id, step_order),
        ).fetchone()
    return _row_to_dict(row)


def update_routine_step(
    goal_id: int,
    step_id: int,
    updates: Dict[str, Any],
) -> Dict[str, Any]:
    if not updates:
        return get_step_by_id(goal_id, step_id)

    fields = [f"{field} = ?" for field in updates]
    values = list(updates.values())
    values.extend([goal_id, step_id])

    with closing(get_connection()) as connection:
        connection.execute(
            f"""
            UPDATE routine_steps
            SET {", ".join(fields)}
            WHERE goal_id = ? AND id = ?
            """,
            values,
        )
        connection.commit()

    return get_step_by_id(goal_id, step_id)


def get_checkin(goal_id: int, checkin_date: str) -> Optional[Dict[str, Any]]:
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM daily_checkins
            WHERE goal_id = ? AND checkin_date = ?
            """,
            (goal_id, checkin_date),
        ).fetchone()
    return _deserialize_checkin(row)


def list_checkins_for_goal(goal_id: int) -> List[Dict[str, Any]]:
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM daily_checkins
            WHERE goal_id = ?
            ORDER BY checkin_date DESC, id DESC
            """,
            (goal_id,),
        ).fetchall()
    return [_deserialize_checkin(row) for row in rows]


def upsert_checkin(
    goal_id: int,
    checkin_date: str,
    completed_step_ids: List[int],
    note: str,
    status: str,
    completion_percent: int,
) -> Dict[str, Any]:
    existing = get_checkin(goal_id, checkin_date)
    timestamp = _utc_now()
    serialized_step_ids = json.dumps(completed_step_ids)

    with closing(get_connection()) as connection:
        if existing:
            connection.execute(
                """
                UPDATE daily_checkins
                SET completed_step_ids = ?, note = ?, status = ?,
                    completion_percent = ?, updated_at = ?
                WHERE goal_id = ? AND checkin_date = ?
                """,
                (
                    serialized_step_ids,
                    note,
                    status,
                    completion_percent,
                    timestamp,
                    goal_id,
                    checkin_date,
                ),
            )
        else:
            connection.execute(
                """
                INSERT INTO daily_checkins (
                    goal_id, checkin_date, completed_step_ids, note, status,
                    completion_percent, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    goal_id,
                    checkin_date,
                    serialized_step_ids,
                    note,
                    status,
                    completion_percent,
                    timestamp,
                    timestamp,
                ),
            )
        connection.commit()

    return get_checkin(goal_id, checkin_date)
