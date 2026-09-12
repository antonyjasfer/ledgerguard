from decimal import Decimal
"""Amazon DynamoDB invoice repository and audit event store for LedgerGuard.

Implements single-table storage design with partition key `INVOICE#{invoice_id}`
and sort keys `METADATA` for invoice entities and `EVENT#{timestamp}#{event_id}`
for immutable audit events.
"""

from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.models.audit import AuditEvent, AuditEventType
from app.models.decision import AgentDecision
from app.models.persistence import InvoiceRecord, _serialize_for_dynamodb
from app.services.interfaces import InvoiceRepository
from app.services.state import TERMINAL_STATES, ProcessingState


class DynamoDBInvoiceRepository(InvoiceRepository):
    """Invoice repository and audit trail backed by Amazon DynamoDB."""

    def __init__(
        self,
        table_name: str | None = None,
        region_name: str | None = None,
        profile_name: str | None = None,
        dynamodb_resource: Any = None,
        table: Any = None,
        settings: Settings | None = None,
    ):
        resolved_settings = settings or get_settings()
        self.table_name = table_name or resolved_settings.LEDGERGUARD_DYNAMODB_TABLE
        self.region_name = region_name or resolved_settings.AWS_REGION
        self.profile_name = profile_name if profile_name is not None else resolved_settings.AWS_PROFILE

        if table is not None:
            self._table = table
        elif dynamodb_resource is not None:
            self._table = dynamodb_resource.Table(self.table_name)
        else:
            session_kwargs: dict[str, Any] = {"region_name": self.region_name}
            if self.profile_name:
                session_kwargs["profile_name"] = self.profile_name
            session = boto3.Session(**session_kwargs)
            resource = session.resource("dynamodb")
            self._table = resource.Table(self.table_name)

    def save_record(self, record: InvoiceRecord) -> None:
        """Save or update the core invoice metadata record."""
        item = record.to_dynamodb_item()
        self._table.put_item(Item=item)

    def get_record(self, invoice_id: str) -> InvoiceRecord | None:
        """Retrieve an invoice record by its unique identifier."""
        pk = f"INVOICE#{invoice_id}"
        sk = "METADATA"
        response = self._table.get_item(Key={"PK": pk, "SK": sk})
        item = response.get("Item")
        if not item:
            return None
        return InvoiceRecord.from_dynamodb_item(item)

    def update_status(
        self,
        invoice_id: str,
        status: ProcessingState,
        decision: AgentDecision | None = None,
        updated_at: str | None = None,
    ) -> None:
        """Update lifecycle status and optionally the decision of an invoice record."""
        pk = f"INVOICE#{invoice_id}"
        sk = "METADATA"
        now = updated_at or datetime.now(timezone.utc).isoformat()

        update_expr = "SET processing_status = :status, updated_at = :updated_at"
        expr_values: dict[str, Any] = {
            ":status": status.value,
            ":updated_at": now,
        }

        if decision is not None:
            update_expr += ", decision = :decision"
            expr_values[":decision"] = decision.value

        self._table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
        )

    def save_audit_event(self, event: AuditEvent) -> None:
        """Persist an immutable audit trail event under the invoice's partition."""
        pk = f"INVOICE#{event.invoice_id}"
        sk = f"EVENT#{event.timestamp}#{event.event_id}"
        raw = event.model_dump()
        item = _serialize_for_dynamodb(raw)
        item["PK"] = pk
        item["SK"] = sk
        self._table.put_item(Item=item)

    def get_audit_events(self, invoice_id: str) -> list[AuditEvent]:
        """Retrieve all chronological audit events recorded for an invoice."""
        pk = f"INVOICE#{invoice_id}"
        response = self._table.query(
            KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with("EVENT#")
        )
        items = response.get("Items", [])
        events = []
        for item in items:
            cleaned = dict(item)
            cleaned.pop("PK", None)
            cleaned.pop("SK", None)
            if "event_type" in cleaned and isinstance(cleaned["event_type"], str):
                cleaned["event_type"] = AuditEventType(cleaned["event_type"])
            events.append(AuditEvent(**cleaned))
        return events

    def is_already_processed(self, invoice_id: str) -> bool:
        """Check if an invoice has already reached a completed terminal state."""
        record = self.get_record(invoice_id)
        if record is None:
            return False
        return record.processing_status in TERMINAL_STATES

    def idempotent_save(self, record: InvoiceRecord) -> bool:
        """Save record safely without corrupting completed state on repeated executions.

        Returns True if saved, False if skipped because invoice is already terminal.
        """
        if self.is_already_processed(record.invoice_id):
            return False
        self.save_record(record)
        return True

    def list_records(
        self,
        limit: int = 50,
        offset: int = 0,
        status: ProcessingState | None = None,
        vendor_id: str | None = None,
        search: str | None = None,
    ) -> list[InvoiceRecord]:
        """Scan and retrieve invoice records matching filter criteria."""
        from boto3.dynamodb.conditions import Attr
        filter_exp = Attr("SK").eq("METADATA")
        if status is not None:
            filter_exp = filter_exp & Attr("processing_status").eq(status.value)
        if vendor_id is not None:
            filter_exp = filter_exp & Attr("vendor_id").eq(vendor_id)

        response = self._table.scan(FilterExpression=filter_exp)
        items = response.get("Items", [])
        records = [InvoiceRecord.from_dynamodb_item(item) for item in items]

        if search:
            s = search.lower()
            records = [
                r for r in records
                if s in r.invoice_id.lower() or s in r.invoice_number.lower() or s in r.vendor_name.lower()
            ]

        # Sort descending by created_at
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[offset : offset + limit]

    def count_records(
        self,
        status: ProcessingState | None = None,
        vendor_id: str | None = None,
        search: str | None = None,
    ) -> int:
        records = self.list_records(limit=10000, offset=0, status=status, vendor_id=vendor_id, search=search)
        return len(records)

    def get_dashboard_stats(self) -> dict[str, Any]:
        """Compute aggregated statistics for dashboard."""
        all_records = self.list_records(limit=10000, offset=0)
        total = len(all_records)
        by_status: dict[str, int] = {}
        by_decision: dict[str, int] = {}
        by_risk_level: dict[str, int] = {}
        total_amount = Decimal("0.00")
        risk_scores: list[int] = []

        auto_approved = 0
        manual_review = 0
        blocked = 0
        pending = 0
        processed = 0

        for r in all_records:
            st = r.processing_status.value
            by_status[st] = by_status.get(st, 0) + 1

            if r.processing_status in TERMINAL_STATES:
                processed += 1
            else:
                pending += 1

            if r.decision is not None:
                dec = r.decision.value
                by_decision[dec] = by_decision.get(dec, 0) + 1
                if dec == "AUTO_APPROVE":
                    auto_approved += 1
                elif dec in ("MANUAL_REVIEW", "ESCALATE"):
                    manual_review += 1
                elif dec == "BLOCK":
                    blocked += 1

            if r.risk_level is not None:
                rl = r.risk_level.value
                by_risk_level[rl] = by_risk_level.get(rl, 0) + 1

            if r.risk_score is not None:
                risk_scores.append(r.risk_score)

            if r.total is not None:
                try:
                    total_amount += Decimal(str(r.total))
                except Exception:
                    pass

        avg_risk = float(sum(risk_scores) / len(risk_scores)) if risk_scores else 0.0
        approval_rate = float((auto_approved / processed) * 100) if processed > 0 else 0.0

        return {
            "total_invoices": total,
            "pending_invoices": pending,
            "processed_invoices": processed,
            "auto_approved_count": auto_approved,
            "manual_review_count": manual_review,
            "blocked_count": blocked,
            "total_amount_usd": float(total_amount),
            "average_risk_score": round(avg_risk, 1),
            "auto_approval_rate_pct": round(approval_rate, 1),
            "by_status": by_status,
            "by_decision": by_decision,
            "by_risk_level": by_risk_level,
        }
