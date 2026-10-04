"""SQLite persistence and tamper-evident hash-chained inference records."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .hashing import audit_record_hash

DEFAULT_DB = Path("trustcv_audit.sqlite3")
GENESIS_HASH = "0" * 64


def configured_db_path() -> Path:
    """Resolve the writable SQLite path, allowing hosts to provide a mount path.

    The default is relative to Streamlit's working directory (the repository
    root on Community Cloud). That local file is temporary on hosted platforms.
    """
    return Path(os.environ.get("TRUSTCV_DB_PATH", str(DEFAULT_DB)))


def connect(db_path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("""CREATE TABLE IF NOT EXISTS inference_audits (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp_utc TEXT NOT NULL,
        image_sha256 TEXT NOT NULL, model_sha256 TEXT NOT NULL, prediction TEXT NOT NULL,
        confidence REAL, mode TEXT NOT NULL, previous_hash TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")
    connection.commit()
    return connection


@contextmanager
def database(db_path: str | Path = DEFAULT_DB):
    """Commit/rollback and always close SQLite handles (important on Windows)."""
    connection = connect(db_path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in ("timestamp_utc", "image_sha256", "model_sha256", "prediction", "confidence", "mode")}


def add_audit(image_sha256: str, model_sha256: str, prediction: str, confidence: float | None,
              mode: str, db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    with database(db_path) as db:
        prior = db.execute("SELECT record_hash FROM inference_audits ORDER BY id DESC LIMIT 1").fetchone()
        previous = prior["record_hash"] if prior else GENESIS_HASH
        item = {"timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "image_sha256": image_sha256, "model_sha256": model_sha256,
                "prediction": prediction, "confidence": confidence, "mode": mode}
        record_hash = audit_record_hash(item, previous)
        db.execute("INSERT INTO inference_audits(timestamp_utc,image_sha256,model_sha256,prediction,confidence,mode,previous_hash,record_hash) VALUES(?,?,?,?,?,?,?,?)",
                   (*item.values(), previous, record_hash))
        return {**item, "previous_hash": previous, "record_hash": record_hash}


def list_audits(db_path: str | Path = DEFAULT_DB, limit: int = 500) -> list[dict[str, Any]]:
    with database(db_path) as db:
        rows = db.execute("SELECT * FROM inference_audits ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]


def verify_chain(db_path: str | Path = DEFAULT_DB) -> tuple[bool, str]:
    with database(db_path) as db:
        rows = db.execute("SELECT * FROM inference_audits ORDER BY id").fetchall()
    previous = GENESIS_HASH
    for index, raw in enumerate(rows, start=1):
        row = dict(raw)
        payload = _payload(row)
        expected = audit_record_hash(payload, previous)
        if row["previous_hash"] != previous:
            return False, f"Record {index} points to a different previous hash"
        if row["record_hash"] != expected:
            return False, f"Record {index} content or hash was changed"
        previous = row["record_hash"]
    return True, f"Verified {len(rows)} record(s)"


def get_reference_hash(db_path: str | Path = DEFAULT_DB) -> str | None:
    with database(db_path) as db:
        row = db.execute("SELECT value FROM settings WHERE key='trusted_model_sha256'").fetchone()
        return row["value"] if row else None


def set_reference_hash(value: str, db_path: str | Path = DEFAULT_DB) -> None:
    with database(db_path) as db:
        db.execute("INSERT INTO settings(key,value,updated_at) VALUES('trusted_model_sha256',?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                   (value, datetime.now(timezone.utc).isoformat(timespec="seconds")))
