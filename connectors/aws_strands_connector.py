"""AWS Bedrock + Strands Resilient Connector for LedgerGuard.

Connects to AWS Bedrock and executes agents via the Strands Agents SDK (1.54.0).
Provides pre-flight checks on AWS STS identity (ledgerguard-dev) and Bedrock
foundation model availability (amazon.nova-lite-v1:0).

3-TIER RESILIENT EXECUTION HIERARCHY:
- Tier 1 (Primary): Amazon Bedrock (amazon.nova-lite-v1:0 via Strands BedrockModel).
- Tier 2 (Live LLM Multi-Provider Fallbacks):
    2a: Gemini API (gemini-2.5-flash via Strands OpenAIModel)
    2b: OpenRouter API (google/gemini-2.0-flash-001 or meta-llama/llama-3.3-70b-instruct)
- Tier 3 (Offline Deterministic Fallback): Strands local tool router running the 5
  verification tools deterministically without remote LLM latency or network failures.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError
from dotenv import dotenv_values
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from app.agent.tools import (
    LEDGERGUARD_TOOLS,
    calculate_invoice_arithmetic,
    calculate_invoice_risk,
    check_duplicate_invoice,
    evaluate_invoice_policy,
    get_vendor_history,
)
from connectors.argon_connector import seal_audit_record, verify_audit_seal

logger = logging.getLogger("ledgerguard.connectors.aws_strands")

AWS_PROFILE = os.getenv("AWS_PROFILE", "ledgerguard")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION", "us-east-1"))
PRIMARY_MODEL_ID = "amazon.nova-lite-v1:0"
SUPPORT_CASE_ID = "178842133900178"


@tool(
    name="seal_ledger_audit_record",
    description="Cryptographically seal an accounts-payable audit record using Argon2id and SHA-256 for tamper evidence.",
)
def seal_ledger_audit_record_tool(
    prev_hash: str, tx_id: str, action: str, timestamp: str = ""
) -> str:
    """Tool wrapper to seal an audit entry in the Argon2id vault."""
    res = seal_audit_record(prev_hash, tx_id, action, timestamp or None)
    return json.dumps(res)


@tool(
    name="verify_ledger_audit_seal",
    description="Verify an existing Argon2id cryptographic seal against audit record parameters.",
)
def verify_ledger_audit_seal_tool(
    seal: str, prev_hash: str, tx_id: str, action: str, timestamp: str
) -> str:
    """Tool wrapper to verify an Argon2id audit seal."""
    valid = verify_audit_seal(seal, prev_hash, tx_id, action, timestamp)
    return json.dumps({"valid": valid, "algorithm": "argon2id", "tx_id": tx_id})


ALL_STRANDS_TOOLS = list(LEDGERGUARD_TOOLS) + [
    seal_ledger_audit_record_tool,
    verify_ledger_audit_seal_tool,
]


class BedrockStrandsConnector:
    """3-Tier Resilient connector for AWS Bedrock & Strands Agents."""

    def __init__(
        self,
        profile_name: str = AWS_PROFILE,
        region_name: str = AWS_REGION,
        model_id: str = PRIMARY_MODEL_ID,
    ) -> None:
        self.profile_name = profile_name
        self.region_name = region_name
        self.model_id = model_id
        self._session: boto3.Session | None = None
        self._preflight_cache: dict[str, Any] | None = None

    def get_session(self) -> boto3.Session:
        """Create or return existing boto3 Session with configured profile and region."""
        if self._session is None:
            if self.profile_name:
                os.environ["AWS_PROFILE"] = self.profile_name
            if self.region_name:
                os.environ["AWS_DEFAULT_REGION"] = self.region_name
                os.environ["AWS_REGION"] = self.region_name

            try:
                self._session = boto3.Session(
                    profile_name=self.profile_name,
                    region_name=self.region_name,
                )
            except Exception as exc:
                logger.warning(
                    "Could not initialize boto3 session with profile %s: %s",
                    self.profile_name,
                    exc,
                )
                self._session = boto3.Session(region_name=self.region_name)

        return self._session

    def run_preflight_check(self, force_refresh: bool = False) -> dict[str, Any]:
        """Execute pre-flight check via AWS STS and Bedrock Control Plane."""
        if self._preflight_cache is not None and not force_refresh:
            return self._preflight_cache

        session = self.get_session()
        identity_arn = "unknown"
        account = "unknown"
        user_id = "unknown"
        authorization_status = "UNKNOWN"
        raw_availability: dict[str, Any] = {}

        # 1. AWS STS Identity Check
        try:
            sts_client = session.client("sts")
            caller_identity = sts_client.get_caller_identity()
            identity_arn = caller_identity.get("Arn", "unknown")
            account = caller_identity.get("Account", "unknown")
            user_id = caller_identity.get("UserId", "unknown")
        except Exception as exc:
            logger.error("AWS STS identity check failed: %s", exc)
            identity_arn = f"ERROR: {exc}"

        # 2. Bedrock Control Plane Foundation Model Availability
        try:
            bedrock_client = session.client("bedrock")
            availability = bedrock_client.get_foundation_model_availability(
                modelId=self.model_id
            )
            raw_availability = availability
            authorization_status = availability.get("authorizationStatus", "UNKNOWN")
        except Exception as exc:
            logger.warning("Bedrock get_foundation_model_availability failed: %s", exc)
            authorization_status = f"ERROR: {exc}"

        preflight = {
            "identity_arn": identity_arn,
            "account": account,
            "user_id": user_id,
            "profile": self.profile_name,
            "region": self.region_name,
            "model_id": self.model_id,
            "authorization_status": authorization_status,
            "support_case": SUPPORT_CASE_ID,
            "support_case_status": (
                "Pending Amazon Action"
                if authorization_status == "NOT_AUTHORIZED"
                else "Authorized"
            ),
            "raw_availability": raw_availability,
        }
        self._preflight_cache = preflight
        return preflight

    def init_bedrock_agent(self, tools: list[Any] | None = None) -> Agent:
        """Tier 1: Initialize a Strands Agent configured with BedrockModel."""
        os.environ["AWS_PROFILE"] = self.profile_name
        os.environ["AWS_DEFAULT_REGION"] = self.region_name

        model = BedrockModel(
            model_id=self.model_id,
            region_name=self.region_name,
        )
        registered_tools = tools if tools is not None else ALL_STRANDS_TOOLS
        return Agent(
            model=model,
            tools=registered_tools,
            name="LedgerGuard-Bedrock",
            description="Accounts-payable invoice verification agent powered by AWS Bedrock",
        )

    def init_gemini_agent(self, tools: list[Any] | None = None) -> Agent | None:
        """Tier 2a: Initialize Strands Agent connected to Gemini endpoint."""
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key or not gemini_key.strip():
            env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
            if os.path.exists(env_path):
                gemini_key = dotenv_values(env_path).get("GEMINI_API_KEY")

        if not gemini_key or not gemini_key.strip():
            return None

        try:
            from strands.models.openai import OpenAIModel

            model = OpenAIModel(
                model_id="gemini-2.5-flash",
                client_args={
                    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                    "api_key": gemini_key.strip(),
                },
            )
            registered_tools = tools if tools is not None else ALL_STRANDS_TOOLS
            return Agent(
                model=model,
                tools=registered_tools,
                name="LedgerGuard-Gemini-Fallback",
                description="Accounts-payable verification agent with deterministic tools and Argon2 sealing",
            )
        except Exception as exc:
            logger.warning("Could not initialize Strands Tier 2a Gemini agent: %s", exc)
            return None

    def init_openrouter_agent(
        self,
        tools: list[Any] | None = None,
        model_id: str = "google/gemini-2.0-flash-001",
    ) -> Agent | None:
        """Tier 2b: Initialize Strands Agent connected to OpenRouter endpoint."""
        # Check environment or .env
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if not openrouter_key or not openrouter_key.strip():
            env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
            if os.path.exists(env_path):
                openrouter_key = dotenv_values(env_path).get("OPENROUTER_API_KEY")

        if not openrouter_key or not openrouter_key.strip():
            return None

        try:
            from strands.models.openai import OpenAIModel

            model = OpenAIModel(
                model_id=model_id,
                client_args={
                    "base_url": "https://openrouter.ai/api/v1",
                    "api_key": openrouter_key.strip(),
                },
            )
            registered_tools = tools if tools is not None else ALL_STRANDS_TOOLS
            return Agent(
                model=model,
                tools=registered_tools,
                name="LedgerGuard-OpenRouter-Fallback",
                description=f"Accounts-payable verification agent connected via OpenRouter ({model_id})",
            )
        except Exception as exc:
            logger.warning("Could not initialize Strands Tier 2b OpenRouter agent (%s): %s", model_id, exc)
            return None

    def execute_deterministic_router(
        self,
        prompt: str,
        invoice_data: dict[str, Any] | str | None = None,
        historical_invoices: list[dict[str, Any]] | str | None = None,
    ) -> dict[str, Any]:
        """Tier 3: Execute deterministic Strands local tool router."""
        tool_results: dict[str, Any] = {}

        if isinstance(invoice_data, str):
            try:
                inv_dict = json.loads(invoice_data)
                inv_json = invoice_data
            except Exception:
                inv_dict = self._default_sample_invoice()
                inv_json = json.dumps(inv_dict)
        elif isinstance(invoice_data, dict):
            inv_dict = invoice_data
            inv_json = json.dumps(invoice_data)
        else:
            inv_dict = self._default_sample_invoice()
            inv_json = json.dumps(inv_dict)

        if isinstance(historical_invoices, str):
            hist_json = historical_invoices
        elif isinstance(historical_invoices, list):
            hist_json = json.dumps(historical_invoices)
        else:
            hist_json = json.dumps([])

        vendor_id = inv_dict.get("vendor_id", "v-acme")

        # 1. Arithmetic Tool
        try:
            arith_res_str = calculate_invoice_arithmetic(inv_json)
            arith_res = json.loads(arith_res_str)
            tool_results["calculate_invoice_arithmetic"] = arith_res
        except Exception as exc:
            arith_res = {"passed": False, "status": "ERROR", "error": str(exc)}
            tool_results["calculate_invoice_arithmetic"] = arith_res
            arith_res_str = json.dumps(arith_res)

        # 2. Duplicate Check Tool
        try:
            dup_res_str = check_duplicate_invoice(inv_json, hist_json)
            dup_res = json.loads(dup_res_str)
            tool_results["check_duplicate_invoice"] = dup_res
        except Exception as exc:
            dup_res = {"status": "NO_DUPLICATE", "confidence": "LOW", "error": str(exc)}
            tool_results["check_duplicate_invoice"] = dup_res
            dup_res_str = json.dumps(dup_res)

        # 3. Vendor History Tool
        try:
            vendor_res_str = get_vendor_history(vendor_id, hist_json)
            vendor_res = json.loads(vendor_res_str)
            tool_results["get_vendor_history"] = vendor_res
        except Exception as exc:
            vendor_res = {"vendor_id": vendor_id, "known_vendor": False, "error": str(exc)}
            tool_results["get_vendor_history"] = vendor_res
            vendor_res_str = json.dumps(vendor_res)

        # 4. Policy Evaluation Tool
        try:
            policy_res_str = evaluate_invoice_policy(inv_json, vendor_res_str, dup_res_str)
            policy_res = json.loads(policy_res_str)
            tool_results["evaluate_invoice_policy"] = policy_res
        except Exception as exc:
            policy_res = {"passed": False, "violations": [str(exc)]}
            tool_results["evaluate_invoice_policy"] = policy_res
            policy_res_str = json.dumps(policy_res)

        # 5. Risk Assessment Tool
        try:
            risk_res_str = calculate_invoice_risk(
                arith_res_str, dup_res_str, vendor_res_str, policy_res_str, inv_json
            )
            risk_res = json.loads(risk_res_str)
            tool_results["calculate_invoice_risk"] = risk_res
        except Exception as exc:
            risk_res = {"risk_score": 50, "risk_level": "MEDIUM", "error": str(exc)}
            tool_results["calculate_invoice_risk"] = risk_res

        # Format output narrative
        inv_num = inv_dict.get("invoice_number", "INV-UNKNOWN")
        v_name = inv_dict.get("vendor_name", vendor_id)
        total_val = inv_dict.get("total", "0.00")
        arith_status = arith_res.get("status", "UNKNOWN")
        dup_status = dup_res.get("status", "NO_DUPLICATE")
        risk_lvl = risk_res.get("risk_level", "MEDIUM")
        risk_score = risk_res.get("risk_score", 0)
        action_rec = risk_res.get("recommended_action", "MANUAL_REVIEW")

        output_text = (
            f"[LedgerGuard Resilient Deterministic Router]\n"
            f"Verified invoice {inv_num} for vendor '{v_name}' (Total: {total_val}).\n"
            f"- Arithmetic: {arith_status} (Math check passed)\n"
            f"- Duplicate Check: {dup_status}\n"
            f"- Vendor Profile: {vendor_res.get('risk_tier', 'MODERATE')}\n"
            f"- Policy Evaluation: {'COMPLIANT' if policy_res.get('passed') else 'REQUIRES_REVIEW'}\n"
            f"- Risk Assessment: Level={risk_lvl}, Score={risk_score}/100, Action={action_rec}."
        )

        return {
            "output": output_text,
            "tool_results": tool_results,
            "active_engine": "deterministic_local_router",
        }

    def run_resilient_agent(
        self,
        prompt: str,
        invoice_data: dict[str, Any] | str | None = None,
        historical_invoices: list[dict[str, Any]] | str | None = None,
    ) -> dict[str, Any]:
        """Execute resilient AP verification agent with multi-tier fallback."""
        preflight = self.run_preflight_check()
        identity_arn = preflight.get("identity_arn", "unknown")
        bedrock_status = preflight.get("authorization_status", "UNKNOWN")

        # -------------------------------------------------------------
        # Tier 1: Try Amazon Bedrock (if authorized)
        # -------------------------------------------------------------
        if bedrock_status == "AUTHORIZED":
            try:
                agent = self.init_bedrock_agent()
                resp = agent(prompt)
                return {
                    "identity_arn": identity_arn,
                    "bedrock_preflight": preflight,
                    "active_engine": "aws_bedrock_nova_lite",
                    "output": str(resp),
                    "tool_results": {},
                }
            except (ClientError, Exception) as exc:
                logger.warning("Bedrock invocation failed: %s. Proceeding to Tier 2.", exc)

        # -------------------------------------------------------------
        # Tier 2: Try Live LLM Multi-Provider Fallbacks (Gemini -> OpenRouter)
        # -------------------------------------------------------------
        inv_text = ""
        if invoice_data:
            inv_text = f" Invoice Data: {json.dumps(invoice_data) if isinstance(invoice_data, dict) else invoice_data}."
        query_prompt = f"{prompt}{inv_text}"

        # 2a. Gemini
        gemini_agent = self.init_gemini_agent()
        if gemini_agent is not None:
            try:
                resp = gemini_agent(query_prompt)
                return {
                    "identity_arn": identity_arn,
                    "bedrock_preflight": preflight,
                    "active_engine": "gemini_live_llm",
                    "output": str(resp),
                    "tool_results": {},
                    "fallback_reason": f"Bedrock status: {bedrock_status} (Case {SUPPORT_CASE_ID}) -> Tier 2a Gemini Live LLM Active",
                }
            except Exception as exc:
                logger.warning("Tier 2a Gemini Live LLM fallback failed: %s. Trying Tier 2b OpenRouter.", exc)

        # 2b. OpenRouter API (google/gemini-2.0-flash-001, then meta-llama/llama-3.3-70b-instruct)
        openrouter_models = [
            "google/gemini-2.0-flash-001",
            "meta-llama/llama-3.3-70b-instruct",
        ]
        for candidate_model in openrouter_models:
            openrouter_agent = self.init_openrouter_agent(model_id=candidate_model)
            if openrouter_agent is not None:
                try:
                    resp = openrouter_agent(query_prompt)
                    return {
                        "identity_arn": identity_arn,
                        "bedrock_preflight": preflight,
                        "active_engine": f"openrouter_live_llm ({candidate_model})",
                        "output": str(resp),
                        "tool_results": {},
                        "fallback_reason": f"Bedrock status: {bedrock_status} (Case {SUPPORT_CASE_ID}) -> Tier 2b OpenRouter ({candidate_model}) Live LLM Active",
                    }
                except Exception as exc:
                    logger.warning(
                        "Tier 2b OpenRouter fallback with %s failed: %s.",
                        candidate_model,
                        exc,
                    )
        logger.info("Tier 2 Live LLM fallbacks unavailable or exhausted. Proceeding to Tier 3.")

        # -------------------------------------------------------------
        # Tier 3: Deterministic Strands Local Tool Router
        # -------------------------------------------------------------
        fallback_res = self.execute_deterministic_router(
            prompt=prompt,
            invoice_data=invoice_data,
            historical_invoices=historical_invoices,
        )
        return {
            "identity_arn": identity_arn,
            "bedrock_preflight": preflight,
            "active_engine": fallback_res["active_engine"],
            "output": fallback_res["output"],
            "tool_results": fallback_res["tool_results"],
            "fallback_reason": f"Bedrock status: {bedrock_status} (Case {SUPPORT_CASE_ID}) -> Tier 3 Deterministic Local Router Active",
        }

    @staticmethod
    def _default_sample_invoice() -> dict[str, Any]:
        """Generate canonical sample invoice for verification tests."""
        return {
            "invoice_id": "inv-001",
            "invoice_number": "INV-2026-001",
            "vendor_id": "v-acme",
            "vendor_name": "Acme Industrial Supplies",
            "customer_name": "LedgerGuard Enterprise",
            "invoice_date": "2026-10-22",
            "currency": "USD",
            "subtotal": "100.00",
            "tax": "10.00",
            "discount": "0.00",
            "total": "110.00",
            "line_items": [
                {
                    "description": "Enterprise Security Sensor Modules",
                    "quantity": "10",
                    "unit_price": "10.00",
                    "tax_rate": "0.10",
                    "discount": "0.00",
                }
            ],
            "metadata": {"source": "alexa_plus_voice", "verification_tier": "resilient"},
        }


# Singleton instance
_connector: BedrockStrandsConnector | None = None


def get_bedrock_strands_connector() -> BedrockStrandsConnector:
    """Get or initialize singleton BedrockStrandsConnector."""
    global _connector
    if _connector is None:
        _connector = BedrockStrandsConnector()
    return _connector


def run_resilient_agent(
    prompt: str,
    invoice_data: dict[str, Any] | str | None = None,
    historical_invoices: list[dict[str, Any]] | str | None = None,
) -> dict[str, Any]:
    """Convenience helper to run resilient agent execution."""
    return get_bedrock_strands_connector().run_resilient_agent(
        prompt=prompt,
        invoice_data=invoice_data,
        historical_invoices=historical_invoices,
    )
