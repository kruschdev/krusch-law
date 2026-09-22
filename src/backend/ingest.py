import os
import logging
from typing import Optional, List, Dict
import pandas as pd
from sqlalchemy.orm import Session

from .db import SessionLocal, LawVector
from .rag import get_embedding

logger = logging.getLogger("kruschlaw.ingest")

SEED_CALIFORNIA_ORDINANCES: List[Dict[str, str]] = [
    {
        "jurisdiction": "Oakland Municipal Code",
        "state": "CA",
        "city_or_county": "Oakland",
        "title": "Oakland Rent Adjustment Program",
        "section": "Section 8.22.030",
        "content": (
            "Landlords must provide tenants with written notice of the Rent Adjustment Program, "
            "including the tenant's right to petition, at the commencement of a tenancy. "
            "Failure to provide this statutory notice bars a landlord from imposing annual rent increases "
            "or pursuing unlawful detainer proceedings based on non-payment of disputed rent."
        )
    },
    {
        "jurisdiction": "Oakland Municipal Code",
        "state": "CA",
        "city_or_county": "Oakland",
        "title": "Oakland Just Cause for Eviction Ordinance",
        "section": "Section 8.22.360",
        "content": (
            "A landlord shall not endeavor to recover possession of a rental unit except upon one of the "
            "enumerated Just Cause grounds, which include: non-payment of rent, substantial violation of lease terms, "
            "owner occupancy in good faith, or withdrawal under the Ellis Act. "
            "Any notice of termination must state with specificity the enumerated statutory cause relied upon."
        )
    },
    {
        "jurisdiction": "San Francisco Police Code",
        "state": "CA",
        "city_or_county": "San Francisco",
        "title": "Residential Noise Level Restrictions",
        "section": "Section 2909",
        "content": (
            "No person shall produce or cause to be produced sound from any source that exceeds the ambient "
            "noise level by 5 dBA at the property plane of any residential property between the hours of 10:00 PM "
            "and 7:00 AM. Violations constitute a public nuisance and are subject to immediate civil administrative citations."
        )
    },
    {
        "jurisdiction": "San Francisco Administrative Code",
        "state": "CA",
        "city_or_county": "San Francisco",
        "title": "Short-Term Residential Rental Regulations",
        "section": "Section 41A.5",
        "content": (
            "Only primary permanent residents may list residential units for transient occupancy (less than 30 consecutive days). "
            "The host must reside in the unit for at least 275 days per calendar year, obtain a valid certificate from "
            "the Office of Short-Term Rentals, and maintain commercial general liability insurance of not less than $500,000."
        )
    },
    {
        "jurisdiction": "Los Angeles Municipal Code",
        "state": "CA",
        "city_or_county": "Los Angeles",
        "title": "Rent Stabilization Ordinance Relocation Assistance",
        "section": "Section 151.09",
        "content": (
            "Under the Rent Stabilization Ordinance (RSO), a landlord seeking possession for owner-occupancy or permanent "
            "removal from the rental housing market must provide statutory relocation fees to displaced tenants. "
            "Relocation amounts are graduated based on tenancy duration and tenant protected status (e.g. senior or disabled)."
        )
    },
    {
        "jurisdiction": "California Civil Code",
        "state": "CA",
        "city_or_county": "Statewide",
        "title": "Security Deposit Limits & Return Requirements",
        "section": "Section 1950.5",
        "content": (
            "A landlord may not demand or receive security, however denominated, in an amount exceeding one month's rent "
            "for residential property. Within 21 calendar days after the tenant vacates, the landlord shall furnish a copy "
            "of an itemized statement indicating the basis for, and the amount of, any security received and the disposition thereof."
        )
    }
]


def ingest_mock_data(db: Optional[Session] = None) -> int:
    """Ingest curated seed legal ordinances into the vector database."""
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        inserted = 0
        for item in SEED_CALIFORNIA_ORDINANCES:
            exists = db.query(LawVector).filter_by(
                jurisdiction=item["jurisdiction"],
                section=item["section"]
            ).first()

            if not exists:
                logger.info(f"Generating embedding for {item['title']} ({item['section']})...")
                embedding = get_embedding(item["content"])
                
                law_vec = LawVector(
                    jurisdiction=item["jurisdiction"],
                    state=item["state"],
                    city_or_county=item["city_or_county"],
                    title=item["title"],
                    section=item["section"],
                    content=item["content"],
                    embedding=embedding
                )
                db.add(law_vec)
                inserted += 1

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


def ingest_locus_parquet(file_path: str, db: Optional[Session] = None, limit: int = 100) -> int:
    """
    Ingest municipal ordinances and local laws from a LOCUS-v1 or compatible Parquet dataset.
    Automatically normalizes heterogeneous schema columns.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Parquet file not found at: {file_path}")

    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        df = pd.read_parquet(file_path)
        logger.info(f"Loaded Parquet dataset from '{file_path}' ({len(df)} total rows). Processing limit: {limit}")

        # Schema resolution: map flexible column names to standard keys
        col_mapping: Dict[str, str] = {}
        for col in df.columns:
            lowered = col.lower()
            if lowered in ["state", "state_code", "st"]:
                col_mapping["state"] = col
            elif lowered in ["city", "county", "city_or_county", "jurisdiction", "jurisdiction_name"]:
                col_mapping["city_or_county"] = col
            elif lowered in ["text", "content", "body", "chunk_text", "ordinance_text"]:
                col_mapping["content"] = col
            elif lowered in ["section", "section_id", "section_num", "sec"]:
                col_mapping["section"] = col
            elif lowered in ["title", "chapter", "code_name", "heading"]:
                col_mapping["title"] = col

        if "content" not in col_mapping:
            raise ValueError(
                f"Parquet dataset lacks a recognizable content/text column. Found columns: {list(df.columns)}"
            )

        inserted = 0
        for idx, row in df.head(limit).iterrows():
            content_text = str(row[col_mapping["content"]]).strip()
            if not content_text or content_text.lower() == "nan":
                continue

            state_val = str(row[col_mapping["state"]]) if "state" in col_mapping else None
            city_val = str(row[col_mapping["city_or_county"]]) if "city_or_county" in col_mapping else None
            sec_val = str(row[col_mapping["section"]]) if "section" in col_mapping else f"Sec-{idx}"
            title_val = str(row[col_mapping["title"]]) if "title" in col_mapping else "Municipal Code"

            # Skip duplicate entries
            exists = db.query(LawVector).filter_by(
                jurisdiction="LOCUS Municipal Law",
                state=state_val,
                city_or_county=city_val,
                section=sec_val
            ).first()

            if not exists:
                embedding = get_embedding(content_text)
                law_vec = LawVector(
                    jurisdiction="LOCUS Municipal Law",
                    state=state_val,
                    city_or_county=city_val,
                    title=title_val,
                    section=sec_val,
                    content=content_text,
                    embedding=embedding
                )
                db.add(law_vec)
                inserted += 1

                # Periodic batch commit to prevent transaction bloat
                if inserted % 25 == 0:
                    db.commit()
                    logger.info(f"Ingested {inserted} LOCUS records...")

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
