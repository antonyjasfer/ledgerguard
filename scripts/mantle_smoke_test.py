"""Real model smoke test for LedgerGuard Phase 1 using Amazon Bedrock Mantle.

Verifies end-to-end integration across:
LedgerGuard Agent -> Strands -> Bedrock Mantle -> Google Gemma 3 27B IT -> Real Response.
"""

import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import boto3
from botocore.exceptions import ClientError

from app.agent.agent import create_ledgerguard_agent
from app.config import get_settings


def classify_error(exc: Exception) -> str:
    """Classify the failure category safely without leaking secrets."""
    exc_str = str(exc)
    exc_type = type(exc).__name__

    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("AccessDeniedException", "AccessDenied", "UnauthorizedOperation"):
            return "AccessDenied"
        if code in ("ValidationException", "InvalidParameterException"):
            return "ValidationException"
        if code in ("ThrottlingException", "RequestLimitExceeded"):
            return "Throttling"
        if code in ("ResourceNotFoundException", "ModelNotFound"):
            return "ModelNotFound"

    if "AccessDenied" in exc_str or "403" in exc_str:
        return "AccessDenied"
    if "ValidationException" in exc_str or "400" in exc_str:
        return "ValidationException"
    if "401" in exc_str or "Unauthorized" in exc_str or "Authentication" in exc_str:
        return "Authentication"
    if "404" in exc_str or "not found" in exc_str.lower():
        return "ModelNotFound"
    if "429" in exc_str or "throttl" in exc_str.lower():
        return "Throttling"
    if "credential" in exc_str.lower():
        return "Credential resolution"
    if "endpoint" in exc_str.lower() or "connect" in exc_str.lower():
        return "Endpoint/configuration"

    return f"Other ({exc_type})"


def run_mantle_smoke_test() -> int:
    """Execute the single live model smoke test via Amazon Bedrock Mantle."""

    # Gate 1: Confirm Python Environment
    venv_dir = os.path.normpath(os.path.join(PROJECT_ROOT, ".venv"))
    current_python = os.path.normpath(sys.executable)
    if not current_python.startswith(venv_dir):
        print("FAILED GATE: Python Environment")
        print("ERROR TYPE: EnvironmentMismatch")
        print(f"SAFE ERROR MESSAGE: Execution Python is '{current_python}', expected under '{venv_dir}'.")
        print("LIKELY ROOT CAUSE: Script executed with global or incorrect Python interpreter.")
        print("NEXT ACTION: Run using .\\.venv\\Scripts\\python.exe scripts\\mantle_smoke_test.py")
        return 1

    # Gate 2: Confirm Configuration
    settings = get_settings()
    if settings.LEDGERGUARD_MODEL_PROVIDER != "bedrock_mantle":
        print("FAILED GATE: Configuration Provider")
        print("ERROR TYPE: ProviderMismatch")
        print(f"SAFE ERROR MESSAGE: Configured provider is '{settings.LEDGERGUARD_MODEL_PROVIDER}', expected 'bedrock_mantle'.")
        print("LIKELY ROOT CAUSE: LEDGERGUARD_MODEL_PROVIDER is set to another provider in .env or environment.")
        print("NEXT ACTION: Set LEDGERGUARD_MODEL_PROVIDER=bedrock_mantle in .env.")
        return 1

    region = settings.AWS_REGION
    if region != "us-east-1":
        print("FAILED GATE: Configuration Region")
        print("ERROR TYPE: RegionMismatch")
        print(f"SAFE ERROR MESSAGE: Configured region is '{region}', expected 'us-east-1'.")
        print("LIKELY ROOT CAUSE: AWS_REGION is set to an unsupported Mantle region.")
        print("NEXT ACTION: Set AWS_REGION=us-east-1.")
        return 1

    model_id = settings.BEDROCK_MANTLE_MODEL_ID
    if model_id != "google.gemma-3-27b-it":
        print("FAILED GATE: Configuration Model ID")
        print("ERROR TYPE: ModelMismatch")
        print(f"SAFE ERROR MESSAGE: Configured model ID is '{model_id}', expected 'google.gemma-3-27b-it'.")
        print("LIKELY ROOT CAUSE: BEDROCK_MANTLE_MODEL_ID is pointing to an unverified model.")
        print("NEXT ACTION: Set BEDROCK_MANTLE_MODEL_ID=google.gemma-3-27b-it.")
        return 1

    # Gate 3: AWS Credential & Identity Verification
    profile_name = settings.AWS_PROFILE or "ledgerguard"
    os.environ["AWS_PROFILE"] = profile_name

    try:
        session = boto3.Session(profile_name=profile_name, region_name=region)
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        arn = identity.get("Arn", "")
    except Exception as exc:
        print("FAILED GATE: AWS Credential Resolution")
        print(f"ERROR TYPE: {classify_error(exc)}")
        print(f"SAFE ERROR MESSAGE: Failed to resolve AWS caller identity for profile '{profile_name}'.")
        print("LIKELY ROOT CAUSE: AWS profile credentials missing or expired.")
        print("NEXT ACTION: Check ~/.aws/credentials or run 'aws configure --profile ledgerguard'.")
        return 1

    if not arn.endswith(":user/ledgerguard-dev"):
        print("FAILED GATE: AWS Identity Verification")
        print("ERROR TYPE: IdentityMismatch")
        print(f"SAFE ERROR MESSAGE: Caller ARN '{arn}' does not end with ':user/ledgerguard-dev'.")
        print("LIKELY ROOT CAUSE: Active AWS profile resolved to an unexpected IAM user.")
        print("NEXT ACTION: Ensure profile 'ledgerguard' maps to IAM user 'ledgerguard-dev'.")
        return 1

    # Gate 4: Strands Agent Initialization
    try:
        agent = create_ledgerguard_agent(settings=settings)
    except Exception as exc:
        print("FAILED GATE: Strands Initialization")
        print(f"ERROR TYPE: {classify_error(exc)}")
        print(f"SAFE ERROR MESSAGE: Strands Agent construction failed: {type(exc).__name__}: {exc}")
        print("LIKELY ROOT CAUSE: Error inside model factory or agent initialization.")
        print("NEXT ACTION: Verify Strands OpenAIResponsesModel and configuration.")
        return 1

    # Gate 5: Live Model Invocation (Exactly ONE request, no automatic fallback, no retry)
    prompt = "Reply with exactly:\nLedgerGuard Bedrock Mantle verification passed."
    try:
        result = agent(prompt)
    except Exception as exc:
        print("FAILED GATE: Real model invocation")
        print(f"ERROR TYPE: {classify_error(exc)}")
        print(f"SAFE ERROR MESSAGE: Live Mantle call failed: {type(exc).__name__}: {exc}")
        print("LIKELY ROOT CAUSE: Bedrock Mantle endpoint error or token generation failure.")
        print("NEXT ACTION: Review safe error details and check AWS Bedrock Mantle endpoint connectivity.")
        return 1

    # Gate 6: Validate Real Response
    response_text = str(result).strip()
    if not response_text:
        print("FAILED GATE: Real response")
        print("ERROR TYPE: EmptyResponse")
        print("SAFE ERROR MESSAGE: Model invocation completed but returned an empty response.")
        print("LIKELY ROOT CAUSE: Upstream provider emitted zero text tokens.")
        print("NEXT ACTION: Check Bedrock Mantle inference quota and parameters.")
        return 1

    # Format Success Output
    print("========================================")
    print("LEDGERGUARD BEDROCK MANTLE SMOKE TEST")
    print("========================================")
    print("")
    print(f"Provider: Bedrock Mantle")
    print(f"Model: {model_id}")
    print(f"Region: {region}")
    print(f"AWS Identity: ledgerguard-dev")
    print("")
    print("Strands initialization: PASS")
    print("AWS credential resolution: PASS")
    print("Bedrock Mantle initialization: PASS")
    print("Real model invocation: PASS")
    print("Real response: PASS")
    print("")
    print("Response:")
    print(response_text)
    print("")
    print("========================================")
    print("BEDROCK MANTLE: PASS")
    print("========================================")

    return 0


if __name__ == "__main__":
    sys.exit(run_mantle_smoke_test())
