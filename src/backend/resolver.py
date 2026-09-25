"""
src/backend/resolver.py
=======================
Controlling Legal Authority & Statutory Precedence Graph Resolver for KruschLaw.
Engineered specifically for corporate counsel, legal aid attorneys, and judicial review.

Implements a true multi-hop Directed Acyclic Graph (DAG) walk across statutory authorities:
  - PREEMPTS / PREEMPTED_BY: Statewide and federal preemption over municipal/county ordinances
    (e.g., Costa-Hawkins Cal. Civ. Code § 1954.50+, Tenant Protection Act § 1946.2, AB 12 § 1950.5(c))
  - AMENDS / AMENDED_BY: Chronological legislative amendments with effective-date gating
  - SUPERSEDES / REPEALS: Formal legislative repeals and statutory sunsets
  - EXEMPTS_FROM / EXCEPTION_TO: Specific statutory exemptions overriding general rules (Lex specialis)
  - DEFINES / DEFINITIONS_REF: Operative statutory definitions binding substantive sections
  - IMPLEMENTS: Municipal ordinances and administrative regulations implementing parent state codes
  - CARVES_OUT: Local ordinance standards permitted where state statute establishes a floor

Features:
  - Pure UTC date comparisons for exact historical analysis (incident date vs enactment date)
  - Cycle detection (depth cap 32, visited set)
  - Multi-hop preemption & amendment traversal
  - Deterministic statutory slot comparison
  - Statutory & municipal conflict detection
"""

from __future__ import annotations

import re
import json
import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .db import LawVector, SessionLocal

logger = logging.getLogger("kruschlaw.resolver")

# Canonical legal hierarchy ranks (lower number = higher legal precedence)
AUTHORITY_RANKS = {
    "constitutional": 1,
    "controlling_statute": 2,
    "implementing_regulation": 3,
    "municipal_ordinance": 4,
    "secondary_commentary": 5,
}

# Known statewide California preemption statutes and doctrines
STATEWIDE_PREEMPTION_REGISTRY = {
    "costa_hawkins": {
        "statute": "Cal. Civ. Code § 1954.50 et seq.",
        "doctrine": "Rent Control Preemption",
        "description": "Preempts municipal rent control on single-family homes, condos, and post-Feb 1, 1995 construction.",
        "preempts_municipal": True,
        "keywords": ["single-family", "condo", "post-1995", "new construction", "vacancy decontrol"]
    },
    "ab_12": {
        "statute": "Cal. Civ. Code § 1950.5(c) (Stats. 2023, ch. 290)",
        "effective_date": date(2024, 7, 1),
        "doctrine": "Security Deposit Cap",
        "description": "Caps residential security deposits at 1 month rent statewide regardless of furnished status (with small-landlord 2-unit exception).",
        "preempts_municipal": True,
        "keywords": ["security deposit", "deposit cap", "ab 12", "1 month rent", "two months"]
    },
    "ab_1482": {
        "statute": "Cal. Civ. Code § 1946.2 & § 1947.12",
        "effective_date": date(2020, 1, 1),
        "doctrine": "Just Cause & Rent Increase Caps",
        "description": "Statewide Just Cause eviction rules and 5% + CPI rent cap; sets floor but preserves stricter local just cause.",
        "preempts_municipal": False,  # Sets floor; more protective local laws survive
        "keywords": ["just cause", "owner move-in", "rent increase cap", "cpi", "no-fault eviction"]
    },
    "ellis_act": {
        "statute": "Cal. Gov. Code § 7060 et seq.",
        "doctrine": "Rental Business Withdrawal",
        "description": "Preempts local municipalities from compelling landlords to remain in the rental business.",
        "preempts_municipal": True,
        "keywords": ["ellis act", "withdraw from rental market", "going out of business"]
    }
}


def to_utc_date(val: Any) -> date:
    """Normalize input date, datetime, or ISO string to UTC date-only."""
    if val is None:
        return datetime.now(timezone.utc).date()
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        if val.tzinfo is None:
            val = val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc).date()
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).date()
        except Exception:
            try:
                # Try simple YYYY-MM-DD
                parts = val.strip().split("T")[0].split("-")
                if len(parts) == 3:
                    return date(int(parts[0]), int(parts[1]), int(parts[2]))
            except Exception:
                pass
    return datetime.now(timezone.utc).date()


def normalize_statutory_citation(cite: Optional[str]) -> str:
    """Normalize statutory citation string into canonical format for graph indexing."""
    if not cite:
        return ""
    cleaned = cite.strip()
    cleaned = re.sub(r'^(Section|Sec\.?|§+)\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()


class LawNode(BaseModel):
    """Strongly typed legal authority node."""
    id: Optional[int] = None
    section: Optional[str] = None
    citation: Optional[str] = None
    title: Optional[str] = None
    topic: Optional[str] = None
    jurisdiction: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    county: Optional[str] = None
    authority_class: Optional[str] = None
    effective_date: Optional[str] = None
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    status: Optional[str] = None
    repealed: bool = False
    content: Optional[str] = None
    source_url: Optional[str] = None


class ResolutionHop(BaseModel):
    """Individual step in the statutory authority resolution graph walk."""
    step: int
    hop_type: str = Field(..., description="PREEMPTION, AMENDMENT, EXCEPTION, SPATIAL_FILTER, TEMPORAL_LOOKBACK, TERMINAL, COVERAGE_CHECK")
    from_node: Optional[str] = None
    to_node: Optional[str] = None
    action: str = Field(..., description="FOLLOW_PREEMPTION, FOLLOW_AMENDMENT, HISTORICAL_LOOKBACK, EXCEPTION_APPLIED, TERMINAL_CONTROLLING_NODE, COVERAGE_HOLE, FILTER_OUT")
    decision: str = Field("KEPT", description="KEPT, DISCARDED, OVERRIDDEN, SUPERSEDED, NOT_YET_ENACTED, REPEALED, COVERAGE_HOLE")
    reason: str = Field(..., description="Explicit rationale for this hop or discard decision")
    as_of_date: str


class CoverageHole(BaseModel):
    """Explicit, first-class result indicating an absent legal authority."""
    topic: str
    jurisdiction: str
    as_of_date: str
    searched_criteria: Dict[str, Any] = Field(default_factory=dict)
    reason: str = "No controlling section found in authoritative corpus for this topic and jurisdiction."
    fallback_neighbors_suppressed: bool = True
    is_coverage_hole: bool = True

    @property
    def doctrine(self) -> str:
        return self.topic


class DiscardedCandidate(BaseModel):
    """Candidate authority node considered and discarded with documented rationale."""
    node_id: Optional[int] = None
    citation: str
    title: Optional[str] = None
    reason: str
    category: str  # PREEMPTED, NOT_YET_ENACTED, REPEALED, SUPERSEDED, SPATIAL_MISMATCH, LOWER_AUTHORITY_RANK


class ResolutionTrace(BaseModel):
    """Complete provenance and audit trail for a controlling law resolution."""
    as_of_date: str
    query_topic: str
    jurisdiction: str
    city: Optional[str] = None
    county: Optional[str] = None
    controlling_node: Optional[LawNode] = None
    governing_citation: str
    hops: List[ResolutionHop] = Field(default_factory=list)
    discarded_nodes: List[DiscardedCandidate] = Field(default_factory=list)
    coverage_hole: Optional[CoverageHole] = None
    active_exceptions: List[Dict[str, Any]] = Field(default_factory=list)
    mandatory_definitions: List[Dict[str, Any]] = Field(default_factory=list)
    statutory_slots: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = 1.0
    notes: str = ""


class LegalResolution:
    """
    Structured result of a multi-hop controlling legal authority resolution.
    Provides complete provenance, derivation chain, and quantitative terms for attorneys.
    Backed by strongly typed Pydantic ResolutionTrace and explicit CoverageHole models.
    """
    def __init__(
        self,
        controlling_node: Optional[Union[Dict[str, Any], LawNode]],
        governing_citation: str,
        topic: str,
        jurisdiction: str,
        as_of_date: date,
        precedence_chain: List[Dict[str, Any]],
        active_exceptions: List[Dict[str, Any]],
        mandatory_definitions: List[Dict[str, Any]],
        statutory_slots: Dict[str, Any],
        confidence_score: float = 1.0,
        notes: Optional[str] = None,
        trace: Optional[ResolutionTrace] = None,
        coverage_hole: Optional[CoverageHole] = None,
        discarded_nodes: Optional[List[Union[Dict[str, Any], DiscardedCandidate]]] = None,
        unconfirmed_proposals: Optional[List[Dict[str, Any]]] = None,
        uncertainty_warning: Optional[str] = None
    ):
        if isinstance(controlling_node, LawNode):
            self.controlling_node = controlling_node.model_dump()
        else:
            self.controlling_node = controlling_node

        self.governing_citation = governing_citation
        self.topic = topic
        self.jurisdiction = jurisdiction
        self.as_of_date = as_of_date
        self.precedence_chain = precedence_chain
        self.active_exceptions = active_exceptions
        self.mandatory_definitions = mandatory_definitions
        self.statutory_slots = statutory_slots
        self.confidence_score = confidence_score
        self.notes = notes or ""
        self.trace = trace
        self.coverage_hole = coverage_hole
        self.discarded_nodes = discarded_nodes or []
        self.unconfirmed_proposals = unconfirmed_proposals or []
        self.uncertainty_warning = uncertainty_warning

    @property
    def is_coverage_hole(self) -> bool:
        return self.coverage_hole is not None or "COVERAGE_HOLE" in self.governing_citation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "controlling_node": self.controlling_node,
            "governing_citation": self.governing_citation,
            "topic": self.topic,
            "jurisdiction": self.jurisdiction,
            "as_of_date": self.as_of_date.isoformat(),
            "precedence_chain": self.precedence_chain,
            "active_exceptions": self.active_exceptions,
            "mandatory_definitions": self.mandatory_definitions,
            "statutory_slots": self.statutory_slots,
            "confidence_score": round(self.confidence_score, 3),
            "notes": self.notes,
            "trace": self.trace.model_dump() if self.trace else None,
            "coverage_hole": self.coverage_hole.model_dump() if self.coverage_hole else None,
            "unconfirmed_proposals": self.unconfirmed_proposals,
            "uncertainty_warning": self.uncertainty_warning,
            "discarded_nodes": [
                d.model_dump() if isinstance(d, BaseModel) else d
                for d in self.discarded_nodes
            ]
        }


def resolve_controlling_law(
    doctrine_or_topic: str,
    jurisdiction: Optional[str] = None,
    city: Optional[str] = None,
    county: Optional[str] = None,
    as_of_date: Optional[Any] = None,
    matter_facts: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
    depth_cap: int = 32
) -> LegalResolution:
    """
    Multi-hop Legal Authority Graph Walker:
    Recursively resolves controlling law as of `as_of_date` by traversing:
      1. Spatial / Territorial gates (Unincorporated vs Municipal boundaries).
      2. Express Preemption chains (Municipal code -> State statute).
      3. Legislative Amendment chains (Older enacted node -> Newer amendment node as of effective date).
      4. Statutory Exception nodes (Evaluating client fact patterns against statutory carve-outs).
      5. Operative Definitions hydration.
    """
    target_date = to_utc_date(as_of_date)
    matter_facts = matter_facts or {}
    close_db = False

    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Step 1: Query initial candidate nodes from database
        query = db.query(LawVector).filter(
            or_(
                LawVector.topic.ilike(f"%{doctrine_or_topic}%"),
                LawVector.title.ilike(f"%{doctrine_or_topic}%"),
                LawVector.tags.ilike(f"%{doctrine_or_topic}%"),
                LawVector.content.ilike(f"%{doctrine_or_topic}%")
            )
        )

        if city:
            query = query.filter(
                or_(
                    LawVector.city.ilike(city),
                    LawVector.city_or_county.ilike(city),
                    LawVector.jurisdiction.ilike(f"%{city}%"),
                    LawVector.jurisdiction.ilike("%California%")
                )
            )
        elif county:
            query = query.filter(
                or_(
                    LawVector.county.ilike(county),
                    LawVector.jurisdiction.ilike(f"%{county}%"),
                    LawVector.jurisdiction.ilike("%California%")
                )
            )

        candidates = query.all()
        if not candidates:
            # Fallback search across California state statutes
            candidates = db.query(LawVector).filter(
                or_(
                    LawVector.topic.ilike(f"%{doctrine_or_topic}%"),
                    LawVector.content.ilike(f"%{doctrine_or_topic}%")
                )
            ).limit(10).all()

        hops: List[ResolutionHop] = []
        discarded_candidates: List[DiscardedCandidate] = []

        # Check for unconfirmed proposed relations for this topic/doctrine
        unconfirmed_proposals = []
        try:
            from .db import StatuteRelation
            proposed_rels = db.query(StatuteRelation).filter(
                StatuteRelation.status == "proposed",
                or_(
                    StatuteRelation.scope_topic.ilike(f"%{doctrine_or_topic}%"),
                    StatuteRelation.source_statute.ilike(f"%{doctrine_or_topic}%"),
                    StatuteRelation.target_statute.ilike(f"%{doctrine_or_topic}%")
                )
            ).all()
            for rel in proposed_rels:
                unconfirmed_proposals.append({
                    "id": rel.id,
                    "source_statute": rel.source_statute,
                    "target_statute": rel.target_statute,
                    "relation_type": rel.relation_type,
                    "scope_topic": rel.scope_topic,
                    "confidence": rel.confidence,
                    "trigger_span": rel.trigger_span,
                    "rationale": rel.rationale
                })
        except Exception:
            pass

        uncertainty_warning = None
        if unconfirmed_proposals:
            uncertainty_warning = (
                f"> ⚠️ **CONTROLLING STATUTE UNCERTAIN; "
                f"{len(unconfirmed_proposals)} proposed preemption/amendment link(s) pending human attorney review.**"
            )

        if not candidates:
            cov_hole = CoverageHole(
                topic=doctrine_or_topic,
                jurisdiction=jurisdiction or city or "California",
                as_of_date=target_date.isoformat(),
                searched_criteria={"doctrine_or_topic": doctrine_or_topic, "city": city, "county": county},
                reason=f"No controlling section found in authoritative corpus for '{doctrine_or_topic}' in {jurisdiction or city or 'California'} as of {target_date.isoformat()}.",
                fallback_neighbors_suppressed=True
            )
            hops.append(ResolutionHop(
                step=1,
                hop_type="COVERAGE_CHECK",
                from_node=None,
                to_node=None,
                action="COVERAGE_HOLE",
                decision="COVERAGE_HOLE",
                reason=f"Zero matching statutory sections found for '{doctrine_or_topic}' in {jurisdiction or city or 'California'}",
                as_of_date=target_date.isoformat()
            ))
            trace = ResolutionTrace(
                as_of_date=target_date.isoformat(),
                query_topic=doctrine_or_topic,
                jurisdiction=jurisdiction or city or "California",
                city=city,
                county=county,
                controlling_node=None,
                governing_citation="No authority found in corpus",
                hops=hops,
                discarded_nodes=discarded_candidates,
                coverage_hole=cov_hole,
                confidence_score=0.0,
                notes="Explicit coverage hole detected. Suppressed weak semantic vector neighbor."
            )
            return LegalResolution(
                controlling_node=None,
                governing_citation="No authority found in corpus",
                topic=doctrine_or_topic,
                jurisdiction=jurisdiction or city or "California",
                as_of_date=target_date,
                precedence_chain=[],
                active_exceptions=[],
                mandatory_definitions=[],
                statutory_slots={},
                confidence_score=0.0,
                notes="Zero candidate nodes found for doctrine/jurisdiction in local law store.",
                trace=trace,
                coverage_hole=cov_hole,
                discarded_nodes=discarded_candidates,
                unconfirmed_proposals=unconfirmed_proposals,
                uncertainty_warning=uncertainty_warning
            )

        # Step 2: Filter spatial applicability (unincorporated vs incorporated)
        is_unincorporated = bool(matter_facts.get("unincorporated", False))
        fact_city = matter_facts.get("city") or city

        spatially_valid = []
        for cand in candidates:
            applies_if_raw = cand.applies_if
            discard_reason = None
            if applies_if_raw:
                try:
                    conds = json.loads(applies_if_raw) if isinstance(applies_if_raw, str) else applies_if_raw
                    if "unincorporated" in conds:
                        if is_unincorporated and conds["unincorporated"] is False:
                            discard_reason = "Excluded by spatial filter: jurisdiction requires incorporated parcel"
                        if not is_unincorporated and conds["unincorporated"] is True:
                            discard_reason = "Excluded by spatial filter: jurisdiction requires unincorporated parcel"
                    if "city" in conds and fact_city:
                        if conds["city"].lower() != fact_city.lower():
                            discard_reason = f"Excluded by spatial filter: applies to {conds['city']}, not {fact_city}"
                except Exception:
                    pass

            if discard_reason:
                discarded_candidates.append(DiscardedCandidate(
                    node_id=cand.id,
                    citation=cand.section or "Unknown Section",
                    title=cand.title,
                    reason=discard_reason,
                    category="SPATIAL_MISMATCH"
                ))
                hops.append(ResolutionHop(
                    step=len(hops) + 1,
                    hop_type="SPATIAL_FILTER",
                    from_node=cand.section,
                    to_node=None,
                    action="FILTER_OUT",
                    decision="DISCARDED",
                    reason=discard_reason,
                    as_of_date=target_date.isoformat()
                ))
            else:
                spatially_valid.append(cand)

        if not spatially_valid:
            spatially_valid = candidates

        # Step 3: Sort by initial authority class rank (controlling_statute > municipal_ordinance)
        def get_rank(item: LawVector) -> int:
            cls = (item.authority_class or "").lower()
            return AUTHORITY_RANKS.get(cls, 4)

        spatially_valid.sort(key=get_rank)

        # Pick primary candidate to start graph walk
        current_node = spatially_valid[0]
        visited: Set[int] = set()
        precedence_chain: List[Dict[str, Any]] = []
        active_exceptions: List[Dict[str, Any]] = []
        mandatory_definitions: List[Dict[str, Any]] = []
        steps = 0

        # Step 4: Recursive Graph Traversal across Preemption & Amendment edges
        while current_node and steps < depth_cap:
            steps += 1
            node_id = current_node.id
            if node_id in visited:
                logger.warning(f"Cycle detected in statutory graph at node ID {node_id}")
                break
            visited.add(node_id)

            chain_step = {
                "step": steps,
                "node_id": current_node.id,
                "section": current_node.section,
                "title": current_node.title,
                "jurisdiction": current_node.jurisdiction,
                "authority_class": current_node.authority_class,
                "effective_date": current_node.effective_date.isoformat() if current_node.effective_date else None,
                "status": current_node.status
            }

            # Check 4A: Preemption Edge (State law preempts Municipal Ordinance)
            preempted_by = current_node.preempted_by
            if preempted_by:
                chain_step["action"] = "FOLLOW_PREEMPTION"
                chain_step["preempted_by"] = preempted_by
                precedence_chain.append(chain_step)

                discarded_candidates.append(DiscardedCandidate(
                    node_id=current_node.id,
                    citation=current_node.section or "Unknown",
                    title=current_node.title,
                    reason=f"Municipal ordinance preempted by statewide statute {preempted_by}",
                    category="PREEMPTED"
                ))
                hops.append(ResolutionHop(
                    step=steps,
                    hop_type="PREEMPTION",
                    from_node=current_node.section,
                    to_node=preempted_by,
                    action="FOLLOW_PREEMPTION",
                    decision="PREEMPTED",
                    reason=f"{current_node.section} is preempted by statewide statute {preempted_by}",
                    as_of_date=target_date.isoformat()
                ))

                # Find the preempting state statute in DB
                clean_target = re.sub(r'[^0-9\.]', '', preempted_by)
                preempting_node = None
                if clean_target:
                    preempting_node = db.query(LawVector).filter(
                        LawVector.section.ilike(f"%{clean_target}%"),
                        LawVector.authority_class == "controlling_statute"
                    ).first()

                if not preempting_node:
                    # Match by doctrine or text in preemption string
                    for key, preg in STATEWIDE_PREEMPTION_REGISTRY.items():
                        if any(kw in preempted_by.lower() for kw in preg["keywords"]):
                            preempting_node = db.query(LawVector).filter(
                                LawVector.authority_class == "controlling_statute",
                                or_(
                                    LawVector.content.ilike(f"%{key}%"),
                                    LawVector.title.ilike(f"%{key}%")
                                )
                            ).first()
                            break

                if preempting_node and preempting_node.id not in visited:
                    current_node = preempting_node
                    continue
                else:
                    # If preempting node not found as explicit entity, record in chain and break
                    break

            # Check 4B: Amendment Edge (Older node -> Newer enacted amendment)
            next_amendment = None
            if current_node.superseded_by_id:
                cand_next = db.query(LawVector).filter(LawVector.id == current_node.superseded_by_id).first()
                if cand_next:
                    eff_from = to_utc_date(cand_next.effective_from or cand_next.effective_date)
                    if eff_from <= target_date:
                        next_amendment = cand_next

            # Also check if current node is marked 'amended' or 'repealed' and a newer live version exists
            if not next_amendment and (current_node.status in ("amended", "repealed") or current_node.repealed):
                newer_nodes = db.query(LawVector).filter(
                    LawVector.jurisdiction == current_node.jurisdiction,
                    LawVector.section == current_node.section,
                    LawVector.status == "enacted",
                    LawVector.id != current_node.id
                ).all()
                for n in newer_nodes:
                    n_eff = to_utc_date(n.effective_from or n.effective_date)
                    if n_eff <= target_date:
                        next_amendment = n
                        break

            if next_amendment and next_amendment.id not in visited:
                chain_step["action"] = "FOLLOW_AMENDMENT"
                chain_step["superseded_by_id"] = next_amendment.id
                precedence_chain.append(chain_step)

                eff_str = next_amendment.effective_date.isoformat() if next_amendment.effective_date else "effective date"
                discarded_candidates.append(DiscardedCandidate(
                    node_id=current_node.id,
                    citation=current_node.section or "Unknown",
                    title=current_node.title,
                    reason=f"Superseded by legislative amendment {next_amendment.section} effective {eff_str}",
                    category="SUPERSEDED"
                ))
                hops.append(ResolutionHop(
                    step=steps,
                    hop_type="AMENDMENT",
                    from_node=current_node.section,
                    to_node=next_amendment.section,
                    action="FOLLOW_AMENDMENT",
                    decision="SUPERSEDED",
                    reason=f"Superseded by newer legislative amendment {next_amendment.section} as of {target_date.isoformat()}",
                    as_of_date=target_date.isoformat()
                ))
                current_node = next_amendment
                continue

            # Check 4C: If current node has effective_from in the future relative to target_date,
            # we need the prior historical version for this incident date!
            node_eff = to_utc_date(current_node.effective_from or current_node.effective_date)
            if node_eff > target_date:
                prior_node = db.query(LawVector).filter(
                    LawVector.jurisdiction == current_node.jurisdiction,
                    LawVector.section == current_node.section,
                    LawVector.id != current_node.id
                ).first()
                if prior_node and prior_node.id not in visited:
                    chain_step["action"] = "HISTORICAL_LOOKBACK"
                    chain_step["prior_node_id"] = prior_node.id
                    precedence_chain.append(chain_step)

                    discarded_candidates.append(DiscardedCandidate(
                        node_id=current_node.id,
                        citation=current_node.section or "Unknown",
                        title=current_node.title,
                        reason=f"Enacted on {node_eff.isoformat()} which is after incident date {target_date.isoformat()}",
                        category="NOT_YET_ENACTED"
                    ))
                    hops.append(ResolutionHop(
                        step=steps,
                        hop_type="TEMPORAL_LOOKBACK",
                        from_node=current_node.section,
                        to_node=prior_node.section,
                        action="HISTORICAL_LOOKBACK",
                        decision="NOT_YET_ENACTED",
                        reason=f"Modern amendment not yet in force as of {target_date.isoformat()}; rolled back to prior enacted law",
                        as_of_date=target_date.isoformat()
                    ))
                    current_node = prior_node
                    continue

            # Terminal node reached
            chain_step["action"] = "TERMINAL_CONTROLLING_NODE"
            precedence_chain.append(chain_step)
            hops.append(ResolutionHop(
                step=steps,
                hop_type="TERMINAL",
                from_node=current_node.section,
                to_node=current_node.section,
                action="TERMINAL_CONTROLLING_NODE",
                decision="KEPT",
                reason=f"Controlling legal authority confirmed as of {target_date.isoformat()}",
                as_of_date=target_date.isoformat()
            ))
            break

        # Step 5: Gather Mandatory Definitions along active path
        if current_node.definitions_ref or current_node.defines_terms:
            def_ref = current_node.definitions_ref or current_node.defines_terms
            def_node = db.query(LawVector).filter(
                LawVector.jurisdiction == current_node.jurisdiction,
                or_(
                    LawVector.section == def_ref,
                    LawVector.section == f"Section {def_ref}",
                    LawVector.section.ilike(f"%{def_ref}%")
                )
            ).first()
            if def_node:
                mandatory_definitions.append({
                    "id": def_node.id,
                    "section": def_node.section,
                    "title": def_node.title,
                    "content": def_node.content
                })

        # Step 6: Evaluate Statutory Exceptions & Carve-Outs against matter facts
        exc_ref = current_node.exceptions_ref or current_node.exception_to
        if exc_ref or current_node.section:
            # Query child exception nodes
            exc_nodes = db.query(LawVector).filter(
                or_(
                    LawVector.exception_to == current_node.section,
                    LawVector.parent_section == current_node.section,
                    LawVector.hierarchy_level == "exceptions"
                )
            ).all()

            for exc in exc_nodes:
                exc_content = (exc.content or "").lower()
                is_triggered = False

                # Owner-occupied duplex exemption (§ 1946.2(e))
                if ("owner-occupied" in exc_content or "duplex" in exc_content) and matter_facts.get("owner_occupied_duplex"):
                    is_triggered = True

                # Single-family dwelling exemption
                if ("single-family" in exc_content or "alienable" in exc_content) and matter_facts.get("single_family"):
                    is_triggered = True

                # New construction 15-year rolling exemption
                if ("15 years" in exc_content or "certificate of occupancy" in exc_content) and matter_facts.get("new_construction"):
                    is_triggered = True

                # Small landlord exception (AB 12 / 2-unit maximum)
                if ("two or fewer" in exc_content or "natural person" in exc_content) and matter_facts.get("small_landlord_exception"):
                    is_triggered = True

                if is_triggered:
                    active_exceptions.append({
                        "id": exc.id,
                        "section": exc.section,
                        "title": exc.title,
                        "content": exc.content,
                        "triggering_fact": "Matched matter facts to statutory carve-out"
                    })
                    hops.append(ResolutionHop(
                        step=len(hops) + 1,
                        hop_type="EXCEPTION",
                        from_node=current_node.section,
                        to_node=exc.section,
                        action="EXCEPTION_APPLIED",
                        decision="KEPT",
                        reason=f"Statutory exception triggered by matter facts: {exc.section}",
                        as_of_date=target_date.isoformat()
                    ))

        # Step 7: Deterministic Slot Extraction from controlling node
        statutory_slots = extract_statutory_slots(current_node.content or "")

        # Format normalized citation
        gov_cite = current_node.section or current_node.title or "California Controlling Statute"
        if not gov_cite.startswith("Section") and not gov_cite.startswith("Cal.") and not gov_cite.startswith("OMC"):
            gov_cite = f"Section {gov_cite}"

        law_node = LawNode(
            id=current_node.id,
            section=current_node.section,
            citation=gov_cite,
            title=current_node.title,
            topic=current_node.topic,
            jurisdiction=current_node.jurisdiction,
            state=current_node.state,
            city=current_node.city or current_node.city_or_county,
            county=current_node.county,
            authority_class=current_node.authority_class,
            effective_date=current_node.effective_date.isoformat() if current_node.effective_date else None,
            effective_from=current_node.effective_from.isoformat() if current_node.effective_from else None,
            effective_to=current_node.effective_to.isoformat() if current_node.effective_to else None,
            status=current_node.status,
            repealed=bool(current_node.repealed),
            content=current_node.content,
            source_url=current_node.source_url
        )

        trace = ResolutionTrace(
            as_of_date=target_date.isoformat(),
            query_topic=doctrine_or_topic,
            jurisdiction=current_node.jurisdiction,
            city=current_node.city or current_node.city_or_county,
            county=current_node.county,
            controlling_node=law_node,
            governing_citation=gov_cite,
            hops=hops,
            discarded_nodes=discarded_candidates,
            coverage_hole=None,
            active_exceptions=active_exceptions,
            mandatory_definitions=mandatory_definitions,
            statutory_slots=statutory_slots,
            confidence_score=0.98 if precedence_chain else 0.85,
            notes=f"Resolved via {len(precedence_chain)} graph steps as of {target_date.isoformat()}."
        )

        return LegalResolution(
            controlling_node={
                "id": current_node.id,
                "section": current_node.section,
                "title": current_node.title,
                "jurisdiction": current_node.jurisdiction,
                "state": current_node.state,
                "city": current_node.city or current_node.city_or_county,
                "county": current_node.county,
                "authority_class": current_node.authority_class,
                "effective_date": current_node.effective_date.isoformat() if current_node.effective_date else None,
                "effective_from": current_node.effective_from.isoformat() if current_node.effective_from else None,
                "effective_to": current_node.effective_to.isoformat() if current_node.effective_to else None,
                "status": current_node.status,
                "repealed": current_node.repealed,
                "content": current_node.content,
                "source_url": current_node.source_url
            },
            governing_citation=gov_cite,
            topic=doctrine_or_topic,
            jurisdiction=current_node.jurisdiction,
            as_of_date=target_date,
            precedence_chain=precedence_chain,
            active_exceptions=active_exceptions,
            mandatory_definitions=mandatory_definitions,
            statutory_slots=statutory_slots,
            confidence_score=0.98 if precedence_chain else 0.85,
            notes=f"Resolved via {len(precedence_chain)} graph steps as of {target_date.isoformat()}.",
            trace=trace,
            coverage_hole=None,
            discarded_nodes=discarded_candidates,
            unconfirmed_proposals=unconfirmed_proposals,
            uncertainty_warning=uncertainty_warning
        )

    except Exception as e:
        logger.error(f"Error during legal authority resolution: {e}", exc_info=True)
        return LegalResolution(
            controlling_node=None,
            governing_citation="Error during resolution",
            topic=doctrine_or_topic,
            jurisdiction=jurisdiction or "California",
            as_of_date=target_date,
            precedence_chain=[],
            active_exceptions=[],
            mandatory_definitions=[],
            statutory_slots={},
            confidence_score=0.0,
            notes=f"Resolution error: {str(e)}"
        )
    finally:
        if close_db:
            db.close()


def explain_why_not_controlling(
    citation: str,
    doctrine_or_topic: str,
    as_of_date: Optional[Any] = None,
    city: Optional[str] = None,
    county: Optional[str] = None,
    matter_facts: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Authoritative diagnostics tool: Explains why a specific statutory section is NOT
    controlling for the given topic, jurisdiction, and as-of date.
    Traces preemption, legislative amendments, temporal effective boundaries, or spatial limits.
    """
    target_date = to_utc_date(as_of_date)
    res = resolve_controlling_law(
        doctrine_or_topic=doctrine_or_topic,
        city=city,
        county=county,
        as_of_date=target_date,
        matter_facts=matter_facts,
        db=db
    )

    controlling_cite = res.governing_citation or "NONE_FOUND"
    clean_target = re.sub(r'[^0-9\.]', '', citation)

    # 1. Check if explicitly in discarded candidates or hops
    discard_reasons = []
    if res.trace:
        for d in res.trace.discarded_nodes:
            d_cite = (d.citation or "").lower()
            d_title = (d.title or "").lower()
            target_l = citation.lower()
            d_clean = re.sub(r'[^0-9\.]', '', d.citation or "")
            if (target_l in d_cite) or (d_cite and d_cite in target_l) or (target_l in d_title) or (clean_target and clean_target == d_clean):
                discard_reasons.append(f"[{d.category}] {d.reason}")
        for hop in res.trace.hops:
            if hop.from_node:
                from_l = hop.from_node.lower()
                target_l = citation.lower()
                from_clean = re.sub(r'[^0-9\.]', '', hop.from_node)
                if (target_l in from_l) or (from_l in target_l) or (clean_target and clean_target == from_clean):
                    if hop.decision != "KEPT":
                        discard_reasons.append(f"[{hop.action}] {hop.reason}")

    if discard_reasons:
        return {
            "citation": citation,
            "is_controlling": False,
            "controlling_authority": controlling_cite,
            "as_of_date": target_date.isoformat(),
            "reasons": discard_reasons,
            "explanation": " ; ".join(discard_reasons)
        }

    # 2. Check if candidate matches the controlling node
    is_ctrl = False
    if res.controlling_node:
        ctrl_sec = (res.controlling_node.get("section") or "").lower()
        ctrl_title = (res.controlling_node.get("title") or "").lower()
        ctrl_cite = controlling_cite.lower()
        target_l = citation.lower()
        clean_ctrl = re.sub(r'[^0-9\.]', '', controlling_cite)

        if (target_l == ctrl_sec) or (target_l in ctrl_cite) or (ctrl_sec and target_l in ctrl_sec) or (target_l in ctrl_title):
            is_ctrl = True
        elif clean_target and clean_target == clean_ctrl and not any(tag in target_l for tag in ["pre-", "superseded", "repealed"]):
            is_ctrl = True

    if is_ctrl:
        return {
            "citation": citation,
            "is_controlling": True,
            "controlling_authority": controlling_cite,
            "as_of_date": target_date.isoformat(),
            "explanation": f"{citation} IS the controlling authority for {doctrine_or_topic} as of {target_date.isoformat()}."
        }

    # 3. Otherwise, not controlling
    generic_reason = f"Section {citation} was superseded, preempted, or not identified as controlling authority for '{controlling_cite}' as of {target_date.isoformat()}."
    return {
        "citation": citation,
        "is_controlling": False,
        "controlling_authority": controlling_cite,
        "as_of_date": target_date.isoformat(),
        "reasons": [generic_reason],
        "explanation": generic_reason
    }


def extract_statutory_slots(text_content: str) -> Dict[str, Any]:
    """
    Deterministic quantitative extraction of binding statutory numbers and deadlines.
    Extracts notice timelines, deposit caps, damages multipliers, and interest terms.
    """
    slots: Dict[str, Any] = {}
    if not text_content:
        return slots

    content_lower = text_content.lower()

    # 1. Statutory Notice Periods
    notice_matches = re.findall(r'(\d+)\s*(?:business\s+|calendar\s+)?days?\b', text_content, re.IGNORECASE)
    if notice_matches:
        days_list = sorted(list({int(d) for d in notice_matches if int(d) < 365}))
        slots["statutory_notice_days"] = days_list
        if 21 in days_list and ("security deposit" in content_lower or "1950.5" in text_content):
            slots["deposit_accounting_days"] = 21
            slots["deposit_return_days"] = 21
        if 3 in days_list and ("pay or quit" in content_lower or "cure" in content_lower):
            slots["cure_notice_days"] = 3
        if 14 in days_list and ("inspection" in content_lower):
            slots["inspection_request_days"] = 14
        if 180 in days_list and ("retaliat" in content_lower or "presumption" in content_lower):
            slots["retaliation_presumption_days"] = 180

    # Hours notice for landlord entry
    hour_match = re.search(r'(\d+)\s*hours?\s*(?:written\s+)?notice', text_content, re.IGNORECASE)
    if hour_match:
        slots["entry_notice_hours"] = int(hour_match.group(1))

    # 2. Security Deposit Cap (Months of Rent)
    if "one month's rent" in content_lower or "1 month's rent" in content_lower or "one month rent" in content_lower:
        slots["deposit_cap_months"] = 1.0
    elif "two months' rent" in content_lower or "2 months' rent" in content_lower or "two months rent" in content_lower:
        slots["deposit_cap_months"] = 2.0
    elif "three months' rent" in content_lower or "3 months' rent" in content_lower:
        slots["deposit_cap_months"] = 3.0

    # 3. Statutory Damages Multiplier
    if re.search(r'twice\s+the\s+amount|2x|double\s+damages|two\s+times', content_lower):
        slots["statutory_damages_multiplier"] = 2.0
    elif re.search(r'treble\s+damages|three\s+times|3x', content_lower):
        slots["statutory_damages_multiplier"] = 3.0

    # 4. Daily Statutory Penalty (e.g. § 789.3 utility shutoff)
    penalty_match = re.search(r'(?:one\s+hundred|100)\s*dollars?\s*(?:for\s+each|per)\s*day', content_lower)
    if penalty_match or "$100" in text_content:
        slots["daily_statutory_penalty"] = 100.0

    # 5. Rent Increase Caps (AB 1482 5% + CPI max 10%)
    if "5 percent" in content_lower or "5%" in text_content:
        slots["rent_cap_base_pct"] = 5.0
    if "10 percent" in content_lower or "10%" in text_content:
        slots["rent_cap_max_pct"] = 10.0

    # 6. Relocation Assistance
    if "one month of the tenant's rent" in content_lower or "one month's rent" in content_lower:
        if "relocation" in content_lower:
            slots["relocation_assistance_months"] = 1.0

    # 7. Habitability & Repair-and-Deduct Waiver Prohibition (§ 1942.1)
    if "1942.1" in text_content or ("waive" in content_lower and ("1941" in text_content or "1942" in text_content or "habitability" in content_lower)):
        slots["habitability_waiver_prohibited"] = True

    # 8. Retaliation Waiver Prohibition (§ 1942.5(h))
    if "1942.5" in text_content and ("waiver" in content_lower or "void" in content_lower):
        slots["retaliation_waiver_prohibited"] = True

    # 9. Commercial Security Deposit Permissive Waiver (§ 1950.7(f))
    if "1950.7" in text_content:
        slots["commercial_deposit_waiver_permitted"] = True

    return slots


def detect_legal_conflicts(
    authorities: List[Dict[str, Any]],
    matter_facts: Optional[Dict[str, Any]] = None,
    as_of_date: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """
    Detects substantive statutory and municipal conflicts across retrieved legal authorities:
      1. Preemption Conflicts: Municipal ordinance provisions overridden by State acts.
      2. Temporal Conflicts: Obsolete/repealed provisions applied to modern incident dates.
      3. Exemption Conflicts: General rule asserted where client facts trigger a recognized exemption.
      4. Numerical & Slot Contradictions: Discrepancies between statutory caps and client terms.
    """
    conflicts: List[Dict[str, Any]] = []
    target_date = to_utc_date(as_of_date)
    matter_facts = matter_facts or {}

    for auth in authorities:
        sec = auth.get("section") or "Unknown Section"
        content = auth.get("content") or ""
        preempted_by = auth.get("preempted_by")

        # Conflict 1: Preemption Conflict
        if preempted_by:
            conflicts.append({
                "conflict_type": "preemption_conflict",
                "severity": "HIGH",
                "section": sec,
                "operative_statute": preempted_by,
                "issue": f"Local provision '{sec}' is preempted by controlling state law: {preempted_by}.",
                "attorney_advisory": (
                    f"Do NOT rely on {sec} as controlling authority in pleadings. "
                    f"State statute ({preempted_by}) occupies the field and controls under California law."
                )
            })

        # Conflict 2: Temporal Conflict (Repealed or Sunset Provision)
        eff_to = auth.get("effective_to")
        if eff_to:
            eff_to_date = to_utc_date(eff_to)
            if eff_to_date < target_date:
                conflicts.append({
                    "conflict_type": "temporal_conflict",
                    "severity": "CRITICAL",
                    "section": sec,
                    "effective_to": eff_to_date.isoformat(),
                    "as_of_date": target_date.isoformat(),
                    "issue": f"Provision '{sec}' sunset on {eff_to_date} and was NOT in effect on matter date {target_date}.",
                    "attorney_advisory": (
                        "Check legislative history for chaptered amendment. Applying repealed provisions "
                        "violates ABA Model Rule 3.3 (Candor Toward the Tribunal)."
                    )
                })

        # Conflict 3: Exemption Conflict (e.g. Single-family home or Owner-occupied duplex)
        if "1946.2" in sec and ("just cause" in content.lower()):
            if matter_facts.get("owner_occupied_duplex"):
                conflicts.append({
                    "conflict_type": "exception_applies",
                    "severity": "HIGH",
                    "section": sec,
                    "statutory_exception": "Cal. Civ. Code § 1946.2(e)(6)",
                    "issue": "Matter facts specify an owner-occupied duplex, which is exempt from statewide Just Cause requirements.",
                    "attorney_advisory": (
                        "Landlord is exempt from demonstrating statutory Just Cause under § 1946.2(e)(6). "
                        "Evaluate local municipal just cause ordinances (e.g. OMC 8.22) if property is in an incorporated city."
                    )
                })
            elif matter_facts.get("single_family"):
                conflicts.append({
                    "conflict_type": "exception_applies",
                    "severity": "HIGH",
                    "section": sec,
                    "statutory_exception": "Cal. Civ. Code § 1946.2(e)(8)",
                    "issue": "Matter involves a single-family dwelling alienable separate from the title to any other dwelling unit.",
                    "attorney_advisory": (
                        "Property may be exempt from AB 1482 if landlord gave statutory written notice of exemption. "
                        "Verify whether lease agreement contains the mandatory exemption disclosure clause."
                    )
                })

        # Conflict 4: Security Deposit Cap Conflict (AB 12 post-July 1, 2024)
        if "1950.5" in sec or "security deposit" in content.lower():
            if target_date >= date(2024, 7, 1):
                # Under AB 12, max deposit is 1 month rent
                claimed_deposit_months = matter_facts.get("deposit_months")
                if claimed_deposit_months and float(claimed_deposit_months) > 1.0:
                    if not matter_facts.get("small_landlord_exception"):
                        conflicts.append({
                            "conflict_type": "statutory_term_violation",
                            "severity": "CRITICAL",
                            "section": "Cal. Civ. Code § 1950.5(c)",
                            "operative_rule": "Maximum 1 month's rent for residential leases executed on or after July 1, 2024.",
                            "violating_term": f"Landlord demanded {claimed_deposit_months} months rent.",
                            "issue": "Lease security deposit exceeds the statutory maximum enacted by Stats. 2023, ch. 290 (AB 12).",
                            "attorney_advisory": (
                                f"Demand immediate refund of excess deposit (${claimed_deposit_months - 1.0:.1f} months). "
                                f"Under § 1950.5(l), bad faith retention subjects landlord to statutory damages of up to twice the deposit amount."
                            )
                        })

        # Conflict 5: Habitability / Repair-and-Deduct Waiver Conflict (§ 1942.1)
        if "1942.1" in sec or "1941" in sec or "habitability" in content.lower():
            if matter_facts.get("waives_habitability") or matter_facts.get("waives_repair_deduct") or matter_facts.get("as_is_lease"):
                conflicts.append({
                    "conflict_type": "statutory_term_violation",
                    "severity": "CRITICAL",
                    "section": "Cal. Civ. Code § 1942.1",
                    "operative_rule": "Any agreement by a tenant by which he waives or modifies his rights under Section 1941 or 1942 shall be void as contrary to public policy.",
                    "violating_term": "Lease purports to waive tenant habitability rights or repair-and-deduct remedies.",
                    "issue": "Tenant rights under Civ. Code §§ 1941 and 1942 are non-waivable as a matter of law.",
                    "attorney_advisory": (
                        "Advise client that the purported waiver is void as against public policy under § 1942.1. "
                        "Tenant remains fully protected by the implied warranty of habitability."
                    )
                })

        # Conflict 6: Deposit Return Timeline Conflict (Civ. Code § 1950.5(g)(1))
        if "1950.5" in sec or "security deposit" in content.lower():
            claimed_return_days = matter_facts.get("deposit_return_days")
            if claimed_return_days and float(claimed_return_days) > 21.0:
                conflicts.append({
                    "conflict_type": "statutory_term_violation",
                    "severity": "HIGH",
                    "section": "Cal. Civ. Code § 1950.5(g)(1)",
                    "operative_rule": "Landlord must furnish itemized accounting and remaining deposit within 21 calendar days.",
                    "violating_term": f"Lease provides {float(claimed_return_days):.0f} days to return deposit.",
                    "issue": "Lease term attempts to extend deposit accounting beyond the mandatory 21-day statutory ceiling.",
                    "attorney_advisory": (
                        f"Lease clause allowing {float(claimed_return_days):.0f} days is void under § 1950.5(n). "
                        "Landlord must account for deposit within 21 calendar days of tenant surrender."
                    )
                })

        # Conflict 7: Retaliation Rights Waiver Conflict (Civ. Code § 1942.5(h))
        if "1942.5" in sec or "retaliat" in content.lower():
            if matter_facts.get("waives_retaliation") or matter_facts.get("waives_retaliation_defense"):
                conflicts.append({
                    "conflict_type": "statutory_term_violation",
                    "severity": "CRITICAL",
                    "section": "Cal. Civ. Code § 1942.5(h)",
                    "operative_rule": "Any waiver by a tenant of rights under Section 1942.5 shall be void as contrary to public policy.",
                    "violating_term": "Lease purports to waive statutory retaliation defenses.",
                    "issue": "Waiver of retaliatory eviction defense is void under California law.",
                    "attorney_advisory": (
                        "Waiver is void as contrary to public policy under § 1942.5(h). "
                        "Retaliatory eviction defense remains fully available in any unlawful detainer."
                    )
                })

    return conflicts
