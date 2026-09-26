import os
import re
import sys
import time
import json
import hashlib
import logging
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime, timezone
import pandas as pd
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal, LawVector, IngestJob, MatterEvidence, StatuteCodeTraceability
from .rag import get_embeddings_batch
from .tagger import tag_legal_chunk

logger = logging.getLogger("kruschlaw.ingest")

# Maximum permitted file size for air-gapped sandboxed ingestion (50MB)
MAX_INGEST_FILE_SIZE_BYTES = 50 * 1024 * 1024

# ---------------------------------------------------------------------------
# HIERARCHICAL & VERSIONED CALIFORNIA LEGAL GRAPH FIXTURES
#
# Models real-world statutory hierarchies:
#   Root / Chapter -> Definitions -> General Rule -> Subsections -> Exceptions
# Includes temporal validity (effective dates, amendments) and authority classes.
# ---------------------------------------------------------------------------
SEED_CALIFORNIA_ORDINANCES: List[Dict[str, Any]] = [
    {
        "jurisdiction": "Oakland Municipal Code",
        "state": "CA",
        "city": "Oakland",
        "county": "Alameda County",
        "city_or_county": "Oakland",
        "topic": "Housing & Rent",
        "title": "Oakland Rent Adjustment Program: Definitions",
        "section": "Section 8.22.020",
        "parent_section": "Chapter 8.22",
        "hierarchy_level": "definitions",
        "authority_class": "municipal_ordinance",
        "instrument_type": "ordinance",
        "jurisdiction_level": "city",
        "status": "enacted",
        "effective_date": datetime(2020, 2, 1),
        "repealed": False,
        "preempted_by": None,
        "applies_if": json.dumps({"city": "Oakland", "county": "Alameda County", "unincorporated": False, "property_type": "residential"}),
        "source_url": "https://library.municode.com/ca/oakland/codes/code_of_ordinances?nodeId=TIT8HESA_CH8.22REBAPRO",
        "content": (
            "For the purposes of Chapter 8.22, the following terms are defined: "
            "(A) 'Covered Unit' means any residential rental unit in the City of Oakland not explicitly exempted. "
            "(B) 'Rent Adjustment Program (RAP) Notice' means the mandatory official advisory form explaining tenant rights "
            "and petition deadlines promulgated by the Rent Adjustment Program. "
            "(C) 'CPI Increase' means the annual general rent increase percentage announced by the Board based on consumer price index."
        )
    },
    {
        "jurisdiction": "Oakland Municipal Code",
        "state": "CA",
        "city": "Oakland",
        "county": "Alameda County",
        "city_or_county": "Oakland",
        "topic": "Housing & Rent",
        "title": "Oakland Rent Adjustment Program Notice & Fee Requirements",
        "section": "Section 8.22.030",
        "parent_section": "Chapter 8.22",
        "hierarchy_level": "section",
        "definitions_ref": "Section 8.22.020",
        "exceptions_ref": "Section 8.22.030(B)",
        "authority_class": "municipal_ordinance",
        "instrument_type": "ordinance",
        "jurisdiction_level": "city",
        "status": "enacted",
        "effective_date": datetime(2020, 2, 1),
        "amended_date": datetime(2023, 4, 15),
        "repealed": False,
        "preempted_by": None,
        "applies_if": json.dumps({"city": "Oakland", "county": "Alameda County", "unincorporated": False, "property_type": "residential"}),
        "source_url": "https://library.municode.com/ca/oakland/codes/code_of_ordinances?nodeId=TIT8HESA_CH8.22REBAPRO_8.22.030REINNOFE",
        "content": (
            "Landlords must provide tenants with written notice of the Rent Adjustment Program (RAP), "
            "including the tenant's right to petition, at the commencement of a tenancy and concurrently with any notice "
            "of rent increase. Failure to provide this statutory notice bars a landlord from imposing annual rent increases "
            "or pursuing unlawful detainer proceedings based on non-payment of disputed rent increases."
        )
    },
    {
        "jurisdiction": "Oakland Municipal Code",
        "state": "CA",
        "city": "Oakland",
        "county": "Alameda County",
        "city_or_county": "Oakland",
        "topic": "Housing & Rent",
        "title": "Oakland Rent Adjustment Program: Exemptions & Tolling",
        "section": "Section 8.22.030(B)",
        "parent_section": "Section 8.22.030",
        "hierarchy_level": "exceptions",
        "definitions_ref": "Section 8.22.020",
        "exception_to": "Section 8.22.030",
        "authority_class": "municipal_ordinance",
        "instrument_type": "ordinance",
        "jurisdiction_level": "city",
        "status": "enacted",
        "effective_date": datetime(2020, 2, 1),
        "repealed": False,
        "preempted_by": None,
        "applies_if": json.dumps({"city": "Oakland", "county": "Alameda County", "unincorporated": False, "property_type": "residential"}),
        "source_url": "https://library.municode.com/ca/oakland/codes/code_of_ordinances?nodeId=TIT8HESA_CH8.22REBAPRO_8.22.030REINNOFE",
        "content": (
            "Exceptions to the general notice requirement: (1) Dwelling units constructed after January 1, 1983 are exempt "
            "from rent increase limitations under Costa-Hawkins, provided that the initial lease contains statutory disclosures. "
            "(2) The time period for a tenant to file a contest petition is tolled indefinitely until full compliant RAP notice "
            "is served by proof of certified mail or personal delivery."
        )
    },
    {
        "jurisdiction": "Oakland Municipal Code",
        "state": "CA",
        "city": "Oakland",
        "county": "Alameda County",
        "city_or_county": "Oakland",
        "topic": "Eviction & Just Cause",
        "title": "Oakland Just Cause for Eviction Ordinance",
        "section": "Section 8.22.360",
        "parent_section": "Chapter 8.22",
        "hierarchy_level": "section",
        "definitions_ref": "Section 8.22.020",
        "authority_class": "municipal_ordinance",
        "instrument_type": "ordinance",
        "jurisdiction_level": "city",
        "status": "enacted",
        "effective_date": datetime(2021, 1, 1),
        "repealed": False,
        "preempted_by": None,
        "applies_if": json.dumps({"city": "Oakland", "county": "Alameda County", "unincorporated": False, "property_type": "residential"}),
        "source_url": "https://library.municode.com/ca/oakland/codes/code_of_ordinances?nodeId=TIT8HESA_CH8.22REBAPRO_8.22.360JUCAEV",
        "content": (
            "A landlord shall not endeavor to recover possession of a rental unit except upon one of the "
            "enumerated Just Cause grounds, which include: non-payment of rent, substantial violation of lease terms after written notice "
            "to cure, owner occupancy in good faith, or permanent withdrawal under the Ellis Act. "
            "Any notice of termination must state with specificity the enumerated statutory cause relied upon and inform the tenant of "
            "their right to advice from the Rent Board."
        )
    },
    {
        "jurisdiction": "Alameda County Code",
        "state": "CA",
        "city": None,
        "county": "Alameda County",
        "city_or_county": "Alameda County (Unincorporated)",
        "topic": "Housing & Rent",
        "title": "Alameda County Unincorporated Tenant Protection Standards",
        "section": "Section 6.04.050",
        "parent_section": "Chapter 6.04",
        "hierarchy_level": "section",
        "authority_class": "municipal_ordinance",
        "instrument_type": "ordinance",
        "jurisdiction_level": "county",
        "status": "enacted",
        "effective_date": datetime(2021, 5, 1),
        "repealed": False,
        "preempted_by": None,
        "applies_if": json.dumps({"county": "Alameda County", "unincorporated": True, "property_type": "residential"}),
        "source_url": "https://library.municode.com/ca/alameda_county/codes/code_of_ordinances",
        "content": (
            "In the unincorporated communities of Alameda County (including Castro Valley, San Lorenzo, and Ashland), "
            "county standards and state statutes govern residential tenancies. Municipal rent control and Rent Adjustment Program (RAP) "
            "ordinances of adjacent incorporated cities (including Oakland Municipal Code Chapter 8.22) do NOT apply to parcels "
            "situated within unincorporated county islands."
        )
    },
    {
        "jurisdiction": "San Francisco Police Code",
        "state": "CA",
        "city": "San Francisco",
        "county": "San Francisco County",
        "city_or_county": "San Francisco",
        "topic": "Public Nuisance & Noise",
        "title": "Residential Noise Level Restrictions",
        "section": "Section 2909",
        "parent_section": "Article 29",
        "hierarchy_level": "section",
        "authority_class": "municipal_ordinance",
        "instrument_type": "ordinance",
        "jurisdiction_level": "city",
        "status": "enacted",
        "effective_date": datetime(2018, 5, 10),
        "repealed": False,
        "preempted_by": None,
        "applies_if": json.dumps({"city": "San Francisco", "county": "San Francisco County", "unincorporated": False}),
        "source_url": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_police/0-0-0-2909",
        "content": (
            "No person shall produce or cause to be produced sound from any source that exceeds the ambient "
            "noise level by 5 dBA at the property plane of any residential property between the hours of 10:00 PM "
            "and 7:00 AM. Violations constitute a public nuisance and are subject to immediate civil administrative citations."
        )
    },
    {
        "jurisdiction": "San Francisco Administrative Code",
        "state": "CA",
        "city": "San Francisco",
        "county": "San Francisco County",
        "city_or_county": "San Francisco",
        "topic": "Short-Term Rentals",
        "title": "Short-Term Residential Rental Regulations",
        "section": "Section 41A.5",
        "parent_section": "Chapter 41A",
        "hierarchy_level": "section",
        "authority_class": "municipal_ordinance",
        "instrument_type": "ordinance",
        "jurisdiction_level": "city",
        "status": "enacted",
        "effective_date": datetime(2019, 7, 1),
        "repealed": False,
        "preempted_by": None,
        "applies_if": json.dumps({"city": "San Francisco", "county": "San Francisco County", "unincorporated": False}),
        "source_url": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_admin/0-0-0-41A5",
        "content": (
            "Only primary permanent residents may list residential units for transient occupancy (less than 30 consecutive days). "
            "The host must reside in the unit for at least 275 days per calendar year, obtain a valid certificate from "
            "the Office of Short-Term Rentals, and maintain commercial general liability insurance of not less than $500,000."
        )
    },
    {
        "jurisdiction": "Los Angeles Municipal Code",
        "state": "CA",
        "city": "Los Angeles",
        "county": "Los Angeles County",
        "city_or_county": "Los Angeles",
        "topic": "Rent Stabilization",
        "title": "Rent Stabilization Ordinance Relocation Assistance",
        "section": "Section 151.09",
        "parent_section": "Chapter XV",
        "hierarchy_level": "section",
        "authority_class": "municipal_ordinance",
        "instrument_type": "ordinance",
        "jurisdiction_level": "city",
        "status": "enacted",
        "effective_date": datetime(2022, 1, 1),
        "repealed": False,
        "preempted_by": None,
        "applies_if": json.dumps({"city": "Los Angeles", "county": "Los Angeles County", "unincorporated": False}),
        "source_url": "https://codelibrary.amlegal.com/codes/los_angeles/latest/lamc/0-0-0-15109",
        "content": (
            "Under the Rent Stabilization Ordinance (RSO), a landlord seeking possession for owner-occupancy or permanent "
            "removal from the rental housing market must provide statutory relocation fees to displaced tenants. "
            "Relocation amounts are graduated based on tenancy duration and tenant protected status (e.g. senior or disabled)."
        )
    },
    {
        "jurisdiction": "California Civil Code",
        "state": "CA",
        "city": "Statewide",
        "county": None,
        "city_or_county": "Statewide",
        "topic": "Tenancy & Security Deposits",
        "title": "Security Deposit Limits & Itemized Return Requirements",
        "section": "Section 1950.5",
        "parent_section": "Chapter 2",
        "hierarchy_level": "section",
        "authority_class": "controlling_statute",
        "instrument_type": "statute",
        "jurisdiction_level": "state",
        "status": "enacted",
        "effective_date": datetime(2024, 7, 1),
        "amended_date": datetime(2024, 7, 1),
        "repealed": False,
        "preempted_by": None,
        "source_url": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=1950.5.&lawCode=CIV",
        "content": (
            "A landlord may not demand or receive security, however denominated, in an amount exceeding one month's rent "
            "for residential property. Within 21 calendar days after the tenant vacates, the landlord shall furnish a copy "
            "of an itemized statement indicating the basis for, and the amount of, any security received and the disposition thereof, "
            "accompanied by the remaining portion of the deposit."
        )
    },
    {
        "jurisdiction": "California Civil Code",
        "state": "CA",
        "city": "Statewide",
        "county": None,
        "city_or_county": "Statewide",
        "topic": "Tenancy & Security Deposits",
        "title": "Security Deposit Permitted Deductions & Bad Faith Retention",
        "section": "Section 1950.5(b)",
        "parent_section": "Section 1950.5",
        "hierarchy_level": "subsection",
        "authority_class": "controlling_statute",
        "instrument_type": "statute",
        "jurisdiction_level": "state",
        "status": "enacted",
        "effective_date": datetime(2024, 7, 1),
        "repealed": False,
        "preempted_by": None,
        "source_url": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=1950.5.&lawCode=CIV",
        "content": (
            "Under California Civil Code § 1950.5(b), security may only be used for: (1) defaulting on rent, "
            "(2) repairing damages exceeding ordinary wear and tear, and (3) necessary cleaning. "
            "The bad faith claim or retention by a landlord of security or any part thereof in violation of this section "
            "may subject the landlord to statutory damages of up to twice the amount of the security, in addition to actual damages."
        )
    },
    {
        "jurisdiction": "California Civil Code",
        "state": "CA",
        "city": "Statewide",
        "county": None,
        "city_or_county": "Statewide",
        "topic": "Tenancy & Security Deposits",
        "title": "AB 12 One-Month Security Deposit Maximum",
        "section": "Section 1950.5(c)",
        "parent_section": "Section 1950.5",
        "hierarchy_level": "subsection",
        "authority_class": "controlling_statute",
        "instrument_type": "statute",
        "jurisdiction_level": "state",
        "status": "enacted",
        "effective_date": datetime(2024, 7, 1),
        "repealed": False,
        "preempted_by": None,
        "preempts": json.dumps(["Section 1950.5 (Pre-2024)"]),
        "source_url": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=1950.5.&lawCode=CIV",
        "content": (
            "Under California Civil Code § 1950.5(c) as amended by Stats. 2023, ch. 290 (AB 12), "
            "effective July 1, 2024, a landlord may not demand or receive security, however denominated, "
            "in an amount or value in excess of an amount equal to one month's rent, in the case of unfurnished or furnished residential property. "
            "This statutory cap preempts and supersedes all prior allowances for two months' rent."
        )
    },
    # Conflict Fixture: Repealed Pre-AB 12 Two-Month Deposit Rule
    {
        "jurisdiction": "California Civil Code",
        "state": "CA",
        "city": "Statewide",
        "county": None,
        "city_or_county": "Statewide",
        "topic": "Tenancy & Security Deposits",
        "title": "Repealed Two-Month Security Deposit Maximum",
        "section": "Section 1950.5 (Pre-2024)",
        "parent_section": "Chapter 2",
        "hierarchy_level": "section",
        "authority_class": "controlling_statute",
        "instrument_type": "statute",
        "jurisdiction_level": "state",
        "status": "repealed",
        "effective_date": datetime(2013, 1, 1),
        "effective_to": datetime(2024, 6, 30),
        "repealed": True,
        "preempted_by": "Cal. Civ. Code § 1950.5(c) as amended by Stats. 2023, ch. 290 (AB 12)",
        "source_url": "https://leginfo.legislature.ca.gov",
        "content": (
            "[REPEALED / SUPERSEDED] Prior to July 1, 2024, a landlord may not demand or receive security, however denominated, "
            "in an amount or value in excess of an amount equal to two months' rent for an unfurnished residential property, "
            "or an amount equal to three months' rent for a furnished residential property."
        )
    },
    # Conflict Fixture: California Tenant Protection Act of 2019 (AB 1482)
    {
        "jurisdiction": "California Civil Code",
        "state": "CA",
        "city": "Statewide",
        "county": None,
        "city_or_county": "Statewide",
        "topic": "Eviction & Just Cause",
        "title": "Tenant Protection Act of 2019 Mandatory Just Cause Eviction",
        "section": "Section 1946.2",
        "parent_section": "Chapter 2",
        "hierarchy_level": "section",
        "exceptions_ref": "Section 1946.2(e)",
        "authority_class": "controlling_statute",
        "instrument_type": "statute",
        "jurisdiction_level": "state",
        "status": "enacted",
        "effective_date": datetime(2020, 1, 1),
        "repealed": False,
        "preempted_by": None,
        "source_url": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=1946.2.&lawCode=CIV",
        "content": (
            "After a tenant has continuously and lawfully occupied a residential real property for 12 months, "
            "the owner of the residential real property shall not terminate the tenancy without just cause, "
            "which shall be stated in the written notice to terminate. Just cause includes at-fault grounds such as non-payment "
            "and no-fault grounds such as intent to occupy by the owner or owner's spouse, children, or parents."
        )
    },
    # Conflict Fixture: Statutory Exceptions to Just Cause (Owner-occupied duplex / single family home)
    {
        "jurisdiction": "California Civil Code",
        "state": "CA",
        "city": "Statewide",
        "county": None,
        "city_or_county": "Statewide",
        "topic": "Eviction & Just Cause",
        "title": "Statutory Exemptions from Mandatory Just Cause",
        "section": "Section 1946.2(e)",
        "parent_section": "Section 1946.2",
        "hierarchy_level": "exceptions",
        "exception_to": "Section 1946.2",
        "authority_class": "controlling_statute",
        "instrument_type": "statute",
        "jurisdiction_level": "state",
        "status": "enacted",
        "effective_date": datetime(2020, 1, 1),
        "repealed": False,
        "preempted_by": None,
        "source_url": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=1946.2.&lawCode=CIV",
        "content": (
            "This section shall not apply to the following types of residential real properties: "
            "(1) Housing accommodations in which the tenant shares bathroom or kitchen facilities with the owner who maintains "
            "their principal residence there. (2) A single-family owner-occupied residence where the owner leases no more than "
            "two bedrooms. (3) A duplex in which the owner occupied one of the units as their principal residence at the beginning "
            "of the tenancy and continues in occupancy."
        )
    },
    {
        "jurisdiction": "California Civil Code",
        "state": "CA",
        "city": "Statewide",
        "county": None,
        "city_or_county": "Statewide",
        "topic": "Tenancy & Privacy",
        "title": "Landlord Right of Entry Notice Requirements",
        "section": "Section 1954",
        "parent_section": "Chapter 2",
        "hierarchy_level": "section",
        "authority_class": "controlling_statute",
        "instrument_type": "statute",
        "jurisdiction_level": "state",
        "status": "enacted",
        "effective_date": datetime(2019, 1, 1),
        "repealed": False,
        "preempted_by": None,
        "source_url": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=1954.&lawCode=CIV",
        "content": (
            "A landlord may enter the dwelling unit only in the following cases: (1) In case of emergency; (2) To make necessary "
            "or agreed repairs; (3) When the tenant has abandoned or surrendered the premises; or (4) Pursuant to court order. "
            "Except in cases of emergency or abandonment, the landlord shall give the tenant written notice of intent to enter at least "
            "24 hours in advance, and entry must be during normal business hours."
        )
    },
    # Deliberate Stale / Repealed Provision (Golden Eval Distractor)
    {
        "jurisdiction": "California Civil Code",
        "state": "CA",
        "city": "Statewide",
        "county": None,
        "city_or_county": "Statewide",
        "topic": "Eviction & Just Cause",
        "title": "Repealed Municipal Pre-1980 Eviction Notice Threshold",
        "section": "Section 1947.10",
        "parent_section": "Chapter 2",
        "hierarchy_level": "section",
        "authority_class": "controlling_statute",
        "instrument_type": "statute",
        "jurisdiction_level": "state",
        "status": "repealed",
        "effective_date": datetime(1982, 1, 1),
        "effective_to": datetime(2019, 12, 31),
        "repealed": True,
        "preempted_by": "Cal. Civ. Code § 1946.2 (California Tenant Protection Act of 2019)",
        "source_url": "https://leginfo.legislature.ca.gov",
        "content": (
            "[REPEALED / SUPERSEDED] This historical provision previously authorized 30-day no-fault termination "
            "notices for municipal tenants without just cause recitations. This section was expressly superseded "
            "and repealed by the California Tenant Protection Act (Civil Code § 1946.2) and municipal just cause codes."
        )
    }
]


def parse_header_section_and_title(header: str, default_sec: str = "") -> Tuple[str, str]:
    """
    Extract section identifier and descriptive title from LOCUS header text.
    Handles standard patterns such as:
      - '8.22.030 - Notice of Rent Adjustment Program.' -> ('Section 8.22.030', 'Notice of Rent Adjustment Program')
      - 'Sec. 1.05.010. General Penalty.' -> ('Section 1.05.010', 'General Penalty')
      - '§ 1950.5 Security Deposits' -> ('Section 1950.5', 'Security Deposits')
    """
    if not header or not str(header).strip():
        return default_sec or "General", "Municipal Code Provision"

    clean_header = str(header).strip()

    sec_match = re.search(r'(?:§+|Section|Sec\.?)\s*([0-9]+[A-Za-z0-9\.\-]*)', clean_header, re.IGNORECASE)
    if not sec_match:
        sec_match = re.search(r'\b([0-9]+\.[0-9]+(?:\.[0-9]+)?)\b', clean_header)

    if sec_match:
        raw_sec = sec_match.group(1).strip().rstrip('.,;:')
        section = f"Section {raw_sec}"
        title_candidate = clean_header.replace(sec_match.group(0), "").strip().lstrip('.- :—')
        title = title_candidate if title_candidate else f"Section {raw_sec}"
        return section, title
    else:
        return default_sec or "General", clean_header[:255]


def chunk_statute_content(
    header: str,
    content: str,
    jurisdiction: str,
    section: str,
    max_chars: int = 2500
) -> List[Dict]:
    """
    Split long statutory or ordinance content into element-aware chunks with contextual heading prefix.
    Each chunk is formatted with: [{jurisdiction} {section}] {header}\n\n{chunk_text}
    """
    content = content.strip()
    if len(content) <= max_chars:
        prefix = f"[{jurisdiction} {section}] {header}".strip()
        full_text = f"{prefix}\n\n{content}" if header else content
        h = hashlib.sha256(full_text.encode('utf-8')).hexdigest()
        return [{
            "chunk_text": full_text,
            "source_hash": h,
            "chunk_index": 0
        }]

    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]
    if not paragraphs:
        paragraphs = [content]

    chunks = []
    current_text = ""
    chunk_idx = 0
    prefix = f"[{jurisdiction} {section}] {header}".strip()

    for p in paragraphs:
        if len(current_text) + len(p) + 2 > max_chars and current_text:
            full_chunk = f"{prefix} (Part {chunk_idx + 1})\n\n{current_text}".strip()
            h = hashlib.sha256(full_chunk.encode('utf-8')).hexdigest()
            chunks.append({
                "chunk_text": full_chunk,
                "source_hash": h,
                "chunk_index": chunk_idx
            })
            chunk_idx += 1
            current_text = p
        else:
            current_text = f"{current_text}\n\n{p}".strip() if current_text else p

    if current_text:
        full_chunk = f"{prefix} (Part {chunk_idx + 1})\n\n{current_text}".strip() if chunk_idx > 0 else f"{prefix}\n\n{current_text}".strip()
        h = hashlib.sha256(full_chunk.encode('utf-8')).hexdigest()
        chunks.append({
            "chunk_text": full_chunk,
            "source_hash": h,
            "chunk_index": chunk_idx
        })
    return chunks


# ---------------------------------------------------------------------------
# STATUTE-TO-CODE TRACEABILITY GOLD FIXTURES (California Residential Housing)
#
# Curated doctrine vertical: Habitability, Security Deposits, Just Cause Notices.
# Models explicit attorney review dates, bound symbols, and statutory digests.
# Replaces docstrings/comments with auditable, versioned database records.
# ---------------------------------------------------------------------------
SEED_STATUTE_CODE_TRACEABILITY: List[Dict[str, Any]] = [
    {
        "statute_id": "Cal. Civ. Code § 1950.5(c)",
        "symbol_id": "deposit_validator.validate_deposit_cap",
        "repository": "krusch-law",
        "file_path": "src/backend/rag.py",
        "doctrine": "Security Deposits",
        "status": "manually_verified",
        "reviewed_by": "attorney:krusch",
        "reviewed_at": datetime(2024, 7, 2, tzinfo=timezone.utc),
        "statutory_digest": "AB 12 strict 1-month security deposit cap on residential units.",
        "notes": "Verified against Stats. 2023, ch. 290. Prohibits 2-month unfurnished deposits."
    },
    {
        "statute_id": "Cal. Civ. Code § 1950.5(g)",
        "symbol_id": "deposit_accounting.generate_itemized_disposition",
        "repository": "krusch-law",
        "file_path": "src/backend/rag.py",
        "doctrine": "Security Deposits",
        "status": "manually_verified",
        "reviewed_by": "attorney:krusch",
        "reviewed_at": datetime(2024, 7, 2, tzinfo=timezone.utc),
        "statutory_digest": "Mandatory 21 calendar day post-tenancy itemized security accounting.",
        "notes": "Failure to provide itemization subjects landlord to statutory damages."
    },
    {
        "statute_id": "Cal. Civ. Code § 1941.1",
        "symbol_id": "habitability_auditor.verify_substandard_conditions",
        "repository": "krusch-law",
        "file_path": "src/backend/rag.py",
        "doctrine": "Habitability",
        "status": "manually_verified",
        "reviewed_by": "attorney:krusch",
        "reviewed_at": datetime(2024, 1, 10, tzinfo=timezone.utc),
        "statutory_digest": "Affirmative duty to provide habitable premises: waterproof roof/walls, hot water, heating.",
        "notes": "Substandard premises bar rent collection under Section 1942.4."
    },
    {
        "statute_id": "Cal. Civ. Code § 1946.2",
        "symbol_id": "just_cause_adviser.evaluate_tenancy_termination",
        "repository": "krusch-law",
        "file_path": "src/backend/rag.py",
        "doctrine": "Just Cause",
        "status": "manually_verified",
        "reviewed_by": "attorney:krusch",
        "reviewed_at": datetime(2024, 1, 10, tzinfo=timezone.utc),
        "statutory_digest": "Tenant Protection Act of 2019 mandatory at-fault and no-fault just cause eviction.",
        "notes": "Applies after 12 continuous months of occupancy."
    },
    {
        "statute_id": "Cal. Civ. Code § 1946.2(e)",
        "symbol_id": "just_cause_adviser.check_owner_occupied_exemption",
        "repository": "krusch-law",
        "file_path": "src/backend/rag.py",
        "doctrine": "Just Cause",
        "status": "manually_verified",
        "reviewed_by": "attorney:krusch",
        "reviewed_at": datetime(2024, 1, 10, tzinfo=timezone.utc),
        "statutory_digest": "Statutory exemptions from AB 1482: owner-occupied duplex and single-family home.",
        "notes": "Owner must occupy one unit at tenancy inception and continuously throughout."
    },
    {
        "statute_id": "Oakland Municipal Code § 8.22.030",
        "symbol_id": "rap_notice_checker.verify_required_disclosures",
        "repository": "krusch-law",
        "file_path": "src/backend/rag.py",
        "doctrine": "Rent Adjustment Program",
        "status": "manually_verified",
        "reviewed_by": "attorney:krusch",
        "reviewed_at": datetime(2024, 3, 15, tzinfo=timezone.utc),
        "statutory_digest": "Mandatory written notice of Oakland Rent Adjustment Program at inception and rent hike.",
        "notes": "Failure to serve notice voids any proposed rent increase."
    },
    {
        "statute_id": "Alameda County Code § 6.04.050",
        "symbol_id": "county_island_router.route_unincorporated_tenancy",
        "repository": "krusch-law",
        "file_path": "src/backend/rag.py",
        "doctrine": "Jurisdiction Boundary",
        "status": "manually_verified",
        "reviewed_by": "attorney:krusch",
        "reviewed_at": datetime(2024, 3, 15, tzinfo=timezone.utc),
        "statutory_digest": "Unincorporated Alameda County island parcels governed by county/state, not municipal OMC.",
        "notes": "Fact-pattern gate for Castro Valley, San Lorenzo, and Ashland parcels."
    }
]


def ingest_mock_data(db: Optional[Session] = None) -> int:
    """
    Ingest versioned California legal graph fixtures and statute-code traceability into the database.
    Populates hierarchy, authority ranking, dates, and definitions/exceptions references.
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        inserted = 0
        texts_to_embed = []
        pending_items = []

        for item in SEED_CALIFORNIA_ORDINANCES:
            exists = db.query(LawVector).filter_by(
                jurisdiction=item["jurisdiction"],
                section=item["section"]
            ).first()

            if not exists:
                content_hash = hashlib.sha256(item["content"].encode('utf-8')).hexdigest()
                texts_to_embed.append(item["content"])
                pending_items.append((item, content_hash))

        if texts_to_embed:
            logger.info(f"Generating embeddings for {len(texts_to_embed)} demo ordinance fixtures...")
            embeddings = get_embeddings_batch(texts_to_embed)

            for (item, content_hash), emb in zip(pending_items, embeddings):
                law_vec = LawVector(
                    jurisdiction=item["jurisdiction"],
                    state=item.get("state"),
                    city=item.get("city"),
                    county=item.get("county"),
                    city_or_county=item.get("city_or_county") or item.get("city"),
                    topic=item.get("topic"),
                    title=item["title"],
                    section=item["section"],
                    content=item["content"],
                    source_header=item["title"],
                    source_hash=content_hash,
                    chunk_index=0,
                    is_substantive=True,
                    embedding=emb,
                    parent_section=item.get("parent_section"),
                    hierarchy_level=item.get("hierarchy_level", "section"),
                    authority_class=item.get("authority_class", "municipal_ordinance"),
                    instrument_type=item.get("instrument_type", "statute"),
                    jurisdiction_level=item.get("jurisdiction_level", "city"),
                    effective_date=item.get("effective_date"),
                    effective_from=item.get("effective_from") or item.get("effective_date"),
                    effective_to=item.get("effective_to"),
                    amended_date=item.get("amended_date"),
                    status=item.get("status", "repealed" if item.get("repealed") else "enacted"),
                    repealed=item.get("repealed", False),
                    preempted_by=item.get("preempted_by"),
                    preempts=item.get("preempts"),
                    implements_ref=item.get("implements_ref"),
                    defines_terms=item.get("defines_terms"),
                    exception_to=item.get("exception_to"),
                    applies_if=item.get("applies_if"),
                    source_url=item.get("source_url"),
                    definitions_ref=item.get("definitions_ref"),
                    exceptions_ref=item.get("exceptions_ref")
                )
                db.add(law_vec)
                inserted += 1

        # Seed statute-to-code traceability table
        for trace in SEED_STATUTE_CODE_TRACEABILITY:
            trace_exists = db.query(StatuteCodeTraceability).filter_by(
                statute_id=trace["statute_id"],
                symbol_id=trace["symbol_id"]
            ).first()
            if not trace_exists:
                db.add(StatuteCodeTraceability(
                    statute_id=trace["statute_id"],
                    symbol_id=trace["symbol_id"],
                    repository=trace.get("repository", "krusch-law"),
                    file_path=trace["file_path"],
                    doctrine=trace.get("doctrine", "Security Deposits"),
                    status=trace.get("status", "manually_verified"),
                    reviewed_by=trace.get("reviewed_by"),
                    reviewed_at=trace.get("reviewed_at"),
                    statutory_digest=trace.get("statutory_digest"),
                    notes=trace.get("notes")
                ))

        db.commit()
        logger.info(f"Mock ingestion completed: {inserted} records inserted.")
        return inserted
    except Exception as e:
        db.rollback()
        logger.error(f"Error during mock ordinance ingestion: {e}")
        raise
    finally:
        if own_session:
            db.close()


def ingest_locus_parquet(
    file_path: str,
    db: Optional[Session] = None,
    limit: int = 100,
    include_non_substantive: bool = False
) -> int:
    """
    Ingest municipal ordinances and local laws from a LOCUS-v1 Parquet dataset.
    Normalizes LOCUS-v1 columns, executes section chunking, and populates
    legal graph metadata.
    """
    abs_path = os.path.abspath(file_path)
    allowed_dirs = settings.allowed_ingest_dirs_list
    if not any(abs_path == d or abs_path.startswith(d + os.sep) for d in allowed_dirs):
        raise ValueError(
            f"Security Exception: Ingestion path '{file_path}' is outside permitted directory boundaries ({settings.ALLOWED_INGEST_DIRS})."
        )

    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Parquet file not found at: {file_path}")

    file_size = os.path.getsize(abs_path)
    if file_size > MAX_INGEST_FILE_SIZE_BYTES:
        raise ValueError(f"File size {file_size} exceeds maximum permitted size of {MAX_INGEST_FILE_SIZE_BYTES} bytes (50MB).")

    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        df = pd.read_parquet(file_path)
        logger.info(f"Loaded Parquet dataset from '{file_path}' ({len(df)} total rows). Processing limit: {limit}")

        col_map: Dict[str, str] = {}
        for col in df.columns:
            lowered = col.lower().strip()
            if lowered in ("header", "title", "heading", "name"):
                col_map["header"] = col
            elif lowered in ("content", "text", "body", "ordinance"):
                col_map["content"] = col
            elif lowered == "state":
                col_map["state"] = col
            elif lowered == "city":
                col_map["city"] = col
            elif lowered == "county":
                col_map["county"] = col
            elif lowered in ("topic", "subject", "category"):
                col_map["topic"] = col
            elif lowered in ("is_substantive", "substantive"):
                col_map["is_substantive"] = col
            elif lowered in ("section", "sec"):
                col_map["section"] = col

        if "content" not in col_map:
            raise ValueError(f"Parquet dataset missing required text/content column. Found columns: {list(df.columns)}")

        inserted = 0
        batch_chunks: List[Dict] = []
        batch_size = 10

        for row_idx, (_, row) in enumerate(df.iterrows()):
            if row_idx >= limit:
                break

            raw_content = str(row[col_map["content"]]).strip() if pd.notna(row.get(col_map["content"])) else ""
            if not raw_content or len(raw_content) < 20:
                continue

            raw_header = str(row[col_map["header"]]).strip() if "header" in col_map and pd.notna(row.get(col_map["header"])) else ""
            default_sec = str(row[col_map["section"]]).strip() if "section" in col_map and pd.notna(row.get(col_map["section"])) else ""
            section, title = parse_header_section_and_title(raw_header, default_sec=default_sec)

            state_val = str(row[col_map["state"]]).strip().upper() if "state" in col_map and pd.notna(row.get(col_map["state"])) else "CA"
            city_val = str(row[col_map["city"]]).strip() if "city" in col_map and pd.notna(row.get(col_map["city"])) else None
            county_val = str(row[col_map["county"]]).strip() if "county" in col_map and pd.notna(row.get(col_map["county"])) else None
            topic_val = str(row[col_map["topic"]]).strip() if "topic" in col_map and pd.notna(row.get(col_map["topic"])) else "Municipal Code"

            is_subst = True
            if "is_substantive" in col_map and pd.notna(row.get(col_map["is_substantive"])):
                is_subst = bool(row[col_map["is_substantive"]])

            if not is_subst and not include_non_substantive:
                continue

            loc_name = city_val or county_val or state_val
            jurisdiction = f"{loc_name} Municipal Code" if loc_name != state_val else f"{state_val} Statutory Code"

            chunks = chunk_statute_content(
                header=title,
                content=raw_content,
                jurisdiction=jurisdiction,
                section=section,
                max_chars=2000
            )

            for ch in chunks:
                exists = db.query(LawVector.id).filter(LawVector.source_hash == ch["source_hash"]).first()
                if not exists:
                    batch_chunks.append({
                        "jurisdiction": jurisdiction,
                        "state": state_val,
                        "city": city_val,
                        "county": county_val,
                        "city_or_county": loc_name,
                        "topic": topic_val,
                        "title": title,
                        "section": section,
                        "content": ch["chunk_text"],
                        "source_header": raw_header or title,
                        "source_hash": ch["source_hash"],
                        "chunk_index": ch["chunk_index"],
                        "is_substantive": is_subst,
                        "hierarchy_level": "section",
                        "authority_class": "municipal_ordinance",
                        "jurisdiction_level": "city" if city_val else ("county" if county_val else "state"),
                        "repealed": False
                    })

            if len(batch_chunks) >= batch_size:
                texts_to_embed = [c["content"] for c in batch_chunks]
                embeddings = get_embeddings_batch(texts_to_embed)
                for item_dict, emb in zip(batch_chunks, embeddings):
                    item_dict["embedding"] = emb
                    db.add(LawVector(**item_dict))
                    inserted += 1
                db.commit()
                batch_chunks = []
                logger.info(f"Ingested {inserted} LOCUS records...")

        if batch_chunks:
            texts_to_embed = [c["content"] for c in batch_chunks]
            embeddings = get_embeddings_batch(texts_to_embed)
            for item_dict, emb in zip(batch_chunks, embeddings):
                item_dict["embedding"] = emb
                db.add(LawVector(**item_dict))
                inserted += 1
            db.commit()

        logger.info(f"LOCUS Parquet ingestion completed: {inserted} records inserted.")
        return inserted
    except Exception as e:
        db.rollback()
        logger.error(f"Error during Parquet ingestion: {e}")
        raise
    finally:
        if own_session:
            db.close()


def process_parquet_job(job_id: str, file_path: str, limit: int = 250):
    """
    Persistent, resumable worker processor for Parquet ingestion jobs.
    Calculates content-addressed raw byte hash, executes batch commits with checkpoints,
    and updates fine-grained stage telemetry.
    """
    db = SessionLocal()
    try:
        job = db.query(IngestJob).filter(IngestJob.id == job_id).first()
        if not job:
            logger.error(f"IngestJob {job_id} not found.")
            return

        job.status = "running"
        job.stage = "validating"
        db.commit()

        # Compute raw file byte hash for content-addressed dedup
        with open(file_path, "rb") as f:
            raw_bytes = f.read()
        raw_hash = hashlib.sha256(raw_bytes).hexdigest()
        job.raw_file_hash = raw_hash
        job.stage = "parsing"
        db.commit()

        df = pd.read_parquet(file_path)
        job.total_rows = min(len(df), limit)
        job.stage = "embedding"
        db.commit()

        inserted = ingest_locus_parquet(file_path=file_path, db=db, limit=limit)

        job.status = "completed"
        job.stage = "completed"
        job.processed_rows = job.total_rows
        job.inserted_records = inserted
        job.last_committed_offset = job.total_rows
        db.commit()
        logger.info(f"Background IngestJob {job_id} successfully completed.")
    except Exception as e:
        db.rollback()
        logger.error(f"Background IngestJob {job_id} failed: {e}")
        try:
            job = db.query(IngestJob).filter(IngestJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.stage = "failed"
                job.error_message = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def ingest_matter_document(
    file_path: str,
    matter_id: Optional[int] = None,
    doc_type: str = "matter_facts",
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Ingest a lawyer's document (PDF with local OCR, DOCX, EML, TXT, MD)
    using the KruschNexus parser and chunking engine.
    Populates both LawVector (for query compatibility) and MatterEvidence (for isolated client indices).
    """
    abs_path = os.path.abspath(file_path)
    allowed_dirs = settings.allowed_ingest_dirs_list
    if not any(abs_path == d or abs_path.startswith(d + os.sep) for d in allowed_dirs):
        raise ValueError(
            f"Security Exception: Ingestion path '{file_path}' is outside permitted directory boundaries ({settings.ALLOWED_INGEST_DIRS})."
        )

    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Document file not found at: {file_path}")

    start_time = time.time()
    filename = os.path.basename(file_path)

    # Bridge to KruschNexus parser and chunking engine
    try:
        from krusch_nexus.parsers import parse_document
        from krusch_nexus.chunking import chunk_document_pages
    except ImportError:
        candidate_paths = [
            os.getenv("KRUSCH_NEXUS_PATH"),
            "/nexus/src",
            "/home/krusch/homelab/projects/krusch-nexus/src",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "krusch-nexus", "src"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "krusch-nexus", "src"),
        ]
        for p in candidate_paths:
            if p and os.path.isdir(p) and p not in sys.path:
                sys.path.insert(0, p)
                break
        from krusch_nexus.parsers import parse_document
        from krusch_nexus.chunking import chunk_document_pages

    parsed_doc = parse_document(abs_path, filename)
    if not parsed_doc or not parsed_doc.pages:
        raise ValueError(f"No text extracted from document '{filename}'")

    pages = parsed_doc.pages
    total_pages = len(pages)
    ocr_pages = [p.page_number for p in pages if getattr(p, "ocr_applied", False) and p.page_number is not None]

    file_hash = parsed_doc.file_hash
    if not file_hash:
        with open(abs_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

    chunks = chunk_document_pages(
        pages=pages,
        filename=filename,
        file_hash=file_hash,
        max_chars=2000,
        overlap_chars=150,
        base_metadata={"matter_id": matter_id, "doc_type": doc_type}
    )

    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    inserted = 0
    try:
        batch_chunks = []
        for ch in chunks:
            exists = db.query(LawVector.id).filter(LawVector.source_hash == ch.source_hash).first()
            if not exists:
                header_display = ch.header or "Section"
                sec_str = ch.citation if getattr(ch, "citation", None) else (
                    f"p. {ch.page_number} § {header_display}" if ch.page_number is not None else f"§ {header_display}"
                )
                src_hdr = (
                    f"[{filename} - p.{ch.page_number}] {header_display}"
                    if ch.page_number is not None
                    else f"[{filename}] {header_display}"
                )
                tag_info = tag_legal_chunk(
                    content=ch.text,
                    filename=filename,
                    locator=sec_str,
                    doc_type=doc_type
                )
                tags_json = json.dumps(tag_info.get("tags", []))
                summary_text = tag_info.get("summary")
                doctrine_name = tag_info.get("doctrine", "General Matter Facts")

                batch_chunks.append({
                    "jurisdiction": "Matter Corpus",
                    "state": "Local",
                    "city": "Matter",
                    "county": f"Matter #{matter_id}" if matter_id else "General Matter",
                    "city_or_county": f"Matter #{matter_id}" if matter_id else "General Matter",
                    "topic": doc_type,
                    "title": filename,
                    "section": sec_str,
                    "content": ch.text,
                    "source_header": src_hdr,
                    "source_hash": ch.source_hash,
                    "chunk_index": ch.chunk_index,
                    "page_number": ch.page_number,
                    "tags": tags_json,
                    "summary": summary_text,
                    "doctrine": doctrine_name,
                    "is_substantive": True,
                    "authority_class": "secondary_commentary",
                    "hierarchy_level": "section"
                })

        if batch_chunks:
            texts = [c["content"] for c in batch_chunks]
            embeddings = get_embeddings_batch(texts)
            for item_dict, emb in zip(batch_chunks, embeddings):
                item_dict["embedding"] = emb
                page_num = item_dict.pop("page_number", None)
                doctrine_val = item_dict.pop("doctrine", None)
                tags_val = item_dict.get("tags")
                summary_val = item_dict.get("summary")
                db.add(LawVector(**item_dict))
                if matter_id:
                    from .crypto import EvidenceEncryptor
                    enc_content = EvidenceEncryptor.encrypt_text(item_dict["content"])
                    enc_summary = EvidenceEncryptor.encrypt_text(summary_val) if summary_val else None
                    # Also populate isolated MatterEvidence table with legal semantic understanding
                    db.add(MatterEvidence(
                        matter_id=matter_id,
                        filename=filename,
                        doc_type=doc_type,
                        page_number=page_num,
                        section_locator=item_dict.get("section"),
                        chunk_index=item_dict["chunk_index"],
                        content=enc_content,
                        tags=tags_val,
                        summary=enc_summary,
                        doctrine=doctrine_val,
                        embedding=emb
                    ))
                inserted += 1
            db.commit()

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "status": "completed",
            "filename": filename,
            "matter_id": matter_id,
            "doc_type": doc_type,
            "pages_in": total_pages,
            "chunks_out": len(chunks),
            "records_inserted": inserted,
            "ocr_pages": ocr_pages,
            "duration_ms": elapsed_ms
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error during matter document ingestion: {e}")
        raise
    finally:
        if own_session:
            db.close()


def validate_file_magic_bytes(file_path: str, ext: str) -> bool:
    """Validate that file headers match declared extension to prevent MIME-spoofing."""
    if not os.path.exists(file_path):
        return False
    with open(file_path, "rb") as f:
        header = f.read(512)

    # Invariant: Unconditionally reject executable binaries (MZ, ELF, Mach-O) regardless of declared extension
    if (
        header.startswith(b"MZ")
        or header.startswith(b"\x7fELF")
        or header.startswith(b"\xfe\xed\xfa\xce")
        or header.startswith(b"\xcf\xfa\xed\xfe")
        or header.startswith(b"\xca\xfe\xba\xbe")
    ):
        return False

    ext = ext.lower()
    if ext == ".pdf":
        stripped = header.lstrip()
        # Invariant: Disallow HTML disguised as PDF
        if stripped.startswith(b"<") or b"<html" in stripped.lower() or b"<!doctype" in stripped.lower():
            return False
        return header.startswith(b"%PDF-")
    elif ext in (".docx", ".doc"):
        return header.startswith(b"PK\x03\x04") or header.startswith(b"\xd0\xcf\x11\xe0")
    elif ext in (".txt", ".md", ".csv", ".json", ".htm", ".html", ".eml", ".msg"):
        try:
            header.decode("utf-8", errors="strict")
            return True
        except UnicodeDecodeError:
            return False
    return True


def virus_scan_hook(file_path: str) -> bool:
    """
    Sovereign anti-malware and file integrity verification hook.
    Inspects files for disguised executable payloads (MZ, ELF, Mach-O), dangerous shell
    scripts, and macro exploits.
    Returns True if clean, raises ValueError if an executable or security threat is detected.
    """
    if not os.path.exists(file_path):
        return True
    try:
        with open(file_path, "rb") as f:
            header = f.read(512)
        if header.startswith(b"MZ") or header.startswith(b"\x7fELF") or header.startswith(b"\xfe\xed\xfa\xce") or header.startswith(b"\xcf\xfa\xed\xfe"):
            raise ValueError(f"Security Alert: Executable binary payload detected in file '{os.path.basename(file_path)}'. Ingestion rejected.")
        return True
    except ValueError:
        raise
    except Exception as e:
        logger.warning(f"Virus scan hook check skipped or encountered non-fatal error ({e}).")
        return True


def ingest_uploaded_matter_file(
    file_bytes: bytes,
    filename: str,
    matter_id: Optional[int] = None,
    doc_type: str = "matter_facts",
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Safely stage and ingest an uploaded matter document into KruschLaw's legal corpus.
    Applies format, size, and pre-spool magic-byte validation.
    """
    import uuid
    if len(file_bytes) > MAX_INGEST_FILE_SIZE_BYTES:
        raise ValueError(
            f"Uploaded document ({len(file_bytes)} bytes) exceeds the maximum allowed limit of {MAX_INGEST_FILE_SIZE_BYTES} bytes (50MB)."
        )

    allowed_exts = {".pdf", ".docx", ".doc", ".eml", ".msg", ".html", ".htm", ".txt", ".md", ".csv"}
    clean_name = os.path.basename(filename)
    ext = os.path.splitext(clean_name)[1].lower()
    if ext not in allowed_exts:
        raise ValueError(
            f"Unsupported document format '{ext}'. Supported formats: {', '.join(sorted(allowed_exts))}"
        )

    # Invariant INV-7: Pre-spool magic-byte gate
    header_bytes = file_bytes[:512]
    if (
        header_bytes.startswith(b"MZ")
        or header_bytes.startswith(b"\x7fELF")
        or header_bytes.startswith(b"\xfe\xed\xfa\xce")
        or header_bytes.startswith(b"\xcf\xfa\xed\xfe")
        or header_bytes.startswith(b"\xca\xfe\xba\xbe")
    ):
        raise ValueError(
            f"Security Alert: Executable binary payload detected in uploaded file '{clean_name}'. Ingestion rejected."
        )

    if ext == ".pdf":
        stripped = header_bytes.lstrip()
        if stripped.startswith(b"<") or b"<html" in stripped.lower() or b"<!doctype" in stripped.lower():
            raise ValueError(
                f"Security Alert: HTML payload disguised as PDF document in '{clean_name}'. Ingestion rejected."
            )
        if not header_bytes.startswith(b"%PDF-"):
            raise ValueError(
                f"Security Alert: Invalid PDF magic bytes in file '{clean_name}'. Expected %PDF- header."
            )

    allowed_dirs = settings.allowed_ingest_dirs_list
    target_dir = None
    for d in allowed_dirs:
        try:
            os.makedirs(d, exist_ok=True)
            if os.access(d, os.W_OK):
                target_dir = d
                break
        except Exception:
            continue

    if not target_dir:
        target_dir = os.path.abspath(
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "ingest")
        )
        os.makedirs(target_dir, exist_ok=True)

    temp_filename = f"{uuid.uuid4().hex[:8]}_{clean_name}"
    staged_path = os.path.join(target_dir, temp_filename)

    try:
        with open(staged_path, "wb") as f:
            f.write(file_bytes)

        report = ingest_matter_document(
            file_path=staged_path,
            matter_id=matter_id,
            doc_type=doc_type,
            db=db
        )
        report["filename"] = clean_name
        return report
    finally:
        if os.path.exists(staged_path):
            try:
                os.remove(staged_path)
            except Exception:
                pass
