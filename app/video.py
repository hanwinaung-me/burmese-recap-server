import sqlite3
import json
from app.config import DATABASE_PATH


def connect():
    db = sqlite3.connect(
        DATABASE_PATH,
        timeout=30
    )
    db.row_factory = sqlite3.Row
    return db


def initialize():
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                original_filename TEXT,
                video_path TEXT,
                video_size INTEGER DEFAULT 0,
                duration REAL DEFAULT 0,
                status TEXT DEFAULT 'CREATED',
                progress INTEGER DEFAULT 0,
                message TEXT DEFAULT '',
                error TEXT DEFAULT '',
                settings TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS job_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        """)


def create_project(project):
    with connect() as db:
        db.execute("""
            INSERT INTO projects (
                id, name, original_filename,
                video_path, video_size, duration,
                status, progress, message,
                settings, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project["id"],
            project["name"],
            project.get("original_filename"),
            project.get("video_path"),
            project.get("video_size", 0),
            project.get("duration", 0),
            project.get("status", "CREATED"),
            project.get("progress", 0),
            project.get("message", ""),
            json.dumps(project.get("settings", {})),
            project["created_at"],
            project["updated_at"]
        ))


def get_project(project_id):
    with connect() as db:
        row = db.execute(
            "SELECT * FROM projects WHERE id = ?",
            (project_id,)
        ).fetchone()

    if not row:
        return None

    result = dict(row)
    result["settings"] = json.loads(result["settings"])
    return result


def list_projects():
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM projects ORDER BY created_at DESC"
        ).fetchall()

    results = []

    for row in rows:
        item = dict(row)
        item["settings"] = json.loads(item["settings"])
        results.append(item)

    return results


def update_project(project_id, **fields):
    allowed = {
        "name", "video_path", "video_size",
        "duration", "status", "progress",
        "message", "error", "settings"
    }

    updates = {
        key: value
        for key, value in fields.items()
        if key in allowed
    }

    if not updates:
        return get_project(project_id)

    if "settings" in updates:
        updates["settings"] = json.dumps(updates["settings"])

    updates["updated_at"] = fields.get(
        "updated_at"
    )

    if not updates["updated_at"]:
        from datetime import datetime, timezone
        updates["updated_at"] = datetime.now(
            timezone.utc
        ).isoformat()

    query = ", ".join(
        f"{key} = ?" for key in updates
    )

    values = list(updates.values()) + [project_id]

    with connect() as db:
        db.execute(
            f"UPDATE projects SET {query} WHERE id = ?",
            values
        )

    return get_project(project_id)


def add_event(project_id, stage, message, created_at):
    with connect() as db:
        db.execute("""
            INSERT INTO job_events (
                project_id, stage, message, created_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            project_id,
            stage,
            message,
            created_at
        ))


def get_events(project_id):
    with connect() as db:
        rows = db.execute("""
            SELECT stage, message, created_at
            FROM job_events
            WHERE project_id = ?
            ORDER BY id ASC
        """, (project_id,)).fetchall()

    return [dict(row) for row in rows]
