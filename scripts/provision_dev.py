"""Explicit opt-in script to provision development AWS resources for LedgerGuard.

CRITICAL ARCHITECTURAL RULE:
This script must be executed manually and explicitly. The LedgerGuard application
will NEVER auto-create AWS resources at startup.

Resources provisioned:
1. S3 Bucket: for invoice documents
2. DynamoDB Table: single-table design with PAY_PER_REQUEST billing
3. SQS Queue: for asynchronous invoice verification jobs
"""

import argparse
import sys
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import get_settings


def provision_s3(s3_client: Any, bucket_name: str, region: str) -> None:
    print(f"[*] Checking S3 bucket '{bucket_name}'...")
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"    [+] S3 bucket '{bucket_name}' already exists.")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in ("404", "NoSuchBucket"):
            print(f"    [*] Creating S3 bucket '{bucket_name}' in region '{region}'...")
            kwargs: dict[str, Any] = {"Bucket": bucket_name}
            if region != "us-east-1":
                kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
            s3_client.create_bucket(**kwargs)
            print(f"    [+] S3 bucket '{bucket_name}' created successfully.")
        else:
            print(f"    [-] Error checking/creating bucket: {exc}")
            raise


def provision_dynamodb(ddb_client: Any, table_name: str) -> None:
    print(f"[*] Checking DynamoDB table '{table_name}'...")
    try:
        ddb_client.describe_table(TableName=table_name)
        print(f"    [+] DynamoDB table '{table_name}' already exists.")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code == "ResourceNotFoundException":
            print(f"    [*] Creating DynamoDB table '{table_name}' (PAY_PER_REQUEST)...")
            ddb_client.create_table(
                TableName=table_name,
                KeySchema=[
                    {"AttributeName": "PK", "KeyType": "HASH"},
                    {"AttributeName": "SK", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "PK", "AttributeType": "S"},
                    {"AttributeName": "SK", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            print(f"    [+] DynamoDB table '{table_name}' creation initiated.")
        else:
            print(f"    [-] Error checking/creating DynamoDB table: {exc}")
            raise


def provision_sqs(sqs_client: Any, queue_name: str, visibility_timeout: int = 300) -> str:
    print(f"[*] Checking SQS queue '{queue_name}'...")
    try:
        res = sqs_client.get_queue_url(QueueName=queue_name)
        url = res.get("QueueUrl", "")
        print(f"    [+] SQS queue '{queue_name}' already exists: {url}")
        return url
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if "NonExistentQueue" in str(code) or "QueueDoesNotExist" in str(code):
            print(f"    [*] Creating SQS queue '{queue_name}'...")
            res = sqs_client.create_queue(
                QueueName=queue_name,
                Attributes={
                    "VisibilityTimeout": str(visibility_timeout),
                    "MessageRetentionPeriod": "86400",  # 1 day
                },
            )
            url = res.get("QueueUrl", "")
            print(f"    [+] SQS queue '{queue_name}' created: {url}")
            return url
        else:
            print(f"    [-] Error checking/creating SQS queue: {exc}")
            raise


def main():
    parser = argparse.ArgumentParser(description="Explicit LedgerGuard dev provisioning script.")
    parser.add_argument("--confirm", action="store_true", help="Confirm resource creation in AWS.")
    args = parser.parse_args()

    settings = get_settings()

    if not args.confirm:
        print("=" * 60)
        print("LEDGERGUARD AWS DEV PROVISIONING PREVIEW")
        print("=" * 60)
        print("Target AWS Region: ", settings.AWS_REGION)
        print("Target AWS Profile:", settings.AWS_PROFILE)
        print("S3 Bucket:         ", settings.LEDGERGUARD_S3_BUCKET or "<not configured>")
        print("DynamoDB Table:    ", settings.LEDGERGUARD_DYNAMODB_TABLE)
        print("SQS Queue:         ", "ledgerguard-invoice-jobs (or configured URL)")
        print()
        print("To execute provisioning, run with --confirm:")
        print("  python scripts/provision_dev.py --confirm")
        print("=" * 60)
        sys.exit(0)

    session_kwargs: dict[str, Any] = {"region_name": settings.AWS_REGION}
    if settings.AWS_PROFILE:
        session_kwargs["profile_name"] = settings.AWS_PROFILE
    session = boto3.Session(**session_kwargs)

    print("=" * 60)
    print("PROVISIONING AWS RESOURCES...")
    print("=" * 60)

    if settings.LEDGERGUARD_S3_BUCKET:
        s3 = session.client("s3")
        provision_s3(s3, settings.LEDGERGUARD_S3_BUCKET, settings.AWS_REGION)
    else:
        print("[!] LEDGERGUARD_S3_BUCKET not set in .env; skipping S3.")

    ddb = session.client("dynamodb")
    provision_dynamodb(ddb, settings.LEDGERGUARD_DYNAMODB_TABLE)

    sqs = session.client("sqs")
    provision_sqs(sqs, "ledgerguard-invoice-jobs", settings.SQS_VISIBILITY_TIMEOUT)

    print("=" * 60)
    print("PROVISIONING COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    main()
