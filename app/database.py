import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


class RunRepository:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    range_start TEXT NOT NULL,
                    range_end TEXT NOT NULL,
                    hostname TEXT,
                    status TEXT NOT NULL,
                    event_count INTEGER NOT NULL DEFAULT 0,
                    active_seconds REAL NOT NULL DEFAULT 0,
                    categories_json TEXT NOT NULL DEFAULT '[]',
                    apps_json TEXT NOT NULL DEFAULT '[]',
                    error TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    model TEXT,
                    prompt_version TEXT,
                    browser_tracking INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            self._migrate_runs(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS segments (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    start TEXT NOT NULL,
                    end TEXT NOT NULL,
                    duration_seconds REAL NOT NULL,
                    app TEXT NOT NULL,
                    category_json TEXT NOT NULL,
                    domain TEXT,
                    session INTEGER NOT NULL DEFAULT 0,
                    context_policy TEXT NOT NULL DEFAULT 'title_omitted,url_domain_only'
                )
                """
            )
            segment_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(segments)").fetchall()
            }
            if "session" not in segment_columns:
                connection.execute(
                    "ALTER TABLE segments ADD COLUMN session INTEGER NOT NULL DEFAULT 0"
                )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                    label TEXT NOT NULL,
                    project_hint TEXT,
                    confidence REAL NOT NULL,
                    duration_seconds REAL NOT NULL,
                    start TEXT NOT NULL,
                    end TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    customer TEXT,
                    description TEXT NOT NULL DEFAULT '',
                    billing_code TEXT,
                    aliases_json TEXT NOT NULL DEFAULT '[]',
                    domains_json TEXT NOT NULL DEFAULT '[]',
                    keywords_json TEXT NOT NULL DEFAULT '[]',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS project_rules (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 1,
                    UNIQUE(project_id, kind, pattern)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS entries (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                    project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
                    position INTEGER NOT NULL,
                    start TEXT NOT NULL,
                    end TEXT NOT NULL,
                    raw_seconds REAL NOT NULL,
                    rounded_seconds INTEGER NOT NULL,
                    local_description TEXT NOT NULL,
                    final_summary TEXT,
                    assignment_confidence REAL NOT NULL DEFAULT 0,
                    assignment_source TEXT NOT NULL DEFAULT 'unassigned',
                    approved INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS entry_tasks (
                    entry_id TEXT NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
                    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    PRIMARY KEY(entry_id, task_id),
                    UNIQUE(task_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS task_segments (
                    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    segment_id TEXT NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
                    PRIMARY KEY (task_id, segment_id),
                    UNIQUE (segment_id)
                )
                """
            )

    @staticmethod
    def _migrate_runs(connection: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(runs)").fetchall()
        }
        migrations = {
            "model": "ALTER TABLE runs ADD COLUMN model TEXT",
            "prompt_version": "ALTER TABLE runs ADD COLUMN prompt_version TEXT",
            "browser_tracking": (
                "ALTER TABLE runs ADD COLUMN browser_tracking INTEGER NOT NULL DEFAULT 0"
            ),
        }
        for column, statement in migrations.items():
            if column not in columns:
                connection.execute(statement)

    def create(self, range_start: str, range_end: str, hostname: Optional[str]) -> Dict[str, Any]:
        run_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runs (id, range_start, range_end, hostname, status, created_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
                """,
                (run_id, range_start, range_end, hostname, created_at),
            )
        return self.get(run_id)  # type: ignore[return-value]

    def mark_running(self, run_id: str, status: str = "reading_activity") -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE runs SET status = ?, error = NULL WHERE id = ? AND status != 'cancelled'",
                (status, run_id),
            )

    def is_cancelled(self, run_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT status FROM runs WHERE id = ?", (run_id,)).fetchone()
            return bool(row and row["status"] == "cancelled")

    def cancel(self, run_id: str) -> bool:
        completed_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE runs SET status = 'cancelled', error = NULL, completed_at = ? "
                "WHERE id = ? AND status NOT IN ('cancelled', 'failed')",
                (completed_at, run_id),
            )
            return cursor.rowcount > 0

    def set_status(self, run_id: str, status: str) -> None:
        self.mark_running(run_id, status)

    def set_hostname(self, run_id: str, hostname: str) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE runs SET hostname = ? WHERE id = ?", (hostname, run_id))

    def complete(self, run_id: str, result: Dict[str, Any]) -> None:
        self.complete_phase2(run_id, result, [], [], None, None)

    def complete_phase2(
        self,
        run_id: str,
        result: Dict[str, Any],
        segments: List[Dict[str, Any]],
        tasks: List[Dict[str, Any]],
        model: Optional[str],
        prompt_version: Optional[str],
    ) -> None:
        completed_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE runs
                SET status = 'completed', event_count = ?, active_seconds = ?,
                    categories_json = ?, apps_json = ?, completed_at = ?, error = NULL,
                    model = ?, prompt_version = ?, browser_tracking = ?
                WHERE id = ? AND status != 'cancelled'
                """,
                (
                    result["event_count"], result["active_seconds"],
                    json.dumps(result["categories"]), json.dumps(result["apps"]),
                    completed_at, model, prompt_version,
                    1 if result.get("browser_tracking") else 0, run_id,
                ),
            )
            if connection.execute("SELECT changes()").fetchone()[0] == 0:
                return
            for position, segment in enumerate(segments):
                connection.execute(
                    """
                    INSERT INTO segments
                    (id, run_id, position, start, end, duration_seconds, app,
                     category_json, domain, session, context_policy)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'title_omitted,url_domain_only')
                    """,
                    (
                        segment["id"], run_id, position, segment["start"], segment["end"],
                        segment["duration_seconds"], segment["app"],
                        json.dumps(segment["category"]), segment.get("domain"),
                        segment.get("session", 0),
                    ),
                )
            for task in tasks:
                self._insert_task(connection, run_id, task)

    @staticmethod
    def _insert_task(
        connection: sqlite3.Connection, run_id: str, task: Dict[str, Any]
    ) -> None:
        connection.execute(
            """
            INSERT INTO tasks
            (id, run_id, label, project_hint, confidence, duration_seconds, start, end, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task["id"], run_id, task["label"], task.get("project_hint"),
                task["confidence"], task["duration_seconds"], task["start"],
                task["end"], task["status"],
            ),
        )
        connection.executemany(
            "INSERT INTO task_segments (task_id, segment_id) VALUES (?, ?)",
            [(task["id"], segment_id) for segment_id in task["segment_ids"]],
        )

    def fail(self, run_id: str, error: str) -> None:
        completed_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                "UPDATE runs SET status = 'failed', error = ?, completed_at = ? WHERE id = ? AND status != 'cancelled'",
                (error[:2000], completed_at, run_id),
            )

    def get(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if not row:
                return None
            value = self._deserialize(row)
            value["segments"] = self._segments(connection, run_id)
            value["tasks"] = self._tasks(connection, run_id)
            value["work_sessions"] = self._work_sessions(
                value["segments"], value["tasks"]
            )
            value["entries"] = self._entries(connection, run_id)
            return value

    def list(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._deserialize(row) for row in rows]

    @staticmethod
    def _segments(connection: sqlite3.Connection, run_id: str) -> List[Dict[str, Any]]:
        rows = connection.execute(
            "SELECT * FROM segments WHERE run_id = ? ORDER BY position", (run_id,)
        ).fetchall()
        values = []
        for row in rows:
            item = dict(row)
            item["category"] = json.loads(item.pop("category_json"))
            values.append(item)
        return values

    @staticmethod
    def _tasks(connection: sqlite3.Connection, run_id: str) -> List[Dict[str, Any]]:
        rows = connection.execute(
            "SELECT * FROM tasks WHERE run_id = ? ORDER BY start", (run_id,)
        ).fetchall()
        values = []
        for row in rows:
            item = dict(row)
            links = connection.execute(
                """
                SELECT ts.segment_id FROM task_segments ts
                JOIN segments s ON s.id = ts.segment_id
                WHERE ts.task_id = ? ORDER BY s.position
                """,
                (item["id"],),
            ).fetchall()
            item["segment_ids"] = [link["segment_id"] for link in links]
            values.append(item)
        return values

    @staticmethod
    def _work_sessions(
        segments: List[Dict[str, Any]], tasks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        sessions: Dict[int, List[Dict[str, Any]]] = {}
        for segment in segments:
            sessions.setdefault(int(segment.get("session", 0)), []).append(segment)
        output = []
        for session_id, items in sorted(sessions.items()):
            items.sort(key=lambda item: item["start"])
            start = items[0]["start"]
            end = items[-1]["end"]
            # Ignore an isolated login/window check before sustained work. A work
            # boundary begins/ends where at least three minutes of active time
            # occurs within a ten-minute neighborhood.
            for candidate in items:
                window_end = datetime.fromisoformat(candidate["start"]).timestamp() + 600
                active = sum(
                    item["duration_seconds"]
                    for item in items
                    if datetime.fromisoformat(item["start"]).timestamp() < window_end
                    and item["start"] >= candidate["start"]
                )
                if active >= 180:
                    start = candidate["start"]
                    break
            for candidate in reversed(items):
                window_start = datetime.fromisoformat(candidate["end"]).timestamp() - 600
                active = sum(
                    item["duration_seconds"]
                    for item in items
                    if datetime.fromisoformat(item["end"]).timestamp() > window_start
                    and item["end"] <= candidate["end"]
                )
                if active >= 180:
                    end = candidate["end"]
                    break
            included = [
                item for item in items if item["start"] >= start and item["end"] <= end
            ] or items
            segment_ids = {item["id"] for item in included}
            session_tasks = sorted(
                [
                    task
                    for task in tasks
                    if any(segment_id in segment_ids for segment_id in task["segment_ids"])
                ],
                key=lambda task: task["start"],
            )
            switches = []
            previous_project = None
            for task in session_tasks:
                project = (task.get("project_hint") or "").strip()
                if project and project.casefold() != (previous_project or "").casefold():
                    switches.append({"start": task["start"], "project": project})
                    previous_project = project
            output.append(
                {
                    "session": session_id,
                    "start": start,
                    "end": end,
                    "active_seconds": round(
                        sum(item["duration_seconds"] for item in included), 3
                    ),
                    "task_count": len(session_tasks),
                    "project_switches": switches,
                }
            )
        return output

    @staticmethod
    def _entries(connection: sqlite3.Connection, run_id: str) -> List[Dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT e.*, p.name project_name, p.customer, p.billing_code
            FROM entries e LEFT JOIN projects p ON p.id = e.project_id
            WHERE e.run_id = ? ORDER BY e.position
            """,
            (run_id,),
        ).fetchall()
        values = []
        for row in rows:
            item = dict(row)
            links = connection.execute(
                "SELECT task_id FROM entry_tasks WHERE entry_id = ?", (item["id"],)
            ).fetchall()
            item["task_ids"] = [link["task_id"] for link in links]
            item["approved"] = bool(item["approved"])
            values.append(item)
        return values

    def list_projects(self, active_only: bool = False) -> List[Dict[str, Any]]:
        query = "SELECT * FROM projects"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY name COLLATE NOCASE"
        with self._connect() as connection:
            rows = connection.execute(query).fetchall()
        return [self._deserialize_project(row) for row in rows]

    def create_project(self, project: Dict[str, Any]) -> Dict[str, Any]:
        project_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO projects
                (id, name, customer, description, billing_code, aliases_json,
                 domains_json, keywords_json, active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id, project["name"].strip(), project.get("customer"),
                    project.get("description", ""), project.get("billing_code"),
                    json.dumps(project.get("aliases", [])),
                    json.dumps(project.get("domains", [])),
                    json.dumps(project.get("keywords", [])),
                    1 if project.get("active", True) else 0,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return self._deserialize_project(row)

    def update_project(self, project_id: str, project: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            if not connection.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone():
                return None
            connection.execute(
                """
                UPDATE projects SET name=?, customer=?, description=?, billing_code=?,
                    aliases_json=?, domains_json=?, keywords_json=?, active=? WHERE id=?
                """,
                (
                    project["name"].strip(), project.get("customer"),
                    project.get("description", ""), project.get("billing_code"),
                    json.dumps(project.get("aliases", [])), json.dumps(project.get("domains", [])),
                    json.dumps(project.get("keywords", [])), 1 if project.get("active", True) else 0,
                    project_id,
                ),
            )
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return self._deserialize_project(row)

    def delete_project(self, project_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _deserialize_project(row: sqlite3.Row) -> Dict[str, Any]:
        value = dict(row)
        value["aliases"] = json.loads(value.pop("aliases_json"))
        value["domains"] = json.loads(value.pop("domains_json"))
        value["keywords"] = json.loads(value.pop("keywords_json"))
        value["active"] = bool(value["active"])
        return value

    def replace_entries(self, run_id: str, entries: List[Dict[str, Any]]) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM entries WHERE run_id = ?", (run_id,))
            for position, entry in enumerate(entries):
                connection.execute(
                    """
                    INSERT INTO entries
                    (id, run_id, project_id, position, start, end, raw_seconds,
                     rounded_seconds, local_description, final_summary,
                     assignment_confidence, assignment_source, approved)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry["id"], run_id, entry.get("project_id"), position,
                        entry["start"], entry["end"], entry["raw_seconds"],
                        entry["rounded_seconds"], entry["local_description"],
                        entry.get("final_summary"), entry.get("assignment_confidence", 0),
                        entry.get("assignment_source", "unassigned"),
                        1 if entry.get("approved") else 0,
                    ),
                )
                connection.executemany(
                    "INSERT INTO entry_tasks (entry_id, task_id) VALUES (?, ?)",
                    [(entry["id"], task_id) for task_id in entry["task_ids"]],
                )

    def update_entry(self, entry_id: str, changes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        allowed = {"project_id", "rounded_seconds", "final_summary", "approved"}
        fields = [field for field in changes if field in allowed]
        if not fields:
            return None
        with self._connect() as connection:
            row = connection.execute("SELECT run_id FROM entries WHERE id = ?", (entry_id,)).fetchone()
            if not row:
                return None
            if "project_id" in fields and changes["project_id"]:
                if not connection.execute(
                    "SELECT 1 FROM projects WHERE id = ?", (changes["project_id"],)
                ).fetchone():
                    raise ValueError("Project not found.")
                changes["assignment_source"] = "manual"
                changes["assignment_confidence"] = 1.0
                fields.extend(["assignment_source", "assignment_confidence"])
            values = [changes[field] for field in fields]
            if "approved" in fields:
                values[fields.index("approved")] = 1 if changes["approved"] else 0
            connection.execute(
                "UPDATE entries SET %s WHERE id = ?" % ", ".join(field + " = ?" for field in fields),
                values + [entry_id],
            )
            return next(item for item in self._entries(connection, row["run_id"]) if item["id"] == entry_id)

    def update_task(
        self, task_id: str, label: str, project_hint: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute("SELECT run_id FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not row:
                return None
            connection.execute(
                """
                UPDATE tasks SET label = ?, project_hint = ?, status = 'edited'
                WHERE id = ?
                """,
                (label, project_hint, task_id),
            )
            return next(item for item in self._tasks(connection, row["run_id"]) if item["id"] == task_id)

    def merge_tasks(self, task_ids: List[str], label: Optional[str] = None) -> Dict[str, Any]:
        if len(set(task_ids)) < 2:
            raise ValueError("Select at least two different tasks.")
        with self._connect() as connection:
            placeholders = ",".join("?" for _ in task_ids)
            rows = connection.execute(
                "SELECT * FROM tasks WHERE id IN (%s)" % placeholders, task_ids
            ).fetchall()
            if len(rows) != len(set(task_ids)) or len({row["run_id"] for row in rows}) != 1:
                raise ValueError("Tasks must exist and belong to the same run.")
            run_id = rows[0]["run_id"]
            links = connection.execute(
                "SELECT segment_id FROM task_segments WHERE task_id IN (%s)" % placeholders,
                task_ids,
            ).fetchall()
            segment_ids = [row["segment_id"] for row in links]
            segments = self._segment_rows(connection, segment_ids)
            task = {
                "id": str(uuid4()),
                "label": (label or rows[0]["label"]).strip(),
                "project_hint": rows[0]["project_hint"],
                "confidence": min(row["confidence"] for row in rows),
                "duration_seconds": round(sum(row["duration_seconds"] for row in segments), 3),
                "start": min(row["start"] for row in segments),
                "end": max(row["end"] for row in segments),
                "status": "edited",
                "segment_ids": [row["id"] for row in segments],
            }
            connection.execute("DELETE FROM tasks WHERE id IN (%s)" % placeholders, task_ids)
            self._insert_task(connection, run_id, task)
            return task

    def split_task(self, task_id: str, groups: List[List[str]]) -> List[Dict[str, Any]]:
        if len(groups) < 2 or any(not group for group in groups):
            raise ValueError("Provide at least two non-empty segment groups.")
        flat = [segment_id for group in groups for segment_id in group]
        if len(flat) != len(set(flat)):
            raise ValueError("A segment cannot appear in more than one split group.")
        with self._connect() as connection:
            original = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not original:
                raise ValueError("Task not found.")
            existing = {
                row["segment_id"]
                for row in connection.execute(
                    "SELECT segment_id FROM task_segments WHERE task_id = ?", (task_id,)
                ).fetchall()
            }
            if set(flat) != existing:
                raise ValueError("Split groups must contain every task segment exactly once.")
            connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            created = []
            for index, group in enumerate(groups, 1):
                segments = self._segment_rows(connection, group)
                task = {
                    "id": str(uuid4()),
                    "label": "%s (part %s)" % (original["label"], index),
                    "project_hint": original["project_hint"],
                    "confidence": original["confidence"],
                    "duration_seconds": round(sum(row["duration_seconds"] for row in segments), 3),
                    "start": min(row["start"] for row in segments),
                    "end": max(row["end"] for row in segments),
                    "status": "edited",
                    "segment_ids": [row["id"] for row in segments],
                }
                self._insert_task(connection, original["run_id"], task)
                created.append(task)
            return created

    @staticmethod
    def _segment_rows(
        connection: sqlite3.Connection, segment_ids: List[str]
    ) -> List[sqlite3.Row]:
        placeholders = ",".join("?" for _ in segment_ids)
        return connection.execute(
            "SELECT * FROM segments WHERE id IN (%s) ORDER BY position" % placeholders,
            segment_ids,
        ).fetchall()

    @staticmethod
    def _deserialize(row: sqlite3.Row) -> Dict[str, Any]:
        value = dict(row)
        value["categories"] = json.loads(value.pop("categories_json"))
        value["apps"] = json.loads(value.pop("apps_json"))
        value["browser_tracking"] = bool(value.get("browser_tracking"))
        return value
