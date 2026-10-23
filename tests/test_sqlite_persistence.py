"""Tests for Phase 6: Durable SQLite storage in WAL mode and state recovery across restarts."""

import pytest
from app.services.sqlite_storage import SQLiteLedgerStore
from connectors.argon_connector import get_argon_connector


def test_sqlite_schema_initialization(tmp_path):
    """SQLite database must initialize tables and enable WAL mode."""
    db_file = tmp_path / "ledger_test.db"
    store = SQLiteLedgerStore(db_path=str(db_file))

    with store._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        journal_mode = cursor.fetchone()[0]
        assert journal_mode.lower() == "wal"

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        assert "invoices" in tables
        assert "audit_blocks" in tables
        assert "session_turns" in tables
        assert "vendor_policies" in tables


def test_invoices_persist_across_reconnection(tmp_path):
    """Invoices saved in store 1 must be accurately rehydrated by new store 2 instance."""
    db_file = tmp_path / "ledger_persist.db"
    store1 = SQLiteLedgerStore(db_path=str(db_file))

    sample_invoice = {
        "invoice_id": "INV-TEST-001",
        "invoice_number": "INV-TEST-001",
        "vendor_id": "v-test",
        "vendor_name": "Test Vendor LLC",
        "customer_name": "LedgerGuard Enterprise",
        "invoice_date": "2026-10-23",
        "currency": "USD",
        "subtotal": "1000.00",
        "tax": "100.00",
        "total": "1100.00",
        "status": "VERIFIED_CLEAN",
        "line_items": [
            {"item_id": "li-1", "description": "Consulting", "quantity": 1, "unit_price": "1000.00", "total": "1000.00"}
        ],
        "metadata": {"source": "test_suite"},
        "forensics": {"risk": {"risk_level": "LOW", "risk_score": 0}},
    }
    store1.save_invoice(sample_invoice)
    del store1

    # Reconnect using separate instance simulating server restart
    store2 = SQLiteLedgerStore(db_path=str(db_file))
    reloaded = store2.get_invoice("INV-TEST-001")
    assert reloaded is not None
    assert reloaded["invoice_id"] == "INV-TEST-001"
    assert reloaded["total"] == "1100.00"
    assert reloaded["status"] == "VERIFIED_CLEAN"
    assert len(reloaded["line_items"]) == 1
    assert reloaded["forensics"]["risk"]["risk_level"] == "LOW"


def test_audit_blocks_persist_and_verify(tmp_path):
    """Cryptographic audit chain stored in SQLite must survive restart and verify cleanly."""
    db_file = tmp_path / "audit_persist.db"
    vault = get_argon_connector()

    store1 = SQLiteLedgerStore(db_path=str(db_file))

    # Genesis block
    gen_seal = vault.seal_payload(
        prev_hash="0" * 64,
        tx_id="GENESIS",
        action="GENESIS_CHAIN_INITIALIZED",
        timestamp="2026-10-22T00:00:00Z",
    )
    b0 = {
        "block_index": 0,
        "event_id": "EVT-000000",
        "prev_hash": "0" * 64,
        "tx_id": "GENESIS",
        "action": "GENESIS_CHAIN_INITIALIZED",
        "actor": "SYSTEM",
        "reason": "Genesis root",
        "timestamp": "2026-10-22T00:00:00Z",
        "sha256": gen_seal["sha256"],
        "argon2_seal": gen_seal["argon2_seal"],
        "parameters": gen_seal["parameters"],
        "metadata": {},
    }
    store1.save_audit_block(b0)

    # Block 1
    b1_seal = vault.seal_payload(
        prev_hash=gen_seal["argon2_seal"],
        tx_id="INV-TEST-001",
        action="INVOICE_INGESTED",
        timestamp="2026-10-23T10:00:00Z",
    )
    b1 = {
        "block_index": 1,
        "event_id": "EVT-000001",
        "prev_hash": gen_seal["argon2_seal"],
        "tx_id": "INV-TEST-001",
        "action": "INVOICE_INGESTED",
        "actor": "OPERATOR",
        "reason": "Test ingestion",
        "timestamp": "2026-10-23T10:00:00Z",
        "sha256": b1_seal["sha256"],
        "argon2_seal": b1_seal["argon2_seal"],
        "parameters": b1_seal["parameters"],
        "metadata": {},
    }
    store1.save_audit_block(b1)
    del store1

    # Reopen database in store2
    store2 = SQLiteLedgerStore(db_path=str(db_file))
    reloaded_chain = store2.get_audit_chain()
    assert len(reloaded_chain) == 2
    assert reloaded_chain[0]["block_index"] == 0
    assert reloaded_chain[1]["block_index"] == 1

    # Verify cryptographic integrity of reloaded chain
    verify_res = vault.verify_chain_integrity(reloaded_chain)
    assert verify_res["is_valid"] is True
    assert verify_res["verification_status"] == "TAMPER_FREE_VERIFIED"


def test_invoice_status_update_persistence(tmp_path):
    """Updating status in SQLite must persist across re-initialization."""
    db_file = tmp_path / "status_test.db"
    store1 = SQLiteLedgerStore(db_path=str(db_file))

    store1.save_invoice({
        "invoice_id": "INV-2026-102",
        "status": "FLAGGED_ARITHMETIC",
        "vendor_id": "v-nexus",
        "total": "3520.00",
    })
    store1.update_invoice_status("INV-2026-102", "QUARANTINED_DISPUTED")
    del store1

    store2 = SQLiteLedgerStore(db_path=str(db_file))
    updated = store2.get_invoice("INV-2026-102")
    assert updated["status"] == "QUARANTINED_DISPUTED"


def test_session_turns_and_vendor_policies_persistence(tmp_path):
    """Session conversational memory and vendor fraud policies must survive restarts."""
    db_file = tmp_path / "session_policy.db"
    store1 = SQLiteLedgerStore(db_path=str(db_file))

    turn = {
        "turn_index": 1,
        "session_id": "alexa-sess-42",
        "role": "user",
        "text": "Quarantine invoice 102",
        "timestamp": "2026-10-23T12:00:00Z",
    }
    store1.save_session_turn(turn)
    store1.save_vendor_policy("v-apex", "FROZEN_PENDING_INVESTIGATION")
    del store1

    store2 = SQLiteLedgerStore(db_path=str(db_file))
    turns = store2.get_session_memory(session_id="alexa-sess-42")
    assert len(turns) == 1
    assert turns[0]["text"] == "Quarantine invoice 102"

    policies = store2.get_vendor_policies()
    assert policies.get("v-apex") == "FROZEN_PENDING_INVESTIGATION"
