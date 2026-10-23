"""LedgerGuard Connectors Package.

Provides modular connectors for:
- AWS Bedrock + Strands Resilient Agent execution with automatic fallback
- Cryptographic Argon2id Vault sealing and tamper-evident verification
- Alexa+ MCP Streamable HTTP server implementing protocol version 2025-11-25
"""

from connectors.argon_connector import (
    ArgonVaultConnector,
    get_argon_connector,
    seal_audit_record,
    verify_audit_seal,
)
from connectors.aws_strands_connector import (
    BedrockStrandsConnector,
    get_bedrock_strands_connector,
    run_resilient_agent,
)
from connectors.alexa_mcp_connector import router as alexa_mcp_router

__all__ = [
    "ArgonVaultConnector",
    "get_argon_connector",
    "seal_audit_record",
    "verify_audit_seal",
    "BedrockStrandsConnector",
    "get_bedrock_strands_connector",
    "run_resilient_agent",
    "alexa_mcp_router",
]
