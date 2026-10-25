"""SQLite database connection and schema initialization."""

import os
import sqlite3

DB_PATH = os.getenv("SPECGUARD_DB", "./specguard.db")


class Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def get_db_connection() -> sqlite3.Connection:
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH, timeout=10, factory=Connection)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=10000')
    return conn


def init_db():
    """Initialize the database schema if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("CREATE TABLE IF NOT EXISTS verification_snapshots (project_id TEXT PRIMARY KEY, data TEXT NOT NULL)")

    # Projects table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            specification TEXT NOT NULL,
            source_code TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Requirements table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requirements (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            text TEXT NOT NULL,
            category TEXT NOT NULL,
            measurable_criteria TEXT NOT NULL,
            ambiguous BOOLEAN DEFAULT 0,
            clarification_note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)

    # Generated tests table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS generated_tests (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            requirement_id TEXT NOT NULL,
            pytest_code TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (requirement_id) REFERENCES requirements(id)
        )
    """)

    # Test results table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            test_id TEXT NOT NULL,
            requirement_id TEXT NOT NULL,
            status TEXT NOT NULL,
            output TEXT,
            duration_ms INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (test_id) REFERENCES generated_tests(id),
            FOREIGN KEY (requirement_id) REFERENCES requirements(id)
        )
    """)

    # Static findings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS static_findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            requirement_id TEXT NOT NULL,
            line_number INTEGER,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (requirement_id) REFERENCES requirements(id)
        )
    """)

    # Fix suggestions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fix_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            requirement_id TEXT NOT NULL,
            explanation TEXT NOT NULL,
            patched_code TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (requirement_id) REFERENCES requirements(id)
        )
    """)

    # Expand-only migration: pre-account projects remain local and are never
    # silently assigned to a newly registered public account.
    if 'owner_id' not in {r[1] for r in conn.execute('PRAGMA table_info(projects)')}:
        conn.execute("ALTER TABLE projects ADD COLUMN owner_id TEXT NOT NULL DEFAULT 'local'")
    if 'name' not in {r[1] for r in conn.execute('PRAGMA table_info(projects)')}:
        conn.execute("ALTER TABLE projects ADD COLUMN name TEXT NOT NULL DEFAULT 'Untitled project'")
    conn.executescript('''
        CREATE INDEX IF NOT EXISTS projects_owner ON projects(owner_id, updated_at);
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
            created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (
            digest TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
        CREATE TABLE IF NOT EXISTS request_limits (
            key TEXT PRIMARY KEY, started INTEGER NOT NULL, count INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS execution_lease (
            id INTEGER PRIMARY KEY CHECK(id=1), token TEXT NOT NULL, expires_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            owner_id TEXT NOT NULL, source_sha256 TEXT NOT NULL,
            status TEXT NOT NULL, created_at INTEGER NOT NULL, report TEXT, error TEXT);
        CREATE INDEX IF NOT EXISTS runs_project ON runs(project_id, created_at);
        CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
        INSERT OR IGNORE INTO schema_version VALUES (1);
    ''')
    if 'recovery_hash' not in {r[1] for r in conn.execute('PRAGMA table_info(users)')}:
        conn.execute('ALTER TABLE users ADD COLUMN recovery_hash TEXT')
    conn.commit()
    conn.close()


class ProjectDB:
    """Database operations for projects."""

    @staticmethod
    def create_project(project_id: str, specification: str, source_code: str,
                       owner_id: str = 'local', name: str = 'Untitled project') -> dict:
        """Create a new project."""
        conn = get_db_connection()
        conn.execute('BEGIN IMMEDIATE')
        if owner_id != 'local' and conn.execute(
            'SELECT count(*) FROM projects WHERE owner_id=?', (owner_id,)
        ).fetchone()[0] >= 20:
            conn.close()
            from fastapi import HTTPException
            raise HTTPException(429, 'Project limit reached; delete an old project first')
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO projects (id, specification, source_code, owner_id, name)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, specification, source_code, owner_id, name),
        )
        conn.commit()
        conn.close()
        return {"id": project_id, "status": "created"}

    @staticmethod
    def get_project(project_id: str) -> dict | None:
        """Get a project by ID."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    @staticmethod
    def update_project(project_id: str, specification: str | None = None, source_code: str | None = None):
        """Update a project's specification or source code."""
        conn = get_db_connection()
        cursor = conn.cursor()
        updates = ["updated_at = CURRENT_TIMESTAMP"]
        params = []
        if specification:
            updates.append("specification = ?")
            params.append(specification)
        if source_code:
            updates.append("source_code = ?")
            params.append(source_code)
        params.append(project_id)
        cursor.execute(f"UPDATE projects SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        conn.close()


class RequirementDB:
    """Database operations for requirements."""

    @staticmethod
    def create_requirement(
        req_id: str,
        project_id: str,
        text: str,
        category: str,
        measurable_criteria: str,
        ambiguous: bool = False,
        clarification_note: str | None = None,
    ):
        """Create a new requirement."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO requirements (id, project_id, text, category, measurable_criteria, ambiguous, clarification_note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (req_id, project_id, text, category, measurable_criteria, ambiguous, clarification_note),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_requirements(project_id: str) -> list:
        """Get all requirements for a project."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM requirements WHERE project_id = ?", (project_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]


class GeneratedTestDB:
    """Database operations for generated tests."""

    @staticmethod
    def create_test(
        test_id: str,
        project_id: str,
        requirement_id: str,
        pytest_code: str,
        description: str,
    ):
        """Create a new generated test."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO generated_tests (id, project_id, requirement_id, pytest_code, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            (test_id, project_id, requirement_id, pytest_code, description),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_tests(project_id: str) -> list:
        """Get all generated tests for a project."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM generated_tests WHERE project_id = ?", (project_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]


class TestResultDB:
    """Database operations for test results."""

    @staticmethod
    def create_result(
        project_id: str,
        test_id: str,
        requirement_id: str,
        status: str,
        output: str,
        duration_ms: int,
    ):
        """Create a new test result."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO test_results (project_id, test_id, requirement_id, status, output, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (project_id, test_id, requirement_id, status, output, duration_ms),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_results(project_id: str) -> list:
        """Get all test results for a project."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM test_results
            WHERE project_id = ?
            ORDER BY created_at DESC
            """,
            (project_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]


class StaticFindingDB:
    """Database operations for static findings."""

    @staticmethod
    def create_finding(
        project_id: str,
        requirement_id: str,
        line_number: int,
        message: str,
    ):
        """Create a new static finding."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO static_findings (project_id, requirement_id, line_number, message)
            VALUES (?, ?, ?, ?)
            """,
            (project_id, requirement_id, line_number, message),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_findings(project_id: str) -> list:
        """Get all static findings for a project."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM static_findings WHERE project_id = ?",
            (project_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]


class FixSuggestionDB:
    """Database operations for fix suggestions."""

    @staticmethod
    def create_suggestion(
        project_id: str,
        requirement_id: str,
        explanation: str,
        patched_code: str,
    ):
        """Create a new fix suggestion."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO fix_suggestions (project_id, requirement_id, explanation, patched_code)
            VALUES (?, ?, ?, ?)
            """,
            (project_id, requirement_id, explanation, patched_code),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_suggestions(project_id: str) -> list:
        """Get all fix suggestions for a project."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM fix_suggestions WHERE project_id = ?",
            (project_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
