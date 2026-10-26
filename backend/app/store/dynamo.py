"""dynamo.py: execution history in DynamoDB (table <prefix>-executions, key execution_id). The record is kept whole as a JSON string."""
from __future__ import annotations

import json
from typing import Optional

from app import aws_resources as aws
from app.store.base import BaseStore


class DynamoStore(BaseStore):
    def __init__(self):
        self._t = None

    @property
    def table(self):
        if self._t is None:
            self._t = aws.dynamo().Table(aws.EXECUTIONS_TABLE)
        return self._t

    def save(self, execution_id: str, record: dict) -> None:
        status = (record.get("verification") or {}).get("status") or record.get("verification_status") or "pass"
        self.table.put_item(Item={"execution_id": execution_id, "created_at": record.get("created_at", ""), "verification_status": status,
                                  "record": json.dumps(record, ensure_ascii=False, default=str)})

    def get(self, execution_id: str) -> Optional[dict]:
        it = self.table.get_item(Key={"execution_id": execution_id}).get("Item")
        return json.loads(it["record"]) if it else None

    def _scan(self) -> list[dict]:
        out, kw = [], {}
        while True:
            r = self.table.scan(**kw)
            out += r.get("Items", [])
            if "LastEvaluatedKey" not in r:
                return out
            kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]

    def list_all(self, verification_status: Optional[list[str]] = None) -> list[dict]:
        items = self._scan()
        if verification_status:
            items = [i for i in items if i.get("verification_status") in verification_status]
        items.sort(key=lambda i: i.get("created_at", ""), reverse=True)
        return [json.loads(i["record"]) for i in items]

    def clear(self) -> None:
        for i in self._scan():
            self.table.delete_item(Key={"execution_id": i["execution_id"]})
