from decimal import Decimal, ROUND_HALF_UP
"""Amazon DynamoDB invoice repository, batch repository, and audit event store for LedgerGuard.

Implements single-table storage design with partition key `INVOICE#{invoice_id}` or `BATCH#{batch_id}`
and sort keys `METADATA` for core entities and `EVENT#{timestamp}#{event_id}` for immutable audit events,
and `DOCUMENT#{document_id}` for ingested batch documents.
"""

from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.models.audit import AuditEvent, AuditEventType
from app.models.batch import BatchRecord, DocumentIngestionRecord
from app.models.decision import AgentDecision
from app.models.persistence import InvoiceRecord, _serialize_for_dynamodb
from app.services.interfaces import BatchRepository, InvoiceRepository
from app.services.state import TERMINAL_STATES, ProcessingState


def _deserialize_from_dynamodb(val: Any) -> Any:
    """Convert DynamoDB Decimals to float or int for JSON serialization."""
    from decimal import Decimal, ROUND_HALF_UP
    if isinstance(val, Decimal):
        if val % 1 == 0:
            return int(val)
        return float(val)
    if isinstance(val, dict):
        return {k: _deserialize_from_dynamodb(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_deserialize_from_dynamodb(x) for x in val]
    return val


class DynamoDBInvoiceRepository(InvoiceRepository, BatchRepository):
    """Invoice and Batch repository and audit trail backed by Amazon DynamoDB."""

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
        try:
            return InvoiceRecord.from_dynamodb_item(item)
        except Exception as exc:
            logger.warning("Could not deserialize DynamoDB record for %s: %s", invoice_id, exc)
            return None

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
        filter_exp = Attr("SK").eq("METADATA") & Attr("PK").begins_with("INVOICE#")
        if status is not None:
            filter_exp = filter_exp & Attr("processing_status").eq(status.value)
        if vendor_id is not None:
            filter_exp = filter_exp & Attr("vendor_id").eq(vendor_id)

        response = self._table.scan(FilterExpression=filter_exp)
        items = response.get("Items", [])
        records = []
        for item in items:
            try:
                records.append(InvoiceRecord.from_dynamodb_item(item))
            except Exception as exc:
                logger.warning("Skipping invalid invoice record from DynamoDB: %s", exc)

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

    def get_dashboard_stats(
        self,
        batch_id: str | None = None,
        date_range: str | None = None,
    ) -> dict[str, Any]:
        """Compute aggregated statistics and AP Financial Summary for dashboard."""
        all_records = self.list_records(limit=10000, offset=0)

        # Filter by batch_id if supplied
        if batch_id:
            all_records = [
                r for r in all_records
                if (r.document_s3_key and f"BATCH#{batch_id}" in r.document_s3_key)
                or (r.document_s3_key and f"/{batch_id}/" in r.document_s3_key)
                or (r.invoice_id and batch_id in r.invoice_id)
            ]

        # Filter by date_range if supplied
        if date_range and date_range != "all_time":
            now = datetime.now(timezone.utc)
            filtered = []
            for r in all_records:
                d_str = r.invoice_date or r.created_at[:10]
                try:
                    inv_dt = datetime.fromisoformat(d_str if "T" in d_str else f"{d_str}T00:00:00+00:00")
                    if date_range == "today" and inv_dt.date() == now.date():
                        filtered.append(r)
                    elif date_range == "7_days" and (now - inv_dt).days <= 7:
                        filtered.append(r)
                    elif date_range == "30_days" and (now - inv_dt).days <= 30:
                        filtered.append(r)
                    else:
                        # If unable to match strictly, exclude
                        pass
                except Exception:
                    filtered.append(r)
            all_records = filtered

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

        # Phase 8: Strict Decimal financial aggregates
        total_invoice_value = Decimal("0.00")
        total_subtotal = Decimal("0.00")
        total_discount = Decimal("0.00")
        total_shipping = Decimal("0.00")
        total_tax = Decimal("0.00")
        estimated_payable_amount = Decimal("0.00")
        auto_approved_value = Decimal("0.00")
        manual_review_value = Decimal("0.00")
        blocked_value = Decimal("0.00")
        duplicate_value = Decimal("0.00")
        complete_payable_invoices_count = 0

        new_vendors_detected = 0
        duplicate_invoices_detected = 0
        verified_spend = Decimal("0.00")

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
                    if r.total is not None:
                        verified_spend += Decimal(str(r.total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        auto_approved_value += Decimal(str(r.total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                elif dec in ("MANUAL_REVIEW", "ESCALATE"):
                    manual_review += 1
                    if r.total is not None:
                        manual_review_value += Decimal(str(r.total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                elif dec == "BLOCK":
                    blocked += 1
                    if r.total is not None:
                        blocked_value += Decimal(str(r.total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            if r.risk_level is not None:
                rl = r.risk_level.value
                by_risk_level[rl] = by_risk_level.get(rl, 0) + 1

            if r.risk_score is not None:
                risk_scores.append(r.risk_score)

            # Invoiced Total
            if r.total is not None:
                amt = Decimal(str(r.total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                total_amount += amt
                total_invoice_value += amt

            # Subtotal
            sub_val: Decimal | None = None
            if r.subtotal is not None:
                sub_val = Decimal(str(r.subtotal)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                total_subtotal += sub_val
            elif r.line_items:
                sum_li = sum(Decimal(str(li.get("amount", "0"))) for li in r.line_items)
                if sum_li > Decimal("0.00"):
                    sub_val = sum_li.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    total_subtotal += sub_val

            # Discount
            disc_val: Decimal = Decimal("0.00")
            if r.discount is not None:
                disc_val = Decimal(str(r.discount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                total_discount += disc_val

            # Shipping
            ship_val: Decimal = Decimal("0.00")
            if r.shipping is not None:
                ship_val = Decimal(str(r.shipping)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                total_shipping += ship_val

            # Tax
            tax_val: Decimal | None = None
            if r.tax is not None:
                tax_val = Decimal(str(r.tax)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                total_tax += tax_val

            # Estimated Payable: SUBTOTAL - DISCOUNT + SHIPPING + TAX
            # Only computed when all financial components are complete (not NOT_STATED)
            if sub_val is not None and tax_val is not None:
                payable = (sub_val - disc_val + ship_val + tax_val).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                estimated_payable_amount += payable
                complete_payable_invoices_count += 1

            summ = str(r.verification_summary or "").upper()
            if "NEW_VENDOR" in summ:
                new_vendors_detected += 1
            if "CONFIRMED_DUPLICATE" in summ or "POSSIBLE_DUPLICATE" in summ:
                duplicate_invoices_detected += 1
                if r.total is not None:
                    duplicate_value += Decimal(str(r.total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        high_risk_invoices = by_risk_level.get("HIGH", 0) + by_risk_level.get("CRITICAL", 0)
        low_risk_invoices = by_risk_level.get("LOW", 0)
        avg_risk = float(sum(risk_scores) / len(risk_scores)) if risk_scores else 0.0
        approval_rate = float((auto_approved / processed) * 100) if processed > 0 else 0.0

        # Quality metrics across documents
        ext_success = 0
        ext_failed = 0
        low_conf = 0
        insufficient_data = 0
        try:
            batches = self.list_batches(limit=100)
            for b in batches:
                docs = self.list_batch_documents(b.batch_id)
                for d in docs:
                    st_val = d.status.value if hasattr(d.status, "value") else str(d.status)
                    if st_val in ("EXTRACTION_COMPLETED", "EXTRACTION_VALIDATED", "AUTO_APPROVED", "MANUAL_REVIEW"):
                        ext_success += 1
                    elif st_val == "EXTRACTION_FAILED":
                        ext_failed += 1
                    elif st_val == "INSUFFICIENT_CONFIDENCE":
                        low_conf += 1
                    elif st_val == "INSUFFICIENT_DATA":
                        insufficient_data += 1
        except Exception:
            pass

        coverage_pct = (
            float(round((complete_payable_invoices_count / total) * 100, 1))
            if total > 0 else 0.0
        )

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
            "new_vendors_detected": new_vendors_detected,
            "duplicate_invoices_detected": duplicate_invoices_detected,
            "high_risk_invoices": high_risk_invoices,
            "low_risk_invoices": low_risk_invoices,
            "total_verified_spend_usd": float(verified_spend),
            "active_policy_summary": {
                "company_name": "LedgerGuard Demo Corporation",
                "company_id": "LEDGERGUARD-DEMO",
                "auto_approval_limit": 5000.0,
                "high_value_threshold": 25000.0,
                "supported_currencies": ["USD", "EUR", "GBP"],
            },
            "total_invoice_value": total_invoice_value,
            "total_subtotal": total_subtotal,
            "total_discount": total_discount,
            "total_shipping": total_shipping,
            "total_tax": total_tax,
            "estimated_payable_amount": estimated_payable_amount,
            "estimated_payable_coverage_pct": coverage_pct,
            "estimated_payable_invoices_count": complete_payable_invoices_count,
            "auto_approved_value": auto_approved_value,
            "manual_review_value": manual_review_value,
            "blocked_value": blocked_value,
            "duplicate_value": duplicate_value,
            "extraction_success_count": ext_success,
            "extraction_failed_count": ext_failed,
            "low_confidence_count": low_conf,
            "insufficient_data_count": insufficient_data,
        }

    # =========================================================================
    # Phase 7: BatchRepository Implementation
    # =========================================================================

    def save_batch(self, batch: BatchRecord) -> None:
        """Save or overwrite a batch metadata record."""
        item = _serialize_for_dynamodb(batch.to_dynamodb_item())
        self._table.put_item(Item=item)

    def get_batch(self, batch_id: str) -> BatchRecord | None:
        """Retrieve a batch record by unique batch identifier."""
        pk = f"BATCH#{batch_id}"
        sk = "METADATA"
        response = self._table.get_item(Key={"PK": pk, "SK": sk})
        item = response.get("Item")
        if not item:
            return None
        return BatchRecord.from_dynamodb_item(item)

    def list_batches(self, limit: int = 50, offset: int = 0) -> list[BatchRecord]:
        """List batches ordered descending by creation timestamp."""
        filter_exp = Attr("SK").eq("METADATA") & Attr("PK").begins_with("BATCH#")
        response = self._table.scan(FilterExpression=filter_exp)
        items = response.get("Items", [])
        records = [BatchRecord.from_dynamodb_item(item) for item in items]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[offset : offset + limit]

    def save_document_record(self, doc: DocumentIngestionRecord) -> None:
        """Save or overwrite a document ingestion record."""
        item = _serialize_for_dynamodb(doc.to_dynamodb_item())
        self._table.put_item(Item=item)

    def get_document_record(self, batch_id: str, document_id: str) -> DocumentIngestionRecord | None:
        """Retrieve a document ingestion record by batch and document ID."""
        pk = f"BATCH#{batch_id}"
        sk = f"DOCUMENT#{document_id}"
        response = self._table.get_item(Key={"PK": pk, "SK": sk})
        item = response.get("Item")
        if not item:
            return None
        return DocumentIngestionRecord.from_dynamodb_item(item)

    def list_batch_documents(self, batch_id: str) -> list[DocumentIngestionRecord]:
        """List all document records belonging to a batch."""
        pk = f"BATCH#{batch_id}"
        response = self._table.query(
            KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with("DOCUMENT#")
        )
        items = response.get("Items", [])
        docs = [DocumentIngestionRecord.from_dynamodb_item(item) for item in items]
        docs.sort(key=lambda d: d.created_at)
        return docs

    def list_batch_documents_paginated(
        self,
        batch_id: str,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> tuple[list[DocumentIngestionRecord], int]:
        """List documents for a batch with fast pagination and optional status filtering."""
        all_docs = self.list_batch_documents(batch_id)
        if status:
            all_docs = [d for d in all_docs if (d.status.value if hasattr(d.status, "value") else d.status) == status]
        total = len(all_docs)
        return all_docs[offset : offset + limit], total


    def find_document_by_hash(self, document_hash: str) -> DocumentIngestionRecord | None:
        """Lookup an existing document by its content SHA-256 hash across all batches."""
        pk = f"DOCHASH#{document_hash}"
        response = self._table.query(
            KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with("DOCUMENT#")
        )
        items = response.get("Items", [])
        if items:
            item = items[0]
            orig_batch = item.get("batch_id")
            orig_doc = item.get("document_id")
            if orig_batch and orig_doc:
                found = self.get_document_record(orig_batch, orig_doc)
                if found:
                    return found

        # Fallback: scan for document records matching hash
        filter_exp = Attr("entity_type").eq("BATCH_DOCUMENT") & Attr("document_hash").eq(document_hash)
        scan_resp = self._table.scan(FilterExpression=filter_exp)
        scan_items = scan_resp.get("Items", [])
        if scan_items:
            return DocumentIngestionRecord.from_dynamodb_item(scan_items[0])
        return None

    def save_document_hash_index(
        self,
        document_hash: str,
        document_id: str,
        batch_id: str,
        s3_key: str | None = None,
    ) -> None:
        """Register a document content hash index item for fast duplicate lookups."""
        item = {
            "PK": f"DOCHASH#{document_hash}",
            "SK": f"DOCUMENT#{document_id}",
            "entity_type": "DOCUMENT_HASH_INDEX",
            "document_hash": document_hash,
            "document_id": document_id,
            "batch_id": batch_id,
            "s3_key": s3_key or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._table.put_item(Item=_serialize_for_dynamodb(item))


    def save_extraction_result(self, batch_id: str, document_id: str, result: Any) -> None:
        """Store structured extraction result in DynamoDB."""
        payload_data = result.to_dict_safe() if hasattr(result, "to_dict_safe") else result
        item = {
            "PK": f"BATCH#{batch_id}",
            "SK": f"EXTRACTION#{document_id}",
            "entity_type": "EXTRACTION_RESULT",
            "batch_id": batch_id,
            "document_id": document_id,
            "payload": payload_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._table.put_item(Item=_serialize_for_dynamodb(item))

    def get_extraction_result(self, batch_id: str, document_id: str) -> dict[str, Any] | None:
        """Retrieve extraction result for a document."""
        pk = f"BATCH#{batch_id}"
        sk = f"EXTRACTION#{document_id}"
        response = self._table.get_item(Key={"PK": pk, "SK": sk})
        item = response.get("Item")
        if item and "payload" in item:
            return _deserialize_from_dynamodb(item["payload"])
        return None


# Alias for dependency injection separation
DynamoDBBatchRepository = DynamoDBInvoiceRepository
