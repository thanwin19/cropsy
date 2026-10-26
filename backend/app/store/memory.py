"""
memory.py — In-memory execution store (thread-safe for single-process use).
Stores Phase7AdvisoryResult as dicts, keyed by execution_id.
"""
from __future__ import annotations

import threading
from typing import Optional

from app.store.base import BaseStore


class MemoryStore(BaseStore):
    def __init__(self):
        self._store: dict[str, dict] = {}
        self._lock = threading.Lock()

    def save(self, execution_id: str, record: dict) -> None:
        with self._lock:
            self._store[execution_id] = record

    def get(self, execution_id: str) -> Optional[dict]:
        with self._lock:
            return self._store.get(execution_id)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def list_all(self, verification_status: Optional[list[str]] = None) -> list[dict]:
        with self._lock:
            records = list(self._store.values())
        if verification_status:
            records = [
                r for r in records
                if (r.get("verification", {}) or {}).get("status") in verification_status
                or r.get("verification_status") in verification_status
            ]
        # Most recent first
        return sorted(records, key=lambda r: r.get("created_at", ""), reverse=True)


# Singleton
_store = MemoryStore()


_dynamo = None


def get_store():
    """In-memory history by default; DynamoDB when CROPSY_STORE=aws."""
    global _dynamo
    from app import aws_resources
    if aws_resources.enabled():
        if _dynamo is None:
            from app.store.dynamo import DynamoStore
            _dynamo = DynamoStore()
        return _dynamo
    return _store
