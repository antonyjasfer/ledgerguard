import boto3

print("=== LedgerGuard Bedrock Runtime Smoke Test ===")

session = boto3.Session(
    profile_name="ledgerguard",
    region_name="us-east-1",
)

sts = session.client("sts")
identity = sts.get_caller_identity()

print("AWS identity:", identity["Arn"])

client = session.client("bedrock-runtime")

response = client.converse(
    modelId="amazon.nova-lite-v1:0",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "text": "Reply with exactly: LedgerGuard runtime verification passed."
                }
            ],
        }
    ],
    inferenceConfig={
        "maxTokens": 20,
    },
)

text = response["output"]["message"]["content"][0]["text"]

print("MODEL RESPONSE:")
print(text)
print("=== TEST COMPLETE ===")