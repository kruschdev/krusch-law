"""
src/backend/nexus_rag.py
========================
KruschNexus RAG retrieval adapter for KruschLaw.
Provides zero vendor lock-in retrieval delegation to NexusClient:
- backend="local": PostgreSQL pgvector + Ollama bge-large
- backend="wondersearch": Wondersearch Cloud Drives (gated by ALLOW_CLOUD=1)
Preserves INV-11 Physical Citation Coordinates (bbox, page_number, char spans).
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List, Optional

from .config import settings

logger = logging.getLogger("kruschlaw.nexus_rag")

_NEXUS_AVAILABLE = False
_NEXUS_CLIENT = None


def _resolve_nexus():
    global _NEXUS_AVAILABLE
    try:
        import krusch_nexus  # noqa: F401
        _NEXUS_AVAILABLE = True
    except ImportError:
        candidate_paths = [
            getattr(settings, "KRUSCH_NEXUS_PATH", None),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "krusch-nexus", "src"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "krusch-nexus", "src"),
            "/nexus/src",
            os.path.expanduser("~/homelab/projects/krusch-nexus/src"),
        ]
        for p in candidate_paths:
            if p and os.path.isdir(p) and p not in sys.path:
                sys.path.insert(0, p)
                break
        try:
            import krusch_nexus  # noqa: F401
            _NEXUS_AVAILABLE = True
        except ImportError:
            _NEXUS_AVAILABLE = False


_resolve_nexus()


def is_nexus_available() -> bool:
    return _NEXUS_AVAILABLE


def get_nexus_client() -> Any:
    global _NEXUS_CLIENT
    if _NEXUS_CLIENT is not None:
        return _NEXUS_CLIENT
    if not is_nexus_available():
        return None
    from krusch_nexus import NexusClient, NexusConfig

    backend = os.getenv("NEXUS_BACKEND", "local").lower()
    allow_cloud = getattr(settings, "ALLOW_CLOUD", False) or os.getenv("ALLOW_CLOUD", "0") in ("1", "true", "True")
    if backend == "wondersearch" and not allow_cloud:
        from krusch_nexus.exceptions import AirGapViolationError
        raise AirGapViolationError(
            "Security Violation: KruschLaw refuses connection to cloud Wondersearch backend without ALLOW_CLOUD=1."
        )

    cfg = NexusConfig.from_env()
    _NEXUS_CLIENT = NexusClient(config=cfg)
    return _NEXUS_CLIENT


def search_laws_nexus(
    text_query: str,
    limit: int = 5,
    state_filter: Optional[str] = None,
    city_filter: Optional[str] = None,
    topic_filter: Optional[str] = None,
    as_of_date: Optional[Any] = None,
    workspace: str = "laws_california"
) -> List[Dict[str, Any]]:
    """Retrieve laws using KruschNexus / Wondersearch provider."""
    client = get_nexus_client()
    if not client:
        return []

    filters = {}
    if state_filter:
        filters["state"] = state_filter
    if city_filter:
        filters["city"] = city_filter
    if topic_filter:
        filters["topic"] = topic_filter

    hits = client.search(
        query=text_query,
        workspace=workspace,
        limit=limit,
        filters=filters if filters else None
    )

    results = []
    for hit in hits:
        meta = hit.score_vector or {}
        section_name = hit.locator or hit.header or "§ General"
        title_name = hit.citation or hit.header or "Statutory Provision"
        results.append({
            "id": hit.chunk_id,
            "jurisdiction": meta.get("jurisdiction", "California"),
            "state": meta.get("state", state_filter or "CA"),
            "city": meta.get("city", city_filter),
            "county": meta.get("county"),
            "city_or_county": meta.get("city_or_county", city_filter),
            "topic": meta.get("topic", topic_filter or "General"),
            "title": title_name,
            "section": section_name,
            "content": hit.text,
            "chunk_index": hit.chunk_index or 0,
            "parent_section": meta.get("parent_section"),
            "hierarchy_level": meta.get("hierarchy_level", 1),
            "authority_class": meta.get("authority_class", "controlling_statute"),
            "instrument_type": meta.get("instrument_type", "statute"),
            "status": meta.get("status", "enacted"),
            "effective_from": meta.get("effective_from"),
            "effective_to": meta.get("effective_to"),
            "preempts": meta.get("preempts"),
            "implements_ref": meta.get("implements_ref"),
            "defines_terms": meta.get("defines_terms"),
            "exception_to": meta.get("exception_to"),
            "applies_if": meta.get("applies_if"),
            "definitions_ref": meta.get("definitions_ref"),
            "exceptions_ref": meta.get("exceptions_ref"),
            "repealed": meta.get("repealed", False),
            "preempted_by": meta.get("preempted_by"),
            "effective_date": meta.get("effective_date"),
            "source_url": meta.get("source_url"),
            "page_number": hit.page_number,
            "printed_page": hit.printed_page,
            "bbox": hit.bbox,
            "char_start": hit.char_start,
            "char_end": hit.char_end,
            "extra_metadata": meta.get("extra_metadata"),
            "similarity": float(hit.score)
        })
    return results


def search_matter_evidence_nexus(
    matter_id: int,
    text_query: Optional[str] = None,
    limit: int = 5,
    doc_type: Optional[str] = None,
    doctrine: Optional[str] = None,
    tag: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieve matter discovery documents using KruschNexus / Wondersearch provider."""
    client = get_nexus_client()
    if not client:
        return []

    workspace = f"matter_{matter_id}"
    filters = {}
    if doc_type:
        filters["doc_type"] = doc_type
    if doctrine:
        filters["doctrine"] = doctrine

    hits = client.search(
        query=text_query or "*",
        workspace=workspace,
        limit=limit,
        filters=filters if filters else None
    )

    results = []
    for hit in hits:
        meta = hit.score_vector or {}
        tags_list = meta.get("tags", [])
        if isinstance(tags_list, str):
            tags_list = [t.strip() for t in tags_list.split(",") if t.strip()]

        results.append({
            "id": hit.chunk_id,
            "matter_id": matter_id,
            "filename": hit.filename or meta.get("filename", "document"),
            "doc_type": hit.doc_type or meta.get("doc_type", doc_type or "general"),
            "page_number": hit.page_number,
            "printed_page": hit.printed_page,
            "section_locator": hit.locator or hit.header or "General",
            "chunk_index": hit.chunk_index or 0,
            "content": hit.text,
            "tags": tags_list,
            "summary": meta.get("summary"),
            "doctrine": meta.get("doctrine", doctrine),
            "bbox": hit.bbox,
            "char_start": hit.char_start,
            "char_end": hit.char_end,
            "extra_metadata": meta.get("extra_metadata"),
            "similarity": round(float(hit.score), 4),
            "created_at": meta.get("created_at")
        })
    return results
