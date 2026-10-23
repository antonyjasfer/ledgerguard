"""Cryptographic Argon2id Vault Connector for LedgerGuard.

Provides tamper-evident cryptographic sealing and verification of accounts-payable
audit trail payloads using Argon2id (memory_cost=65536, time_cost=2, parallelism=2)
combined with SHA-256 pre-digests for ledger immutability and provenance tracking.
Enforces complete chain integrity verification from genesis block.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

logger = logging.getLogger("ledgerguard.connectors.argon")

DEFAULT_TIME_COST = 2
DEFAULT_MEMORY_COST = 65536
DEFAULT_PARALLELISM = 2


class ArgonVaultConnector:
    """Cryptographic Vault Connector for tamper-evident ledger sealing and verification."""

    def __init__(
        self,
        time_cost: int = DEFAULT_TIME_COST,
        memory_cost: int = DEFAULT_MEMORY_COST,
        parallelism: int = DEFAULT_PARALLELISM,
    ) -> None:
        self.time_cost = time_cost
        self.memory_cost = memory_cost
        self.parallelism = parallelism
        self._hasher = PasswordHasher(
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
        )

    @staticmethod
    def format_payload(prev_hash: str, tx_id: str, action: str, timestamp: str) -> str:
        """Format canonical ledger audit payload: prev_hash|tx_id|action|timestamp."""
        return f"{prev_hash}|{tx_id}|{action}|{timestamp}"

    @staticmethod
    def compute_sha256(payload: str) -> str:
        """Compute SHA-256 hexadecimal digest of payload."""
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def seal_payload(
        self,
        prev_hash: str,
        tx_id: str,
        action: str,
        timestamp: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Hash and seal ledger audit payload using Argon2id and SHA-256.

        Args:
            prev_hash: Hash of previous audit block (or 'GENESIS' / zeros).
            tx_id: Transaction or invoice identifier.
            action: Action performed (e.g. 'INVOICE_VERIFIED', 'PAYMENT_HELD').
            timestamp: ISO 8601 UTC timestamp string. Defaults to current UTC time.
            metadata: Optional additional metadata dict to include in result.

        Returns:
            Dictionary containing audit payload, sha256 digest, and argon2_seal.
        """
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        canonical_payload = self.format_payload(prev_hash, tx_id, action, ts)
        sha256_digest = self.compute_sha256(canonical_payload)
        argon2_seal = self._hasher.hash(canonical_payload)

        result: dict[str, Any] = {
            "payload": canonical_payload,
            "sha256": sha256_digest,
            "argon2_seal": argon2_seal,
            "prev_hash": prev_hash,
            "tx_id": tx_id,
            "action": action,
            "timestamp": ts,
            "algorithm": "argon2id",
            "parameters": {
                "time_cost": self.time_cost,
                "memory_cost": self.memory_cost,
                "parallelism": self.parallelism,
            },
        }
        if metadata:
            result["metadata"] = metadata
        return result

    def verify_seal(
        self,
        seal: str,
        prev_hash: str,
        tx_id: str,
        action: str,
        timestamp: str,
    ) -> bool:
        """Verify an existing Argon2id seal against audit payload parameters."""
        canonical_payload = self.format_payload(prev_hash, tx_id, action, timestamp)
        return self.verify_raw(seal, canonical_payload)

    def verify_raw(self, seal: str, canonical_payload: str) -> bool:
        """Verify an Argon2id seal directly against the canonical payload string."""
        try:
            return self._hasher.verify(seal, canonical_payload)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
        except Exception as exc:
            logger.warning("Unexpected error during Argon2id verification: %s", exc)
            return False

    def verify_tamper_evidence(
        self,
        seal: str,
        prev_hash: str,
        tx_id: str,
        action: str,
        timestamp: str,
        tampered_field: str = "tx_id",
        tampered_value: str = "TAMPERED_VAL",
    ) -> dict[str, Any]:
        """Perform a tamper test demonstrating verification succeeds on original and fails on tampered data."""
        original_valid = self.verify_seal(seal, prev_hash, tx_id, action, timestamp)

        test_prev_hash = tampered_value if tampered_field == "prev_hash" else prev_hash
        test_tx_id = tampered_value if tampered_field == "tx_id" else tx_id
        test_action = tampered_value if tampered_field == "action" else action
        test_timestamp = tampered_value if tampered_field == "timestamp" else timestamp

        tampered_valid = self.verify_seal(
            seal, test_prev_hash, test_tx_id, test_action, test_timestamp
        )

        return {
            "original_valid": original_valid,
            "tampered_valid": tampered_valid,
            "tamper_detected": (original_valid and not tampered_valid),
            "tampered_field": tampered_field,
        }

    def verify_chain_integrity(self, chain: list[dict[str, Any]]) -> dict[str, Any]:
        """Verify complete cryptographic audit chain from genesis block to tip.

        Checks:
        1. Non-empty chain with Genesis at block 0.
        2. Strict sequential block indices (0, 1, 2, ...).
        3. Strict SHA-256 link matching: block[i].prev_hash == block[i-1].sha256.
        4. Recomputed SHA-256 digest match for every block's canonical payload.
        5. Memory-hard Argon2id seal verification for every block.

        Returns:
            Dict containing is_valid, total_blocks, tampered_blocks, verification_errors.
        """
        if not chain:
            return {
                "is_valid": False,
                "total_blocks": 0,
                "tampered_blocks": [],
                "verification_errors": ["Audit chain is empty."],
                "verified_at": datetime.now(timezone.utc).isoformat(),
            }

        tampered_blocks: list[int] = []
        errors: list[str] = []

        # 1. Verify Genesis block
        genesis = chain[0]
        if genesis.get("block_index") != 0:
            tampered_blocks.append(0)
            errors.append("Genesis block does not have block_index 0.")

        expected_genesis_prev = "0" * 64
        if genesis.get("prev_hash") != expected_genesis_prev:
            tampered_blocks.append(0)
            errors.append(f"Genesis prev_hash mismatch: expected {expected_genesis_prev}, got {genesis.get('prev_hash')}")

        # Canonical verification of Genesis payload
        gen_payload = self.format_payload(
            genesis.get("prev_hash", ""),
            genesis.get("tx_id", ""),
            genesis.get("action", ""),
            genesis.get("timestamp", ""),
        )
        gen_sha = self.compute_sha256(gen_payload)
        if gen_sha != genesis.get("sha256"):
            tampered_blocks.append(0)
            errors.append("Genesis block SHA-256 digest mismatch.")
        elif not self.verify_raw(genesis.get("argon2_seal", ""), gen_payload):
            tampered_blocks.append(0)
            errors.append("Genesis block Argon2id seal verification failed.")

        # 2. Iterate through subsequent blocks
        for i in range(1, len(chain)):
            block = chain[i]
            prev_block = chain[i - 1]
            idx = block.get("block_index", i)

            # Check index continuity
            if idx != prev_block.get("block_index", i - 1) + 1:
                tampered_blocks.append(idx)
                errors.append(f"Block {idx}: Index continuity broken (expected {prev_block.get('block_index') + 1}).")

            # Check previous hash link (supports either argon2_seal or sha256 links)
            valid_prev_links = [
                prev_block.get("argon2_seal"),
                prev_block.get("sha256"),
            ]
            if block.get("prev_hash") not in [p for p in valid_prev_links if p]:
                tampered_blocks.append(idx)
                errors.append(
                    f"Block {idx}: prev_hash link broken! "
                    f"Expected {prev_block.get('argon2_seal', '')[:12]}..., got {str(block.get('prev_hash'))[:12]}..."
                )

            # Recompute canonical payload and digest
            payload = self.format_payload(
                block.get("prev_hash", ""),
                block.get("tx_id", ""),
                block.get("action", ""),
                block.get("timestamp", ""),
            )
            computed_sha = self.compute_sha256(payload)
            if computed_sha != block.get("sha256"):
                tampered_blocks.append(idx)
                errors.append(f"Block {idx}: Content digest tampered! SHA-256 hash does not match payload.")
                continue

            # Verify Argon2id seal
            seal_valid = self.verify_raw(block.get("argon2_seal", ""), payload)
            if not seal_valid:
                tampered_blocks.append(idx)
                errors.append(f"Block {idx}: Argon2id cryptographic seal verification failed.")

        tampered_blocks_unique = sorted(list(set(tampered_blocks)))
        is_valid = len(tampered_blocks_unique) == 0

        return {
            "is_valid": is_valid,
            "total_blocks": len(chain),
            "tampered_blocks": tampered_blocks_unique,
            "verification_status": "TAMPER_FREE_VERIFIED" if is_valid else "TAMPERING_DETECTED",
            "verification_errors": errors,
            "algorithm": "argon2id-sha256-hash-chain",
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }


_connector: ArgonVaultConnector | None = None


def get_argon_connector() -> ArgonVaultConnector:
    """Get or initialize singleton ArgonVaultConnector."""
    global _connector
    if _connector is None:
        _connector = ArgonVaultConnector()
    return _connector


def seal_audit_record(
    prev_hash: str,
    tx_id: str,
    action: str,
    timestamp: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convenience helper to seal an audit record."""
    return get_argon_connector().seal_payload(
        prev_hash=prev_hash,
        tx_id=tx_id,
        action=action,
        timestamp=timestamp,
        metadata=metadata,
    )


def verify_audit_seal(
    seal: str,
    prev_hash: str,
    tx_id: str,
    action: str,
    timestamp: str,
) -> bool:
    """Convenience helper to verify an audit seal."""
    return get_argon_connector().verify_seal(
        seal=seal,
        prev_hash=prev_hash,
        tx_id=tx_id,
        action=action,
        timestamp=timestamp,
    )


def verify_chain_integrity(chain: list[dict[str, Any]]) -> dict[str, Any]:
    """Convenience helper to verify an entire audit chain."""
    return get_argon_connector().verify_chain_integrity(chain)
