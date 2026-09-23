import os
import re
import hashlib
import logging
from typing import Optional, List, Dict, Tuple, Any
import pandas as pd
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal, LawVector, IngestJob
from .rag import get_embedding, get_embeddings_batch

logger = logging.getLogger("kruschlaw.ingest")

# ---------------------------------------------------------------------------
# PARAPHRASED DEMO FIXTURES (NON-OFFICIAL TEST DATA)
#
# NOTE: These seed entries are short, paraphrased illustrative fixtures for
# local interface testing and automated pipeline verification. They DO NOT
# contain the unamended, official statutory text of controlling California
# or municipal codes and must NEVER be relied upon as legal authority.
# ---------------------------------------------------------------------------
SEED_CALIFORNIA_ORDINANCES: List[Dict[str, str]] = [
    {
        "jurisdiction": "Oakland Municipal Code",
        "state": "CA",
        "city": "Oakland",
        "county": "Alameda County",
        "city_or_county": "Oakland",
        "topic": "Housing & Rent",
        "title": "Oakland Rent Adjustment Program (Demo Paraphrase)",
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
        "city": "Oakland",
        "county": "Alameda County",
        "city_or_county": "Oakland",
        "topic": "Eviction & Just Cause",
        "title": "Oakland Just Cause for Eviction Ordinance (Demo Paraphrase)",
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
        "city": "San Francisco",
        "county": "San Francisco County",
        "city_or_county": "San Francisco",
        "topic": "Public Nuisance & Noise",
        "title": "Residential Noise Level Restrictions (Demo Paraphrase)",
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
        "city": "San Francisco",
        "county": "San Francisco County",
        "city_or_county": "San Francisco",
        "topic": "Short-Term Rentals",
        "title": "Short-Term Residential Rental Regulations (Demo Paraphrase)",
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
        "city": "Los Angeles",
        "county": "Los Angeles County",
        "city_or_county": "Los Angeles",
        "topic": "Rent Stabilization",
        "title": "Rent Stabilization Ordinance Relocation Assistance (Demo Paraphrase)",
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
        "city": "Statewide",
        "county": None,
        "city_or_county": "Statewide",
        "topic": "Tenancy & Security Deposits",
        "title": "Security Deposit Limits & Return Requirements (Demo Paraphrase)",
        "section": "Section 1950.5",
        "content": (
            "A landlord may not demand or receive security, however denominated, in an amount exceeding one month's rent "
            "for residential property. Within 21 calendar days after the tenant vacates, the landlord shall furnish a copy "
            "of an itemized statement indicating the basis for, and the amount of, any security received and the disposition thereof."
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

    # Match section pattern: 'Section 8.22.030' or 'Sec. 8.22.030' or '§ 8.22.030' or '8.22.030'
    sec_match = re.search(r'(?:§+|Section|Sec\.?)\s*([0-9]+[A-Za-z0-9\.\-]*)', clean_header, re.IGNORECASE)
    if not sec_match:
        sec_match = re.search(r'\b([0-9]+\.[0-9]+(?:\.[0-9]+)?)\b', clean_header)

    if sec_match:
        raw_sec = sec_match.group(1).strip().rstrip('.,;:')
        section = f"Section {raw_sec}"
        # Remaining portion serves as the section title
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

    # Split into paragraphs to preserve legal sentence/paragraph integrity
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


def ingest_mock_data(db: Optional[Session] = None) -> int:
    """Ingest paraphrased California seed demo fixtures into the database."""
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
                    embedding=emb
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


def ingest_locus_parquet(
    file_path: str,
    db: Optional[Session] = None,
    limit: int = 100,
    include_non_substantive: bool = False
) -> int:
    """
    Ingest municipal ordinances and local laws from a LOCUS-v1 Parquet dataset.
    Normalizes LOCUS-v1 columns:
      - header, content, state, city, county, topic, function, is_substantive
    Performs section-aware chunking, header-aware contextual prefixes,
    SHA-256 deduplication, and batch embeddings.
    """
    abs_path = os.path.abspath(file_path)
    allowed_dirs = settings.allowed_ingest_dirs_list
    if not any(abs_path == d or abs_path.startswith(d + os.sep) for d in allowed_dirs):
        raise ValueError(
            f"Security Exception: Ingestion path '{file_path}' is outside permitted directory boundaries ({settings.ALLOWED_INGEST_DIRS})."
        )

    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Parquet file not found at: {file_path}")

    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        df = pd.read_parquet(file_path)
        logger.info(f"Loaded Parquet dataset from '{file_path}' ({len(df)} total rows). Processing limit: {limit}")

        # Map LOCUS and common dataset columns
        col_map: Dict[str, str] = {}
        for col in df.columns:
            lowered = col.lower().strip()
            if lowered in ["header", "heading", "title", "chapter"]:
                col_map.setdefault("header", col)
            elif lowered in ["content", "text", "body", "ordinance_text", "chunk_text"]:
                col_map.setdefault("content", col)
            elif lowered in ["state", "state_code", "st"]:
                col_map.setdefault("state", col)
            elif lowered in ["city", "city_name"]:
                col_map.setdefault("city", col)
            elif lowered in ["county", "county_name"]:
                col_map.setdefault("county", col)
            elif lowered in ["topic", "function", "category"]:
                col_map.setdefault("topic", col)
            elif lowered in ["is_substantive", "substantive"]:
                col_map.setdefault("is_substantive", col)
            elif lowered in ["section", "section_id", "section_num", "sec"]:
                col_map.setdefault("section", col)
            elif lowered in ["jurisdiction", "jurisdiction_name"]:
                col_map.setdefault("jurisdiction", col)

        if "content" not in col_map:
            raise ValueError(
                f"Parquet dataset lacks a recognizable content/text column. Found columns: {list(df.columns)}"
            )

        # Filter substantive rows if column present and not overridden
        if "is_substantive" in col_map and not include_non_substantive:
            df = df[df[col_map["is_substantive"]] == True]

        inserted = 0
        batch_chunks = []

        for idx, row in df.head(limit).iterrows():
            content_raw = str(row[col_map["content"]]).strip()
            if not content_raw or content_raw.lower() == "nan":
                continue

            raw_header = str(row[col_map["header"]]).strip() if "header" in col_map else ""
            state_val = str(row[col_map["state"]]).strip().upper() if "state" in col_map and pd.notna(row[col_map["state"]]) else None
            city_val = str(row[col_map["city"]]).strip() if "city" in col_map and pd.notna(row[col_map["city"]]) else None
            county_val = str(row[col_map["county"]]).strip() if "county" in col_map and pd.notna(row[col_map["county"]]) else None
            topic_val = str(row[col_map["topic"]]).strip() if "topic" in col_map and pd.notna(row[col_map["topic"]]) else None
            is_sub = bool(row[col_map["is_substantive"]]) if "is_substantive" in col_map else True

            # Determine jurisdiction name
            if "jurisdiction" in col_map and pd.notna(row[col_map["jurisdiction"]]):
                jurisdiction_name = str(row[col_map["jurisdiction"]]).strip()
            elif city_val:
                jurisdiction_name = f"{city_val} Municipal Code"
            elif county_val:
                jurisdiction_name = f"{county_val} Code"
            else:
                jurisdiction_name = "LOCUS Municipal Law"

            # Parse section and title from header
            default_sec = str(row[col_map["section"]]).strip() if "section" in col_map and pd.notna(row[col_map["section"]]) else f"Sec-{idx}"
            parsed_sec, parsed_title = parse_header_section_and_title(raw_header, default_sec=default_sec)

            # Element-aware chunking
            chunks = chunk_statute_content(
                header=raw_header or parsed_title,
                content=content_raw,
                jurisdiction=jurisdiction_name,
                section=parsed_sec
            )

            city_or_cty = city_val or county_val or "Unknown"

            for ch in chunks:
                # Check for duplicate chunk via source_hash or section key
                exists = db.query(LawVector.id).filter(
                    (LawVector.source_hash == ch["source_hash"]) |
                    (
                        (LawVector.jurisdiction == jurisdiction_name) &
                        (LawVector.section == parsed_sec) &
                        (LawVector.chunk_index == ch["chunk_index"])
                    )
                ).first()

                if not exists:
                    batch_chunks.append({
                        "jurisdiction": jurisdiction_name,
                        "state": state_val,
                        "city": city_val,
                        "county": county_val,
                        "city_or_county": city_or_cty,
                        "topic": topic_val,
                        "title": parsed_title,
                        "section": parsed_sec,
                        "content": ch["chunk_text"],
                        "source_header": raw_header,
                        "source_hash": ch["source_hash"],
                        "chunk_index": ch["chunk_index"],
                        "is_substantive": is_sub
                    })

            # Process in embedding batches to scale efficiently
            if len(batch_chunks) >= settings.EMBED_BATCH_SIZE:
                texts_to_embed = [c["content"] for c in batch_chunks]
                embeddings = get_embeddings_batch(texts_to_embed)
                for item_dict, emb in zip(batch_chunks, embeddings):
                    item_dict["embedding"] = emb
                    db.add(LawVector(**item_dict))
                    inserted += 1
                db.commit()
                batch_chunks = []
                logger.info(f"Ingested {inserted} LOCUS records...")

        # Process any remaining chunks
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
    Background worker function to execute Parquet ingestion asynchronously,
    updating IngestJob database records with real-time progress.
    """
    db = SessionLocal()
    try:
        job = db.query(IngestJob).filter(IngestJob.id == job_id).first()
        if not job:
            logger.error(f"IngestJob {job_id} not found.")
            return

        job.status = "running"
        db.commit()

        # Count total rows
        df = pd.read_parquet(file_path)
        job.total_rows = min(len(df), limit)
        db.commit()

        # Ingest
        inserted = ingest_locus_parquet(file_path=file_path, db=db, limit=limit)

        job.status = "completed"
        job.processed_rows = job.total_rows
        job.inserted_records = inserted
        db.commit()
        logger.info(f"Background IngestJob {job_id} successfully completed.")
    except Exception as e:
        db.rollback()
        logger.error(f"Background IngestJob {job_id} failed: {e}")
        try:
            job = db.query(IngestJob).filter(IngestJob.id == job_id).first()
            if job:
                job.status = "failed"
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
    Ingest a lawyer's document (PDF with local OCR fallback, DOCX, EML, TXT, MD)
    using the KruschNexus parser and chunking engine into KruschLaw's LawVector corpus.
    Preserves exact 1-based page numbers and section headers.
    """
    import sys
    import time
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
    nexus_src = os.getenv("KRUSCH_NEXUS_PATH", "/home/krusch/homelab/projects/krusch-nexus/src")
    if nexus_src not in sys.path and os.path.isdir(nexus_src):
        sys.path.insert(0, nexus_src)

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

    # Structural chunking via KruschNexus
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
                    "is_substantive": True
                })

        if batch_chunks:
            texts = [c["content"] for c in batch_chunks]
            embeddings = get_embeddings_batch(texts)
            for item_dict, emb in zip(batch_chunks, embeddings):
                item_dict["embedding"] = emb
                db.add(LawVector(**item_dict))
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


def ingest_uploaded_matter_file(
    file_bytes: bytes,
    filename: str,
    matter_id: Optional[int] = None,
    doc_type: str = "matter_facts",
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Safely stage and ingest an uploaded matter document into KruschLaw's legal corpus
    using KruschNexus's parsing and structural chunking engine.
    """
    import uuid
    allowed_exts = {".pdf", ".docx", ".doc", ".eml", ".msg", ".html", ".htm", ".txt", ".md", ".csv"}
    clean_name = os.path.basename(filename)
    ext = os.path.splitext(clean_name)[1].lower()
    if ext not in allowed_exts:
        raise ValueError(
            f"Unsupported document format '{ext}'. Supported formats: {', '.join(sorted(allowed_exts))}"
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

