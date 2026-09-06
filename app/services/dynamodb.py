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
