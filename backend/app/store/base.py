"""
base.py — Abstract store interface for execution records.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseStore(ABC):
    @abstractmethod
    def save(self, execution_id: str, record: dict) -> None: ...

    @abstractmethod
    def get(self, execution_id: str) -> Optional[dict]: ...

    @abstractmethod
    def list_all(self, verification_status: Optional[list[str]] = None) -> list[dict]: ...
