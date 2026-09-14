"""Local folder bulk invoice ingestion CLI script for LedgerGuard Phase 7.

Discovers supported documents (.pdf, .png, .jpg, .jpeg) in a target folder,
validates them, and submits them to the LedgerGuard Batch Ingestion API.

SECURITY:
Strictly forbids passing API keys via visible command-line arguments (--api-key).
Uses environment variable LEDGERGUARD_API_KEY or application settings.
Never logs or echoes secret values to stdout/stderr.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import httpx


SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


def discover_files(folder_path: Path) -> list[Path]:
    """Scan folder for supported invoice document files."""
    if not folder_path.is_dir():
        print(f"Error: Folder '{folder_path}' does not exist or is not a directory.", file=sys.stderr)
        sys.exit(1)

    files = [
        f for f in folder_path.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    files.sort(key=lambda p: p.name)
    return files


def run_ingestion(
    folder: str,
    api_url: str = "http://127.0.0.1:8000",
    source: str = "CLI_FOLDER",
) -> dict[str, Any]:
    """Execute folder ingestion via LedgerGuard REST API."""
    target_dir = Path(folder).resolve()
    print(f"Scanning '{target_dir}' for invoice documents...")

    candidate_files = discover_files(target_dir)
    if not candidate_files:
        print(f"No supported invoice documents (.pdf, .png, .jpg, .jpeg) found in '{target_dir}'.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(candidate_files)} candidate document(s).")

    # Secure authentication retrieval - NEVER via command line arguments
    api_key = os.getenv("LEDGERGUARD_API_KEY")
    headers: dict[str, str] = {}
    if api_key:
        headers["X-API-Key"] = api_key.strip()

    upload_files = []
    file_handles = []
    try:
        for file_path in candidate_files:
            handle = open(file_path, "rb")
            file_handles.append(handle)
            ext = file_path.suffix.lower()
            mime = "application/pdf" if ext == ".pdf" else f"image/{ext.lstrip('.')}"
            upload_files.append(("files", (file_path.name, handle, mime)))

        upload_endpoint = f"{api_url.rstrip('/')}/batches/upload"
        print(f"Uploading {len(upload_files)} document(s) to {upload_endpoint}...")

        data = {"source": source}
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                upload_endpoint,
                files=upload_files,
                data=data,
                headers=headers,
            )

        if response.status_code not in (200, 201):
            print(f"Ingestion failed with HTTP {response.status_code}: {response.text}", file=sys.stderr)
            sys.exit(1)

        result: dict[str, Any] = response.json()
        return result

    finally:
        for handle in file_handles:
            try:
                handle.close()
            except Exception:
                pass


def print_summary(batch_data: dict[str, Any]) -> None:
    """Print clean terminal summary of ingestion result."""
    batch_id = batch_data.get("batch_id", "UNKNOWN")
    status = batch_data.get("status", "UNKNOWN")
    source = batch_data.get("source", "CLI_FOLDER")
    received = batch_data.get("received_count", 0)
    accepted = batch_data.get("accepted_count", 0)
    rejected = batch_data.get("rejected_count", 0)
    duplicates = batch_data.get("duplicate_count", 0)
    failed = batch_data.get("failed_count", 0)
    queued = batch_data.get("queued_count", 0)
    docs = batch_data.get("documents", [])

    print("\n" + "=" * 64)
    print("           LedgerGuard Bulk Ingestion Summary")
    print("=" * 64)
    print(f"Batch ID:        {batch_id}")
    print(f"Lifecycle State: {status}")
    print(f"Source:          {source}")
    print(f"Files Scanned:   {received}")
    print(f"Accepted:        {accepted}")
    print(f"Duplicates:      {duplicates}")
    print(f"Rejected:        {rejected}")
    print(f"Failed:          {failed}")
    print(f"Queued Jobs:     {queued}")
    print("Document State:  AWAITING_EXTRACTION (Phase 7 Raw Ingestion)")
    print("-" * 64)

    print(f"{'Filename':<25} {'Status':<12} {'Document ID':<18} {'Size':<8}")
    print("-" * 64)
    for d in docs:
        fn = d.get("original_filename", "unknown")
        if len(fn) > 23:
            fn = fn[:20] + "..."
        st = d.get("status", "UNKNOWN")
        doc_id = d.get("document_id", "N/A")
        sz = f"{d.get('file_size', 0)} B"
        print(f"{fn:<25} {st:<12} {doc_id:<18} {sz:<8}")
        if st == "DUPLICATE":
            matched = d.get("matched_document_id", "unknown")
            print(f"   -> Duplicate detected! Matches prior document: {matched}")
        elif st == "REJECTED":
            reason = d.get("error_message", "Validation failed")
            print(f"   -> Rejected: {reason}")
    print("=" * 64 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest a folder of invoice documents into LedgerGuard (Phase 7)."
    )
    parser.add_argument(
        "--folder",
        type=str,
        default="demo_batch",
        help="Path to folder containing invoice documents (default: demo_batch)",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://127.0.0.1:8000",
        help="LedgerGuard API base URL (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--source",
        type=str,
        default="CLI_FOLDER",
        help="Ingestion source label (default: CLI_FOLDER)",
    )

    args = parser.parse_args()
    result = run_ingestion(folder=args.folder, api_url=args.api_url, source=args.source)
    print_summary(result)


if __name__ == "__main__":
    main()
