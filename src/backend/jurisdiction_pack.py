"""
src/backend/jurisdiction_pack.py
================================
Jurisdiction Pack standard and loader for KruschLaw.
Formalizes state, municipal, and regulatory codes as versioned, reproducible data packages.

Enforces:
  1. Separation of canonical statutory source artifacts from rebuildable derived vectors.
  2. Provenance tracking: source URLs, retrieved-at timestamps, SHA-256 content hashes,
     official publishers, and legal editions.
  3. Explicit coverage modeling: Documents covered legal doctrines and known coverage holes
     so the system refuses to answer out-of-scope queries rather than hallucinating fuzzy neighbors.
"""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db import StatutoryArtifact, rebuild_vectors_from_artifacts


class StatuteFixture(BaseModel):
    """Authoritative statutory or ordinance text fixture with legal metadata."""
    citation: str = Field(..., description="Canonical legal citation (e.g., 'Cal. Civ. Code § 1950.5')")
    section_number: Optional[str] = Field(None, description="Section identifier (e.g., '1950.5' or '8.22.030')")
    title: str = Field(..., description="Official title of the statute or ordinance")
    topic: str = Field(..., description="Subject matter doctrine (e.g., 'Security Deposits', 'Just Cause')")
    authority_class: str = Field("controlling_statute", description="Hierarchy: controlling_statute, municipal_ordinance, etc.")
    hierarchy_level: str = Field("section", description="Hierarchy level: code, chapter, section, subsection")
    effective_date: Optional[str] = Field(None, description="ISO Date statute became enforceable (YYYY-MM-DD)")
    repeal_date: Optional[str] = Field(None, description="ISO Date statute was repealed/sunset (YYYY-MM-DD)")
    source_url: Optional[str] = Field(None, description="Official government or reporter source URL")
    publisher: Optional[str] = Field(None, description="Official publisher (e.g., 'California Office of Legislative Counsel')")
    edition: Optional[str] = Field(None, description="Official code supplement or legislative edition")
    raw_content: str = Field(..., description="Unabridged verbatim statutory content")
    statutory_slots: Dict[str, Any] = Field(default_factory=dict, description="Deterministic numeric and temporal terms")
    preempted_by: Optional[str] = Field(None, description="Citation of parent statute preempting this section")
    preempts: List[str] = Field(default_factory=list, description="Citations preempted by this section")
    defines_terms: List[str] = Field(default_factory=list, description="Operative legal definitions established")
    exceptions_ref: Optional[str] = Field(None, description="Reference to explicit statutory exception provision")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional custom metadata")


class ParserConfig(BaseModel):
    """Parsing and tokenization configuration for this jurisdiction's code style."""
    citation_pattern: Optional[str] = Field(None, description="Regex pattern matching valid sections")
    slot_extractors: List[str] = Field(default_factory=list, description="Active deterministic slot extractors")


class CoverageExpectation(BaseModel):
    """
    Explicit specification of what legal doctrines are covered by this pack,
    and which areas constitute known coverage holes.
    """
    covered_topics: List[str] = Field(..., description="Doctrines with authoritative provisions in this pack")
    known_uncovered_topics: List[str] = Field(
        default_factory=list,
        description="Doctrines intentionally NOT covered; system must return typed CoverageHole"
    )

    @property
    def uncovered_topics(self) -> List[str]:
        return self.known_uncovered_topics


class JurisdictionPack(BaseModel):
    """
    Self-contained, verifiable jurisdiction code package.
    Separates official source of truth from derived vector indices.
    """
    pack_id: str = Field(..., description="Unique pack identifier (e.g., 'ca_oakland_pack_v1')")
    version: str = Field("1.0.0", description="Semver version of the pack definition")
    state: str = Field("CA", description="Two-letter state postal code")
    municipality: Optional[str] = Field(None, description="City name if applicable (e.g., 'Oakland')")
    county: Optional[str] = Field(None, description="County name if applicable (e.g., 'Alameda County')")
    code_families: List[str] = Field(..., description="List of code families (e.g., ['California Civil Code', 'Oakland Municipal Code'])")
    description: str = Field(..., description="Human-readable overview of the jurisdiction pack")
    publisher: str = Field(..., description="Authoritative legislative publisher")
    edition: str = Field(..., description="Code edition or legislative session identifier")
    retrieved_at: Optional[str] = Field(None, description="ISO timestamp when statutory data was pulled")
    parser_config: Optional[ParserConfig] = Field(None, description="Jurisdiction-specific parser settings")
    coverage: CoverageExpectation = Field(..., description="Explicit coverage bounds and known holes")
    statutes: List[StatuteFixture] = Field(..., description="List of statutory and ordinance provisions")


def parse_iso_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO YYYY-MM-DD or full timestamp to timezone-aware UTC datetime."""
    if not date_str:
        return None
    try:
        if "T" in date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            parts = date_str.strip().split("-")
            dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]), tzinfo=timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def load_jurisdiction_pack(path_or_content: Union[str, Path, Dict[str, Any]]) -> JurisdictionPack:
    """
    Load and validate a JurisdictionPack from a YAML/JSON file path, YAML/JSON string, or dict.
    """
    data: Dict[str, Any]
    if isinstance(path_or_content, dict):
        data = path_or_content
    elif isinstance(path_or_content, (str, Path)):
        p = Path(path_or_content)
        if p.exists() and p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
            if p.suffix.lower() in (".yaml", ".yml"):
                data = yaml.safe_load(content)
            else:
                data = json.loads(content)
        else:
            # Try interpreting as raw YAML/JSON string
            raw_str = str(path_or_content).strip()
            if raw_str.startswith("{"):
                data = json.loads(raw_str)
            else:
                data = yaml.safe_load(raw_str)
    else:
        raise ValueError(f"Unsupported jurisdiction pack input type: {type(path_or_content)}")

    return JurisdictionPack.model_validate(data)


def import_jurisdiction_pack(
    pack: Union[JurisdictionPack, str, Path],
    db: Session,
    rebuild_vectors: bool = True
) -> Dict[str, Any]:
    """
    Import an authoritative JurisdictionPack into the database:
      1. Hashes every raw statute text (SHA-256) for deterministic deduplication.
      2. Persists canonical records into statutory_artifacts table (Source of Truth).
      3. Optionally triggers rebuild_vectors_from_artifacts to generate derived laws_vectors.
    """
    if isinstance(pack, (str, Path)):
        pack = load_jurisdiction_pack(pack)

    imported_count = 0
    now_utc = datetime.now(timezone.utc)
    retrieved_time = parse_iso_date(pack.retrieved_at) or now_utc

    for stat in pack.statutes:
        raw_text = stat.raw_content.strip()
        art_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

        # Check existing artifact
        existing = db.query(StatutoryArtifact).filter(
            StatutoryArtifact.artifact_hash == art_hash
        ).first()

        eff_date = parse_iso_date(stat.effective_date)
        rep_date = parse_iso_date(stat.repeal_date)

        metadata_dict = {
            "statutory_slots": stat.statutory_slots,
            "preempted_by": stat.preempted_by,
            "preempts": stat.preempts,
            "defines_terms": stat.defines_terms,
            "exceptions_ref": stat.exceptions_ref,
            "hierarchy_level": stat.hierarchy_level,
            "custom_metadata": stat.metadata
        }

        if existing:
            # Update fields
            existing.jurisdiction_pack_id = pack.pack_id
            existing.state = pack.state
            existing.municipality = pack.municipality
            existing.county = pack.county
            existing.code_family = pack.code_families[0] if pack.code_families else "Statutes"
            existing.citation = stat.citation
            existing.section_number = stat.section_number
            existing.title = stat.title
            existing.topic = stat.topic
            existing.authority_class = stat.authority_class
            existing.raw_content = raw_text
            existing.source_url = stat.source_url
            existing.publisher = stat.publisher or pack.publisher
            existing.edition = stat.edition or pack.edition
            existing.effective_date = eff_date
            existing.repeal_date = rep_date
            existing.metadata_json = json.dumps(metadata_dict)
            existing.updated_at = now_utc
        else:
            artifact = StatutoryArtifact(
                artifact_hash=art_hash,
                jurisdiction_pack_id=pack.pack_id,
                state=pack.state,
                municipality=pack.municipality,
                county=pack.county,
                code_family=pack.code_families[0] if pack.code_families else "Statutes",
                citation=stat.citation,
                section_number=stat.section_number,
                title=stat.title,
                topic=stat.topic,
                authority_class=stat.authority_class,
                raw_content=raw_text,
                source_url=stat.source_url,
                publisher=stat.publisher or pack.publisher,
                edition=stat.edition or pack.edition,
                effective_date=eff_date,
                repeal_date=rep_date,
                retrieved_at=retrieved_time,
                is_canonical=True,
                metadata_json=json.dumps(metadata_dict)
            )
            db.add(artifact)

        imported_count += 1

    db.commit()

    vectors_count = 0
    if rebuild_vectors:
        vectors_count = rebuild_vectors_from_artifacts(db, pack_id=pack.pack_id)

    return {
        "pack_id": pack.pack_id,
        "version": pack.version,
        "statutes_imported": imported_count,
        "artifacts_imported": imported_count,
        "vectors_rebuilt": vectors_count,
        "vectors_created": vectors_count,
        "covered_topics": pack.coverage.covered_topics,
        "known_uncovered_topics": pack.coverage.known_uncovered_topics
    }
