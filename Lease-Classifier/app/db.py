"""
Lightweight audit log.

Every classification is persisted so the tool has a defensible record of what it
decided and on what inputs — important for a governance-sensitive product. Uses
the Python standard-library sqlite3 (no external dependency); swap DB_PATH for a
Postgres DSN + driver when you outgrow SQLite.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.getenv("EFG_DB_PATH", Path(__file__).resolve().parent.parent / "efg_audit.db"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS classifications (
    id             TEXT PRIMARY KEY,
    created_at     TEXT NOT NULL,
    document       TEXT,
    gaap_verdict   TEXT,
    tax_verdict    TEXT,
    ucc_verdict    TEXT,
    alignment      TEXT,
    report_json    TEXT NOT NULL
);
"""


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as conn:
        conn.executescript(_SCHEMA)


def record_classification(report_dict: dict) -> str:
    record_id = str(uuid.uuid4())
    summary = {r["regime"]: r["verdict"] for r in report_dict.get("executive_summary", [])}
    with _conn() as conn:
        conn.execute(
            "INSERT INTO classifications "
            "(id, created_at, document, gaap_verdict, tax_verdict, ucc_verdict, alignment, report_json) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                record_id,
                datetime.now(timezone.utc).isoformat(),
                report_dict.get("document"),
                summary.get("GAAP (ASC 842)"),
                summary.get("Tax (IRC)"),
                summary.get("UCC (§1-203)"),
                report_dict.get("cross_regime_alignment"),
                json.dumps(report_dict),
            ),
        )
    return record_id


def get_classification(record_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT report_json FROM classifications WHERE id = ?", (record_id,)
        ).fetchone()
    return json.loads(row["report_json"]) if row else None


def list_classifications(limit: int = 50) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, created_at, document, gaap_verdict, tax_verdict, ucc_verdict, alignment "
            "FROM classifications ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
