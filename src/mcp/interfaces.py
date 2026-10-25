"""
src/mcp/interfaces.py
=====================
Service protocol abstractions and default bindings for the KruschLaw MCP Gateway.
Decouples `src/mcp/gateway.py` from direct low-level `src.backend.*` imports (ARCH-01).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

from src.backend import db as db_mod
from src.backend.crypto import execute_verifiable_purge
from src.backend.db import LawVector
from src.backend.rag import retrieve_laws
from src.backend.resolver import resolve_controlling_law


class RagServiceProtocol(Protocol):
    def __call__(
        self,
        query: str,
        db: Any,
        top_k: int = 5,
        jurisdiction: Optional[str] = None,
        topic: Optional[str] = None,
        as_of_date: Optional[Any] = None,
    ) -> List[Any]: ...


class ResolverServiceProtocol(Protocol):
    def __call__(
        self,
        topic: str,
        jurisdiction: str,
        db: Any,
        as_of_date: Optional[Any] = None,
    ) -> Dict[str, Any]: ...


class CryptoPurgeServiceProtocol(Protocol):
    def __call__(
        self,
        db: Any,
        target_type: str,
        target_id: str,
        reason: str,
    ) -> Dict[str, Any]: ...


__all__ = [
    "RagServiceProtocol",
    "ResolverServiceProtocol",
    "CryptoPurgeServiceProtocol",
    "db_mod",
    "LawVector",
    "execute_verifiable_purge",
    "retrieve_laws",
    "resolve_controlling_law",
]
