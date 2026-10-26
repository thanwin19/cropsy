"""events.py: small append-only logs (unclear questions, feedback, photo findings) in DynamoDB table <prefix>-events (key: kind + time)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app import aws_resources as aws


def _table():
    return aws.dynamo().Table(aws.EVENTS_TABLE)


def put(kind: str, row: dict) -> None:
    ts = row.get("time") or datetime.now(timezone.utc).isoformat()
    _table().put_item(Item={"kind": kind, "ts": f"{ts}#{uuid.uuid4().hex[:6]}", "data": json.dumps(row, ensure_ascii=False, default=str)})


def recent(kind: str, n: int = 100) -> list[dict]:
    """Newest n rows of this kind, returned oldest first (the same order the local files use)."""
    from boto3.dynamodb.conditions import Key
    r = _table().query(KeyConditionExpression=Key("kind").eq(kind), ScanIndexForward=False, Limit=n)
    return [json.loads(i["data"]) for i in reversed(r.get("Items", []))]


def clear(kinds=("miss", "feedback", "photo_finding")) -> None:
    from boto3.dynamodb.conditions import Key
    t = _table()
    for k in kinds:
        while True:
            items = t.query(KeyConditionExpression=Key("kind").eq(k), Limit=100).get("Items", [])
            if not items:
                break
            for i in items:
                t.delete_item(Key={"kind": i["kind"], "ts": i["ts"]})
