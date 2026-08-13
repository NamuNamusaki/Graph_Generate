"""
MySQL connection layer for the USERS / PROJECTS / JOBS tables in schema.sql.

Mirrors config.py's pattern of reading connection details from environment
variables (so nothing is hardcoded), and exposes small, explicit CRUD
functions rather than an ORM -- matching the rest of this codebase's style.

This module IS wired into web_api/app.py: submit_analysis() calls
create_project()/create_job(), get_status() calls get_job_by_uuid()/
update_job_progress(), and get_job_result()/download_sequence_file() both
call get_job_by_uuid(). Job state (status, step_current, output_result_path,
etc.) lives in MySQL now, not an in-memory dict -- it survives an `api`
container restart. The one thing intentionally NOT persisted here is
email-notification bookkeeping (which address was subscribed, whether the
completion email fired yet); app.py keeps that in a small in-memory dict
instead, since schema.sql's JOBS table has no columns for it.

Setup:
    pip install mysql-connector-python
    mysql -u root -p < schema.sql          # creates the `smartbiopep` DB + tables
    export DB_HOST=localhost DB_USER=root DB_PASSWORD=... DB_NAME=smartbiopep

    # or, to just apply schema.sql from Python instead of the mysql CLI:
    python3 db.py --init-schema
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any, Optional

import mysql.connector
from mysql.connector import pooling

# -----------------------------------------------------------------------------------------
# CONNECTION CONFIG -- same env-var-with-default pattern as config.py
# -----------------------------------------------------------------------------------------
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "smartbiopep")

# A connection pool, not a single global connection: FastAPI serves requests
# concurrently, and a lone mysql.connector connection isn't safe to share
# across threads/requests. Pool is created lazily (on first use) rather than
# at import time, so importing this module never fails just because a DB
# isn't reachable yet (e.g. while running pages that don't touch the DB).
_pool: Optional[pooling.MySQLConnectionPool] = None


def _get_pool() -> pooling.MySQLConnectionPool:
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="smartbiopep_pool",
            pool_size=5,
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            autocommit=False,
        )
    return _pool


@contextmanager
def get_cursor(commit: bool = False):
    """
    Yields a dict-returning cursor from a pooled connection, and always
    closes both the cursor and the connection (back to the pool) afterward.
    Pass commit=True for INSERT/UPDATE/DELETE; left False (default) for
    read-only SELECTs so nothing is ever committed by accident.

    Usage:
        with get_cursor(commit=True) as cur:
            cur.execute("INSERT INTO users (...) VALUES (...)", (...))
            new_id = cur.lastrowid
    """
    conn = _get_pool().get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()  # returns the connection to the pool, doesn't actually close it


# -----------------------------------------------------------------------------------------
# USERS
# -----------------------------------------------------------------------------------------
def create_user(username: str, email: str, password_hash: str) -> int:
    """Inserts a new user and returns the new row's id."""
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, password_hash),
        )
        return cur.lastrowid


def get_user_by_username(username: str) -> Optional[dict]:
    """Looks up a user by username (e.g. for login) -- None if not found."""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        return cur.fetchone()


def get_user(user_id: int) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return cur.fetchone()


# -----------------------------------------------------------------------------------------
# PROJECTS
# -----------------------------------------------------------------------------------------
def create_project(user_id: int, project_name: str, description: str = None) -> int:
    """Inserts a new project owned by user_id and returns the new row's id."""
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO projects (user_id, project_name, description) VALUES (%s, %s, %s)",
            (user_id, project_name, description),
        )
        return cur.lastrowid


def get_project(project_id: int) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
        return cur.fetchone()


def list_projects_for_user(user_id: int) -> list[dict]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM projects WHERE user_id = %s ORDER BY created_at DESC",
            (user_id,),
        )
        return cur.fetchall()


# -----------------------------------------------------------------------------------------
# JOBS
# -----------------------------------------------------------------------------------------
def create_job(
    job_uuid: str,
    project_id: int,
    input_fasta_path: str = None,
    list_bioactivity_id: list[int] = None,
    list_step_total: list[str] = None,
) -> int:
    """
    Registers a new job for a project. Called by submit_analysis() in
    web_api/app.py -- job_uuid is a UNIQUE column here, so a duplicate
    job_uuid raises mysql.connector.IntegrityError instead of silently
    overwriting a previous row (a plain dict keyed by job_uuid, the
    in-memory approach this replaced, couldn't make that distinction).
    """
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO jobs
                (job_uuid, project_id, status, input_fasta_path,
                 list_bioactivity_id, list_step_total, step_current)
            VALUES (%s, %s, 'PENDING', %s, %s, %s, 0)
            """,
            (
                job_uuid,
                project_id,
                input_fasta_path,
                json.dumps(list_bioactivity_id) if list_bioactivity_id is not None else None,
                json.dumps(list_step_total) if list_step_total is not None else None,
            ),
        )
        return cur.lastrowid


def _decode_job_row(row: Optional[dict]) -> Optional[dict]:
    """JSON columns come back from mysql-connector as strings -- decode them
    into Python lists so callers get the same shape they'd build in Python."""
    if row is None:
        return None
    for key in ("list_bioactivity_id", "list_step_total"):
        if row.get(key):
            row[key] = json.loads(row[key])
    return row


def get_job_by_uuid(job_uuid: str) -> Optional[dict]:
    """The lookup every API endpoint in web_api/app.py needs -- get_status(),
    get_job_result(), and download_sequence_file() all call this first."""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM jobs WHERE job_uuid = %s", (job_uuid,))
        return _decode_job_row(cur.fetchone())


def list_jobs_for_project(project_id: int) -> list[dict]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM jobs WHERE project_id = %s ORDER BY submitted_at DESC",
            (project_id,),
        )
        return [_decode_job_row(r) for r in cur.fetchall()]


def update_job_progress(
    job_uuid: str,
    *,
    status: str = None,
    step_current: int = None,
    list_step_total: list[str] = None,
    output_result_path: str = None,
    error_message: str = None,
    started_at_now: bool = False,
    completed_at_now: bool = False,
    updated_by_worker: str = None,
    worker_name: str = None,
) -> None:
    """
    Updates only the fields actually passed in -- called from web_api/app.py's
    submit_analysis() and get_status() in place of the handful of
    `job["..."] = ...` lines the old in-memory-dict version used, collapsed
    into one call. Pass started_at_now=True /
    completed_at_now=True to stamp those columns with the current server
    time (matches TIMESTAMP semantics better than sending a Python-side
    timestamp across timezones).

    Example (mirrors what get_status() does when a job finishes):
        update_job_progress(
            job_uuid, status="SUCCESS", step_current=4,
            output_result_path="/data/results/JOB000001",
            completed_at_now=True,
        )
    """
    sets: list[str] = []
    params: list[Any] = []

    if status is not None:
        sets.append("status = %s")
        params.append(status)
    if step_current is not None:
        sets.append("step_current = %s")
        params.append(step_current)
    if list_step_total is not None:
        sets.append("list_step_total = %s")
        params.append(json.dumps(list_step_total))
    if output_result_path is not None:
        sets.append("output_result_path = %s")
        params.append(output_result_path)
    if error_message is not None:
        sets.append("error_message = %s")
        params.append(error_message)
    if updated_by_worker is not None:
        sets.append("updated_by_worker = %s")
        params.append(updated_by_worker)
    if worker_name is not None:
        sets.append("worker_name = %s")
        params.append(worker_name)
    if started_at_now:
        sets.append("started_at = CURRENT_TIMESTAMP")
    if completed_at_now:
        sets.append("completed_at = CURRENT_TIMESTAMP")

    if not sets:
        return  # nothing to update -- avoid emitting `UPDATE ... SET` with no columns

    params.append(job_uuid)
    with get_cursor(commit=True) as cur:
        cur.execute(
            f"UPDATE jobs SET {', '.join(sets)} WHERE job_uuid = %s",
            params,
        )


# -----------------------------------------------------------------------------------------
# ONE-OFF SETUP HELPER
# -----------------------------------------------------------------------------------------
def init_schema() -> None:
    """Applies schema.sql against the configured MySQL server. Equivalent to
    running `mysql -u ... -p ... < schema.sql` from the shell, provided here
    for convenience (`python3 db.py --init-schema`)."""
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    # schema.sql creates the database itself (CREATE DATABASE IF NOT EXISTS),
    # so this connects without specifying `database=` up front.
    conn = mysql.connector.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD)
    try:
        cur = conn.cursor()
        for statement in filter(None, (s.strip() for s in schema_sql.split(";"))):
            cur.execute(statement)
        conn.commit()
        cur.close()
    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    if "--init-schema" in sys.argv:
        init_schema()
        print(f"Schema applied to {DB_HOST}:{DB_PORT}/{DB_NAME}")
    else:
        print(__doc__)
