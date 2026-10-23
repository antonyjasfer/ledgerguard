"""Vercel serverless entrypoint for strands-bedrock-preflight service."""

import sys
from pathlib import Path
from fastapi import FastAPI

# Add package root to sys.path
package_root = Path(__file__).resolve().parent.parent
if str(package_root) not in sys.path:
    sys.path.insert(0, str(package_root))

from strands_bedrock_preflight import BedrockPreflightGuard

app = FastAPI(title="Strands Bedrock Preflight Service")
guard = BedrockPreflightGuard()


@app.get("/preflight")
async def get_preflight():
    """Run pre-flight check across Bedrock control plane."""
    return guard.run_preflight()


@app.get("/health")
async def get_health():
    """Health check endpoint."""
    return {"status": "ok", "service": "strands-bedrock-preflight"}
