"""Alexa+ MCP Streamable HTTP Connector for LedgerGuard.

Implements the Model Context Protocol (MCP) Streamable HTTP transport and
specification version 2025-11-25. Exposes deterministic accounts-payable verification
tools, anomaly detection, and cryptographic Argon2id audit sealing to Alexa+ and Bedrock agents.

Supported MCP Methods:
- initialize (returns server info, capabilities, instructions, protocolVersion 2025-11-25)
- notifications/initialized
- tools/list (exposes AP verification tools and Argon2id cryptographic vault tools)
- tools/call (executes requested tool directly with typed argument parsing)
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.agent.tools import (
    calculate_invoice_arithmetic,
    calculate_invoice_risk,
    check_duplicate_invoice,
    detect_transaction_anomalies,
    evaluate_invoice_policy,
    get_vendor_history,
)
from connectors.argon_connector import seal_audit_record, verify_audit_seal, verify_chain_integrity
from connectors.aws_strands_connector import get_bedrock_strands_connector

logger = logging.getLogger("ledgerguard.connectors.alexa_mcp")

router = APIRouter(tags=["Alexa+ MCP Streamable HTTP"])

MCP_PROTOCOL_VERSION = "2025-11-25"
SERVER_NAME = "ledgerguard-alexa-plus-mcp"
SERVER_VERSION = "1.0.0"

# Tool metadata and schema definitions for tools/list
MCP_TOOLS_CATALOGUE = [
    {
        "name": "calculate_invoice_arithmetic",
        "description": (
            "Verify invoice arithmetic consistency using deterministic Decimal calculations. "
            "Validates line item products (quantity * unit_price), subtotals, tax, discount, and grand total. "
            "Returns PASS, FAIL, or INSUFFICIENT_DATA."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "invoice_data": {
                    "type": "string",
                    "description": "JSON string containing invoice data model fields",
                }
            },
            "required": ["invoice_data"],
        },
    },
    {
        "name": "check_duplicate_invoice",
        "description": (
            "Check whether an invoice is a duplicate against historical records. "
            "Returns CONFIRMED_DUPLICATE (same vendor and invoice number), "
            "POSSIBLE_DUPLICATE (same vendor, amount, and close date), or NO_DUPLICATE."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "invoice_data": {
                    "type": "string",
                    "description": "JSON string containing candidate invoice",
                },
                "historical_invoices": {
                    "type": "string",
                    "description": "JSON string containing array of historical invoices",
                },
            },
            "required": ["invoice_data", "historical_invoices"],
        },
    },
    {
        "name": "get_vendor_history",
        "description": (
            "Retrieve vendor historical profile, approval status, payment track record, and risk tier."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "vendor_id": {"type": "string", "description": "Vendor unique identifier"},
                "historical_invoices": {
                    "type": "string",
                    "description": "JSON string containing array of historical invoices",
                },
            },
            "required": ["vendor_id", "historical_invoices"],
        },
    },
    {
        "name": "evaluate_invoice_policy",
        "description": (
            "Evaluate invoice compliance against enterprise accounts-payable policies and spend limits."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "invoice_data": {"type": "string", "description": "JSON string containing invoice"},
                "vendor_history_json": {
                    "type": "string",
                    "description": "JSON string of vendor history evaluation",
                },
                "duplicate_result_json": {
                    "type": "string",
                    "description": "JSON string of duplicate check result",
                },
            },
            "required": ["invoice_data", "vendor_history_json", "duplicate_result_json"],
        },
    },
    {
        "name": "calculate_invoice_risk",
        "description": (
            "Compute composite accounts-payable risk score (0-100), risk tier (LOW/MEDIUM/HIGH/CRITICAL), "
            "risk factors, and recommended action (AUTO_APPROVE, MANUAL_REVIEW, BLOCK)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "arithmetic_result_json": {"type": "string"},
                "duplicate_result_json": {"type": "string"},
                "vendor_history_json": {"type": "string"},
                "policy_result_json": {"type": "string"},
                "invoice_data": {"type": "string"},
            },
            "required": [
                "arithmetic_result_json",
                "duplicate_result_json",
                "vendor_history_json",
                "policy_result_json",
                "invoice_data",
            ],
        },
    },
    {
        "name": "detect_transaction_anomalies",
        "description": (
            "Execute deterministic financial anomaly detection rules on an invoice against historical "
            "records. Detects recurring subscription price increases, duplicate billing, line-item arithmetic "
            "variances, and unregistered vendor spend breaches. Returns structured AnomalyScanReport."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "invoice_data": {
                    "type": "string",
                    "description": "JSON string containing invoice data model fields",
                },
                "historical_invoices": {
                    "type": "string",
                    "description": "JSON string containing array of historical invoices",
                },
            },
            "required": ["invoice_data", "historical_invoices"],
        },
    },
    {
        "name": "seal_ledger_audit_record",
        "description": (
            "Cryptographically seal an accounts-payable audit entry into the tamper-evident vault "
            "using Argon2id (64MB memory, 2 iterations, 2 threads) and SHA-256."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prev_hash": {
                    "type": "string",
                    "description": "Hash of previous audit entry in the chain, or 'GENESIS'",
                },
                "tx_id": {"type": "string", "description": "Invoice or transaction identifier"},
                "action": {
                    "type": "string",
                    "description": "Action performed (e.g. INVOICE_VERIFIED, PAYMENT_BLOCKED)",
                },
                "timestamp": {
                    "type": "string",
                    "description": "Optional ISO 8601 timestamp (defaults to current UTC)",
                },
            },
            "required": ["prev_hash", "tx_id", "action"],
        },
    },
    {
        "name": "verify_ledger_audit_seal",
        "description": (
            "Verify an Argon2id tamper-evident cryptographic seal against audit record parameters."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "seal": {"type": "string", "description": "Existing Argon2id seal string"},
                "prev_hash": {"type": "string", "description": "Previous hash"},
                "tx_id": {"type": "string", "description": "Transaction identifier"},
                "action": {"type": "string", "description": "Action performed"},
                "timestamp": {"type": "string", "description": "Timestamp sealed"},
            },
            "required": ["seal", "prev_hash", "tx_id", "action", "timestamp"],
        },
    },
    {
        "name": "verify_ledger_audit_chain",
        "description": (
            "Verify complete cryptographic audit chain from genesis block. Validates sequential "
            "SHA-256 linkages and Argon2id memory-hard seals for every block."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "chain": {
                    "type": "array",
                    "description": "Array of audit blocks to verify",
                    "items": {"type": "object"},
                }
            },
            "required": ["chain"],
        },
    },
    {
        "name": "verify_invoice_autonomous",
        "description": (
            "Run full autonomous accounts-payable verification pipeline with Bedrock resilience "
            "and generate a cryptographically sealed Argon2id audit record in one turn."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "invoice_data": {
                    "type": "string",
                    "description": "JSON string containing invoice model",
                },
                "prev_hash": {
                    "type": "string",
                    "description": "Hash of previous audit chain block (defaults to 'GENESIS')",
                },
            },
            "required": ["invoice_data"],
        },
    },
]


def _handle_tool_call(name: str, arguments: dict[str, Any]) -> str:
    """Dispatch tools/call to corresponding deterministic implementation."""
    if name == "calculate_invoice_arithmetic":
        inv_data = arguments.get("invoice_data", "{}")
        return calculate_invoice_arithmetic(inv_data)

    elif name == "check_duplicate_invoice":
        inv_data = arguments.get("invoice_data", "{}")
        hist_data = arguments.get("historical_invoices", "[]")
        return check_duplicate_invoice(inv_data, hist_data)

    elif name == "get_vendor_history":
        v_id = arguments.get("vendor_id", "")
        hist_data = arguments.get("historical_invoices", "[]")
        return get_vendor_history(v_id, hist_data)

    elif name == "evaluate_invoice_policy":
        inv_data = arguments.get("invoice_data", "{}")
        vh = arguments.get("vendor_history_json", "{}")
        dup = arguments.get("duplicate_result_json", "{}")
        return evaluate_invoice_policy(inv_data, vh, dup)

    elif name == "calculate_invoice_risk":
        arith = arguments.get("arithmetic_result_json", "{}")
        dup = arguments.get("duplicate_result_json", "{}")
        vh = arguments.get("vendor_history_json", "{}")
        pol = arguments.get("policy_result_json", "{}")
        inv_data = arguments.get("invoice_data", "{}")
        return calculate_invoice_risk(arith, dup, vh, pol, inv_data)

    elif name == "detect_transaction_anomalies":
        inv_data = arguments.get("invoice_data", "{}")
        hist_data = arguments.get("historical_invoices", "[]")
        return detect_transaction_anomalies(inv_data, hist_data)

    elif name == "seal_ledger_audit_record":
        prev_hash = arguments.get("prev_hash", "GENESIS")
        tx_id = arguments.get("tx_id", "")
        action = arguments.get("action", "INVOICE_AUDITED")
        ts = arguments.get("timestamp")
        res = seal_audit_record(prev_hash, tx_id, action, ts)
        return json.dumps(res)

    elif name == "verify_ledger_audit_seal":
        seal = arguments.get("seal", "")
        prev_hash = arguments.get("prev_hash", "")
        tx_id = arguments.get("tx_id", "")
        action = arguments.get("action", "")
        ts = arguments.get("timestamp", "")
        valid = verify_audit_seal(seal, prev_hash, tx_id, action, ts)
        return json.dumps({"valid": valid, "algorithm": "argon2id", "tx_id": tx_id})

    elif name == "verify_ledger_audit_chain":
        chain = arguments.get("chain", [])
        res = verify_chain_integrity(chain)
        return json.dumps(res)

    elif name == "verify_invoice_autonomous":
        inv_data = arguments.get("invoice_data", "{}")
        prev_hash = arguments.get("prev_hash", "GENESIS")
        connector = get_bedrock_strands_connector()
        agent_res = connector.run_resilient_agent(
            prompt="Verify invoice and compute risk",
            invoice_data=inv_data,
        )
        tx_id = "INV-AUDIT"
        try:
            parsed = json.loads(inv_data) if isinstance(inv_data, str) else inv_data
            tx_id = parsed.get("invoice_number", parsed.get("invoice_id", tx_id))
        except Exception:
            pass
        seal = seal_audit_record(
            prev_hash=prev_hash,
            tx_id=tx_id,
            action="INVOICE_AUTONOMOUS_VERIFIED",
            metadata={"active_engine": agent_res.get("active_engine")},
        )
        return json.dumps({
            "verification": agent_res,
            "audit_seal": seal,
        })

    else:
        raise ValueError(f"Unknown tool: {name}")


def _process_jsonrpc_request(data: dict[str, Any]) -> dict[str, Any] | None:
    """Process a single JSON-RPC 2.0 message conforming to MCP 2025-11-25."""
    method = data.get("method")
    req_id = data.get("id")

    # Notifications (no id)
    if method == "notifications/initialized":
        logger.info("MCP client acknowledged initialization")
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {"listChanged": False},
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
                "instructions": (
                    "LedgerGuard Alexa+ MCP Server providing accounts-payable invoice verification, "
                    "arithmetic validation, duplicate prevention, anomaly detection, and cryptographic Argon2id audit sealing."
                ),
            },
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": MCP_TOOLS_CATALOGUE,
            },
        }

    elif method == "tools/call":
        params = data.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        try:
            result_str = _handle_tool_call(tool_name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result_str,
                        }
                    ],
                    "isError": False,
                },
            }
        except Exception as exc:
            logger.error("Error executing tool %s: %s", tool_name, exc)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error executing tool {tool_name}: {exc}",
                        }
                    ],
                    "isError": True,
                },
            }

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not found",
            },
        }


@router.post("/mcp")
async def mcp_post_endpoint(
    request: Request,
    accept: str | None = Header(default=None),
) -> Response:
    """Streamable HTTP POST endpoint for MCP protocol version 2025-11-25.

    Supports application/json and text/event-stream (SSE) transports.
    """
    try:
        payload = await request.json()
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc}"},
            },
        )

    response_payload = _process_jsonrpc_request(payload)
    session_id = str(uuid.uuid4())

    # Return empty 204 for notifications
    if response_payload is None:
        return Response(status_code=204, headers={"mcp-session-id": session_id})

    # If client requested Server-Sent Events stream
    if accept and "text/event-stream" in accept:
        async def event_generator():
            event_data = f"event: message\ndata: {json.dumps(response_payload)}\n\n"
            yield event_data.encode("utf-8")

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "mcp-session-id": session_id,
                "protocol-version": MCP_PROTOCOL_VERSION,
            },
        )

    # Standard JSON-RPC response
    return JSONResponse(
        content=response_payload,
        headers={
            "mcp-session-id": session_id,
            "protocol-version": MCP_PROTOCOL_VERSION,
        },
    )


@router.get("/mcp")
async def mcp_get_endpoint() -> JSONResponse:
    """Streamable HTTP GET discovery/status endpoint for MCP server."""
    return JSONResponse(
        content={
            "status": "healthy",
            "service": SERVER_NAME,
            "version": SERVER_VERSION,
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "transport": "streamable-http",
            "tools_count": len(MCP_TOOLS_CATALOGUE),
        },
        headers={
            "protocol-version": MCP_PROTOCOL_VERSION,
        },
    )
