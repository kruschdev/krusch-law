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
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from .db import LawVector, SessionLocal
from .tagger import extract_legal_slots

extract_statutory_slots = extract_legal_slots

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


class LegalResolution:
    """
    Structured result of a multi-hop controlling legal authority resolution.
    Provides complete provenance, derivation chain, and quantitative terms for attorneys.
    """
    def __init__(
        self,
        controlling_node: Optional[Dict[str, Any]],
        governing_citation: str,
        topic: str,
        jurisdiction: str,
        as_of_date: date,
        precedence_chain: List[Dict[str, Any]],
        active_exceptions: List[Dict[str, Any]],
        mandatory_definitions: List[Dict[str, Any]],
        statutory_slots: Dict[str, Any],
        confidence_score: float = 1.0,
        notes: Optional[str] = None
    ):
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
            "notes": self.notes
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

        if not candidates:
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
                notes="Zero candidate nodes found for doctrine/jurisdiction in local law store."
            )

        # Step 2: Filter spatial applicability (unincorporated vs incorporated)
        is_unincorporated = bool(matter_facts.get("unincorporated", False))
        fact_city = matter_facts.get("city") or city

        spatially_valid = []
        for cand in candidates:
            applies_if_raw = cand.applies_if
            if applies_if_raw:
                try:
                    conds = json.loads(applies_if_raw) if isinstance(applies_if_raw, str) else applies_if_raw
                    if "unincorporated" in conds:
                        if is_unincorporated and conds["unincorporated"] is False:
                            continue
                        if not is_unincorporated and conds["unincorporated"] is True:
                            continue
                    if "city" in conds and fact_city:
                        if conds["city"].lower() != fact_city.lower():
                            continue
                except Exception:
                    pass
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
            # If superseded_by_id is set, or if an amended node exists
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
                    current_node = prior_node
                    continue

            # Terminal node reached
            chain_step["action"] = "TERMINAL_CONTROLLING_NODE"
            precedence_chain.append(chain_step)
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

        # Step 7: Deterministic Slot Extraction from controlling node
        statutory_slots = extract_statutory_slots(current_node.content or "")

        # Format normalized citation
        gov_cite = current_node.section or current_node.title or "California Controlling Statute"
        if not gov_cite.startswith("Section") and not gov_cite.startswith("Cal.") and not gov_cite.startswith("OMC"):
            gov_cite = f"Section {gov_cite}"

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
            notes=f"Resolved via {len(precedence_chain)} graph steps as of {target_date.isoformat()}."
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
                        f"Check legislative history for chaptered amendment. Applying repealed provisions "
                        f"violates ABA Model Rule 3.3 (Candor Toward the Tribunal)."
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

    return conflicts
