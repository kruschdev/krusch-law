"""
KruschLaw Legal Semantic Chunk Tagger (tagger.py)
==================================================
Extracts structured legal taxonomy tags, 1-sentence micro-digests,
and doctrinal classifications for document chunks ingested through KruschNexus.

Mirrors krusch-git's semantic tagging agent, bridging the gap between
colloquial client evidence phrasing and formal statutory doctrine.
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional

import httpx

from .config import settings

logger = logging.getLogger("kruschlaw.tagger")

TAGGER_SYSTEM_PROMPT = """You are an expert legal knowledge architect specializing in California tenant and housing law.
Given a document chunk with its citation locator, output a JSON object with:
- "summary": A precise 1-sentence legal or factual micro-digest (max 140 chars) of what this chunk establishes.
- "tags": An array of 3-5 lowercase semantic tags (e.g. ["security-deposit", "ab-12", "statutory-cap", "trust-account"]).
- "doctrine": The primary legal doctrine (e.g. "Security Deposits", "Just Cause", "Habitability", "Rent Control", "Lease Terms", "Discovery Facts").

Rules:
- Never use filler phrases like "This excerpt discusses..." or "The document says..."
- Output ONLY valid raw JSON. No markdown fences, no backticks, no explanatory text.
"""

# Common legal taxonomy keywords for high-speed offline/heuristic fallback
DOCTRINE_PATTERNS = [
    (
        "Security Deposits",
        re.compile(r'\b(security\s+deposit|deposit|1950\.5|ab\s*12|itemized\s+accounting|trust\s+account|cleaning\s+fee|deduction)\b', re.IGNORECASE),
        ["security-deposit", "deposit-accounting", "statutory-limit"]
    ),
    (
        "Just Cause",
        re.compile(r'\b(just\s+cause|1946\.2|ab\s*1482|owner\s+(?:move-in|occupancy)|relocation\s+payment|notice\s+to\s+quit|at-fault|no-fault)\b', re.IGNORECASE),
        ["just-cause", "eviction-defense", "notice-to-quit"]
    ),
    (
        "Habitability",
        re.compile(r'\b(habitab|1941\.1|substandard|mold|waterproof|plumbing|hot\s+water|heating|weatherproof|infest)\b', re.IGNORECASE),
        ["habitability", "substandard-housing", "implied-warranty"]
    ),
    (
        "Rent Control",
        re.compile(r'\b(rent\s+(?:adjustment|increase|cap|board|stabilization)|8\.22|allowable\s+rent|cpi|banked\s+rent)\b', re.IGNORECASE),
        ["rent-control", "rent-increase", "ordinance-compliance"]
    ),
    (
        "Self-Help Eviction",
        re.compile(r'\b(lockout|lock\s+out|shut\s+off|789\.3|utility\s+shutoff|interruption\s+of\s+service)\b', re.IGNORECASE),
        ["self-help-eviction", "lockout", "statutory-penalty"]
    ),
    (
        "Lease Terms",
        re.compile(r'\b(lease|tenancy|agreement|covenant|premises|term\s+of\s+lease|tenant\s+shall|landlord\s+shall)\b', re.IGNORECASE),
        ["lease-terms", "contract-clause", "tenancy-rules"]
    )
]


def heuristic_tag_chunk(
    content: str,
    filename: str = "",
    locator: Optional[str] = None,
    doc_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Deterministic rule-based legal tagger for instant, zero-latency tagging.
    Serves as an offline fallback when Ollama is unavailable or in resource-constrained environments.
    """
    clean_text = content.strip()
    first_period = clean_text.find(".")
    if 0 < first_period < 140:
        summary = clean_text[:first_period + 1].strip()
    else:
        summary = (clean_text[:137] + "...").strip() if len(clean_text) > 140 else clean_text

    matched_doctrine = "General Matter Facts"
    matched_tags: List[str] = []

    text_to_scan = f"{filename} {locator or ''} {content}"
    for doctrine_name, pattern, default_tags in DOCTRINE_PATTERNS:
        if pattern.search(text_to_scan):
            matched_doctrine = doctrine_name
            matched_tags.extend(default_tags)
            break

    # Add doc_type tag if available
    if doc_type and doc_type not in ("general", "matter_facts"):
        matched_tags.append(doc_type.lower().replace("_", "-"))

    # Extract any statutory citation mentions
    sec_match = re.findall(r'(?:§+|Section)\s*([0-9A-Za-z\.\-]+)', content, re.IGNORECASE)
    for s in sec_match[:2]:
        matched_tags.append(f"sec-{s.lower()}")

    if not matched_tags:
        matched_tags = ["evidence", "matter-record"]

    # Deduplicate while preserving order, max 5 tags
    seen = set()
    deduped_tags = []
    for t in matched_tags:
        clean_tag = re.sub(r'[^a-z0-9\-]', '', t.lower().strip())
        if clean_tag and clean_tag not in seen:
            seen.add(clean_tag)
            deduped_tags.append(clean_tag)
            if len(deduped_tags) >= 5:
                break

    return {
        "summary": summary,
        "tags": deduped_tags,
        "doctrine": matched_doctrine
    }


def tag_chunk_with_llm(
    content: str,
    filename: str = "",
    locator: Optional[str] = None,
    doc_type: Optional[str] = None,
    timeout: Optional[float] = None
) -> Optional[Dict[str, Any]]:
    """
    Request structured legal tags, micro-digest summary, and doctrine from local Ollama.
    """
    to = timeout or float(getattr(settings, "TAGGER_TIMEOUT", 15.0))
    model = getattr(settings, "TAGGER_MODEL", getattr(settings, "OLLAMA_LLM_MODEL", "qwen2.5-coder:7b"))
    host = settings.OLLAMA_BASE_URL.rstrip("/")

    truncated_content = content[:3000]
    loc_info = f" (Locator: {locator})" if locator else ""
    user_prompt = f"Document: {filename}{loc_info}\nClassification: {doc_type or 'unspecified'}\n\nChunk Text:\n```\n{truncated_content}\n```"

    try:
        with httpx.Client(timeout=to) as client:
            resp = client.post(
                f"{host}/api/generate",
                json={
                    "model": model,
                    "system": TAGGER_SYSTEM_PROMPT,
                    "prompt": user_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 150,
                        "top_p": 0.9
                    }
                }
            )
            if resp.status_code != 200:
                logger.warning(f"Ollama tagger status {resp.status_code}: {resp.text[:100]}")
                return None

            data = resp.json()
            raw = (data.get("response") or "").strip()
            if not raw:
                return None

            # Clean JSON formatting
            cleaned = raw
            cleaned = re.sub(r'^```json?\s*', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s*```$', '', cleaned)
            last_brace = cleaned.lastIndexOf('}') if hasattr(cleaned, 'lastIndexOf') else cleaned.rfind('}')
            if last_brace > 0:
                cleaned = cleaned[:last_brace + 1]

            parsed = json.loads(cleaned)
            summary = str(parsed.get("summary") or "").strip()[:140]
            raw_tags = parsed.get("tags") or []
            doctrine = str(parsed.get("doctrine") or "").strip() or "General Matter Facts"

            if not summary or not isinstance(raw_tags, list):
                return None

            clean_tags = []
            for t in raw_tags[:5]:
                ct = re.sub(r'[^a-z0-9\-]', '', str(t).lower().strip())
                if ct and ct not in clean_tags:
                    clean_tags.append(ct)

            return {
                "summary": summary,
                "tags": clean_tags,
                "doctrine": doctrine
            }
    except Exception as e:
        logger.debug(f"LLM tagging unavailable or failed ({e}); falling back to heuristic tagger.")
        return None


def tag_legal_chunk(
    content: str,
    filename: str = "",
    locator: Optional[str] = None,
    doc_type: Optional[str] = None,
    use_llm: bool = True
) -> Dict[str, Any]:
    """
    Primary interface for legal chunk tagging.
    Attempts LLM tagging via local Ollama and falls back to deterministic heuristic tagging.
    """
    if use_llm:
        res = tag_chunk_with_llm(
            content=content,
            filename=filename,
            locator=locator,
            doc_type=doc_type
        )
        if res is not None and res.get("tags"):
            return res

    return heuristic_tag_chunk(
        content=content,
        filename=filename,
        locator=locator,
        doc_type=doc_type
    )
