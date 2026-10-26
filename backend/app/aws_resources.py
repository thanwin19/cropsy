"""
aws_resources.py: where Cropsy keeps its data when it runs on AWS (S3 and DynamoDB) or locally.

CROPSY_STORE=local (default)  history in memory, logs in local files: nothing needs AWS besides Bedrock.
CROPSY_STORE=aws              history and logs in DynamoDB; reference photos served from S3 (CROPSY_BUCKET).
Names: tables  <CROPSY_PREFIX>-executions  and  <CROPSY_PREFIX>-events ;  bucket  CROPSY_BUCKET.
Nothing here creates a resource: scripts/provision_aws.py does that, only when asked with --apply.
"""
from __future__ import annotations

import os

from app import config

STORE = os.getenv("CROPSY_STORE", "local").lower()
PREFIX = os.getenv("CROPSY_PREFIX", "cropsy")
BUCKET = os.getenv("CROPSY_BUCKET", "")
REGION = os.getenv("CROPSY_REGION") or config.AWS_REGION
EXECUTIONS_TABLE = f"{PREFIX}-executions"
EVENTS_TABLE = f"{PREFIX}-events"

_session = None


def enabled() -> bool:
    return STORE == "aws"


def session():
    """boto3 session: the SSO profile on a laptop, the function's own role on Lambda."""
    global _session
    if _session is None:
        import boto3
        try:
            _session = boto3.Session(profile_name=os.getenv("AWS_PROFILE", config.AWS_PROFILE), region_name=REGION)
        except Exception:  # noqa: BLE001
            _session = boto3.Session(region_name=REGION)
    return _session


def dynamo():
    return session().resource("dynamodb")


def s3():
    return session().client("s3")


def presigned_asset(key: str, seconds: int = 3600) -> str | None:
    """A time-limited link to a private S3 object (reference photos), or None when S3 is not configured."""
    if not (enabled() and BUCKET):
        return None
    try:
        return s3().generate_presigned_url("get_object", Params={"Bucket": BUCKET, "Key": key}, ExpiresIn=seconds)
    except Exception:  # noqa: BLE001
        return None
