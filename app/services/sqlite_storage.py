"""Persistent SQLite storage engine for LedgerGuard.

Replaces volatile in-memory global state with a durable, atomic, thread-safe
SQLite database. Stores invoice states, append-only cryptographic audit chain blocks,
voice session memory turns, and vendor policy overrides.

Enforces Write-Ahead Logging (WAL) for high concurrency and resilience across
application restarts.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

logger = logging.getLogger("ledgerguard.services.sqlite")

DB_DIR = Path("data")
DB_FILE = DB_DIR / "ledgerguard.db"


def _json_default(obj: Any) -> Any:
    """Safe serializer for Decimal and datetime objects."""
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return str(obj)


class SQLiteLedgerStore:
    """Thread-safe persistent storage manager for LedgerGuard."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DB_FILE
        self._lock = threading.Lock()
        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a connection configured with WAL and proper timeout."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=20.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _initialize_database(self) -> None:
        """Create schemas for invoices, audit blocks, session turns, and vendor policies."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Invoices table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                    invoice_id TEXT PRIMARY KEY,
                    invoice_number TEXT NOT NULL,
                    vendor_id TEXT NOT NULL,
                    vendor_name TEXT NOT NULL,
                    total TEXT NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'USD',
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_vendor ON invoices(vendor_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);")

            # 2. Cryptographic Audit Chain table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_blocks (
                    block_index INTEGER PRIMARY KEY,
                    event_id TEXT UNIQUE,
                    prev_hash TEXT NOT NULL,
                    tx_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL DEFAULT 'SYSTEM',
                    reason TEXT,
                    timestamp TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    argon2_seal TEXT NOT NULL,
                    metadata_json TEXT
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_tx_id ON audit_blocks(tx_id);")

            # 3. Session memory turns
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_turns (
                    turn_index INTEGER PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    intent TEXT,
                    timestamp TEXT NOT NULL
                );
            """)

            # 4. Vendor Policies table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vendor_policies (
                    vendor_id TEXT PRIMARY KEY,
                    policy_status TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.commit()
            logger.info("SQLite database initialized at %s with WAL enabled", self.db_path)

    # -------------------------------------------------------------------------
    # Invoices Persistence
    # -------------------------------------------------------------------------
    def save_invoice(self, inv_dict: dict[str, Any]) -> None:
        """Upsert an invoice record atomically."""
        inv_id = inv_dict["invoice_id"]
        inv_num = inv_dict.get("invoice_number", inv_id)
        v_id = inv_dict.get("vendor_id", "unknown")
        v_name = inv_dict.get("vendor_name", "Unknown Vendor")
        total = str(inv_dict.get("total", "0.00"))
        currency = inv_dict.get("currency", "USD")
        status = inv_dict.get("status", "PENDING_AUDIT")
        now_ts = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(inv_dict, default=_json_default)

        with self._lock, self._get_connection() as conn:
            conn.execute("""
                INSERT INTO invoices (invoice_id, invoice_number, vendor_id, vendor_name, total, currency, status, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(invoice_id) DO UPDATE SET
                    status=excluded.status,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at;
            """, (inv_id, inv_num, v_id, v_name, total, currency, status, payload_json, now_ts))
            conn.commit()

    def get_invoice(self, invoice_id: str) -> dict[str, Any] | None:
        """Retrieve a specific invoice by ID."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute("SELECT payload_json FROM invoices WHERE invoice_id = ?", (invoice_id,))
            row = cursor.fetchone()
            if row:
                return json.loads(row["payload_json"])
            return None

    def get_all_invoices(self) -> dict[str, dict[str, Any]]:
        """Retrieve all persisted invoices mapped by invoice_id."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute("SELECT invoice_id, payload_json FROM invoices ORDER BY invoice_id ASC")
            result = {}
            for row in cursor.fetchall():
                result[row["invoice_id"]] = json.loads(row["payload_json"])
            return result

    def update_invoice_status(self, invoice_id: str, new_status: str) -> None:
        """Update status in invoice payload and index column."""
        inv = self.get_invoice(invoice_id)
        if inv is not None:
            inv["status"] = new_status
            self.save_invoice(inv)

    # -------------------------------------------------------------------------
    # Audit Chain Persistence
    # -------------------------------------------------------------------------
    def save_audit_block(self, block: dict[str, Any]) -> None:
        """Append an immutable block to the audit chain."""
        b_idx = int(block["block_index"])
        event_id = block.get("event_id", f"EVT-{b_idx:06d}")
        prev_hash = block["prev_hash"]
        tx_id = block["tx_id"]
        action = block["action"]
        actor = block.get("actor", "SYSTEM")
        reason = block.get("reason", "")
        ts = block["timestamp"]
        sha256 = block["sha256"]
        argon2_seal = block["argon2_seal"]
        meta_json = json.dumps(block.get("metadata", {}), default=_json_default)

        with self._lock, self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO audit_blocks (block_index, event_id, prev_hash, tx_id, action, actor, reason, timestamp, sha256, argon2_seal, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (b_idx, event_id, prev_hash, tx_id, action, actor, reason, ts, sha256, argon2_seal, meta_json))
            conn.commit()

    def get_audit_chain(self) -> list[dict[str, Any]]:
        """Retrieve complete chronological audit chain."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM audit_blocks ORDER BY block_index ASC")
            chain = []
            for row in cursor.fetchall():
                meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
                chain.append({
                    "block_index": row["block_index"],
                    "event_id": row["event_id"],
                    "prev_hash": row["prev_hash"],
                    "tx_id": row["tx_id"],
                    "action": row["action"],
                    "actor": row["actor"],
                    "reason": row["reason"],
                    "timestamp": row["timestamp"],
                    "sha256": row["sha256"],
                    "argon2_seal": row["argon2_seal"],
                    "metadata": meta,
                })
            return chain

    # -------------------------------------------------------------------------
    # Session Memory Persistence
    # -------------------------------------------------------------------------
    def save_session_turn(self, turn: dict[str, Any]) -> None:
        """Persist a conversation turn."""
        t_idx = int(turn["turn_index"])
        s_id = turn.get("session_id", "default")
        role = turn["role"]
        text = turn["text"]
        intent = turn.get("intent")
        ts = turn["timestamp"]

        with self._lock, self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO session_turns (turn_index, session_id, role, text, intent, timestamp)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (t_idx, s_id, role, text, intent, ts))
            conn.commit()

    def get_session_memory(self, session_id: str | None = None) -> list[dict[str, Any]]:
        """Retrieve chronological conversational memory turns."""
        with self._lock, self._get_connection() as conn:
            if session_id:
                cursor = conn.execute(
                    "SELECT * FROM session_turns WHERE session_id = ? ORDER BY turn_index ASC",
                    (session_id,),
                )
            else:
                cursor = conn.execute("SELECT * FROM session_turns ORDER BY turn_index ASC")
            return [dict(row) for row in cursor.fetchall()]

    # -------------------------------------------------------------------------
    # Vendor Policies Persistence
    # -------------------------------------------------------------------------
    def save_vendor_policy(self, vendor_id: str, policy_status: str) -> None:
        """Persist vendor policy override."""
        now_ts = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_connection() as conn:
            conn.execute("""
                INSERT INTO vendor_policies (vendor_id, policy_status, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(vendor_id) DO UPDATE SET policy_status=excluded.policy_status, updated_at=excluded.updated_at;
            """, (vendor_id, policy_status, now_ts))
            conn.commit()

    def get_vendor_policies(self) -> dict[str, str]:
        """Retrieve all vendor policy statuses."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute("SELECT vendor_id, policy_status FROM vendor_policies")
            return {row["vendor_id"]: row["policy_status"] for row in cursor.fetchall()}

    def reset_database(self) -> None:
        """Clear all tables while preserving schema."""
        with self._lock, self._get_connection() as conn:
            conn.execute("DELETE FROM invoices;")
            conn.execute("DELETE FROM audit_blocks;")
            conn.execute("DELETE FROM session_turns;")
            conn.execute("DELETE FROM vendor_policies;")
            conn.commit()
            logger.info("LedgerGuard SQLite database reset successfully.")


_store_instance: SQLiteLedgerStore | None = None


def get_sqlite_store() -> SQLiteLedgerStore:
    """Get or initialize singleton SQLiteLedgerStore."""
    global _store_instance
    if _store_instance is None:
        _store_instance = SQLiteLedgerStore()
    return _store_instance
