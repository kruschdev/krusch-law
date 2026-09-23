import re
import uuid
import time
import hashlib
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from fastapi import (
    FastAPI, Depends, HTTPException, Query, Security,
    BackgroundTasks, UploadFile, File, Form, Request, Response
)
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field

from .config import settings, is_loopback_or_private_host
from .db import (
    init_db, SessionLocal, Case, IngestJob, GroundingReport, AuditLog, MatterEvidence,
    StatuteCodeTraceability, LawVector
)
from .rag import (
    get_embedding, retrieve_laws, generate_legal_analysis,
    UPL_DISCLAIMER, RetrievalError, verify_assertion_grounding,
    expand_legal_query, retrieve_matter_evidence
)
from .ingest import (
    ingest_mock_data, ingest_locus_parquet, process_parquet_job,
    ingest_matter_document, ingest_uploaded_matter_file
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("kruschlaw.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database schemas, extensions, and HNSW indexes on service boot."""
    logger.info("Initializing KruschLaw database schemas and HNSW indexes...")
    try:
        init_db()
        logger.info("Database schemas and indexes initialized successfully.")
    except Exception as e:
        logger.error(f"Error during database startup initialization: {e}")
    yield


app = FastAPI(
    title="KruschLaw API",
    description="Air-Gapped, Privacy-First Legal RAG & Ordinance Intelligence Engine (Research Prototype)",
    version="0.3.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> Optional[str]:
    """
    Verify API Key authentication.
    In non-development environments, unauthenticated access is strictly blocked to protect client data.
    """
    is_dev = getattr(settings, "ENVIRONMENT", "development").lower() in ("development", "dev", "test")
    if not is_dev and not settings.API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Server Misconfiguration: API_KEY must be configured in non-development environments to safeguard client matter confidentiality."
        )
    if not settings.API_KEY:
        return None
    if not api_key or api_key.strip() != settings.API_KEY.strip():
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Missing or invalid X-API-Key header. Client matter data is protected."
        )
    return api_key


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    """FastAPI database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def log_audit_event(
    db: Session,
    action: str,
    actor_key: Optional[str] = None,
    client_ip: Optional[str] = None,
    matter_id: Optional[int] = None,
    retrieved_section_ids: Optional[List[str]] = None,
    model_name: Optional[str] = None,
    grounding_verdict: Optional[str] = None,
    duration_ms: Optional[int] = None
):
    """Write an immutable audit log entry for sovereign review."""
    try:
        actor_hash = hashlib.sha256(actor_key.encode('utf-8')).hexdigest() if actor_key else None
        audit = AuditLog(
            actor_key_hash=actor_hash,
            client_ip=client_ip,
            action=action,
            matter_id=matter_id,
            retrieved_section_ids=json.dumps(retrieved_section_ids) if retrieved_section_ids else None,
            model_name=model_name or settings.OLLAMA_LLM_MODEL,
            model_version="qwen2.5:14b",
            grounding_verdict=grounding_verdict,
            duration_ms=duration_ms
        )
        db.add(audit)
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to record audit log: {e}")


# --- Pydantic Request & Response Schemas ---

class CaseCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255, description="Short title of the client matter")
    matter_number: Optional[str] = Field(None, max_length=50, description="Internal matter tracking code")
    client_name: Optional[str] = Field(None, max_length=255, description="Confidential client or party identifier")
    description: Optional[str] = Field(None, max_length=500, description="Brief classification, tags, or client reference")
    facts: str = Field(..., min_length=10, description="Detailed narrative of facts and circumstances")


class CaseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=255)
    matter_number: Optional[str] = Field(None, max_length=50)
    client_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    facts: Optional[str] = Field(None, min_length=10)


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    matter_number: Optional[str] = None
    client_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    facts: str
    created_at: str
    updated_at: Optional[str] = None


class ParquetIngestRequest(BaseModel):
    file_path: str = Field(..., description="Absolute path to a LOCUS-v1 or compatible Parquet file")
    limit: Optional[int] = Field(100, ge=1, le=10000, description="Maximum number of sections to ingest")


class IngestResponse(BaseModel):
    status: str
    inserted_records: int


class AsyncIngestResponse(BaseModel):
    job_id: str
    status: str
    file_path: str


class IngestJobStatusResponse(BaseModel):
    id: str
    status: str
    file_path: str
    raw_file_hash: Optional[str] = None
    stage: str = "queued"
    total_rows: int = 0
    processed_rows: int = 0
    inserted_records: int = 0
    last_committed_offset: int = 0
    chunks_total: int = 0
    chunks_embedded: int = 0
    error_message: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None


class DocumentIngestRequest(BaseModel):
    file_path: str
    matter_id: Optional[int] = None
    doc_type: Optional[str] = "matter_facts"


class DocumentIngestResponse(BaseModel):
    status: str
    filename: str
    matter_id: Optional[int] = None
    doc_type: Optional[str] = "matter_facts"
    pages_in: int
    chunks_out: int
    records_inserted: int
    ocr_pages: List[int] = []
    duration_ms: float


class LawItem(BaseModel):
    id: int
    jurisdiction: str
    state: Optional[str] = None
    city: Optional[str] = None
    county: Optional[str] = None
    city_or_county: Optional[str] = None
    topic: Optional[str] = None
    title: Optional[str] = None
    section: Optional[str] = None
    content: str
    chunk_index: Optional[int] = 0
    similarity: float
    parent_section: Optional[str] = None
    hierarchy_level: Optional[str] = "section"
    authority_class: Optional[str] = "municipal_ordinance"
    definitions_ref: Optional[str] = None
    exceptions_ref: Optional[str] = None
    repealed: Optional[bool] = False
    preempted_by: Optional[str] = None
    effective_date: Optional[str] = None
    source_url: Optional[str] = None
    is_hydrated_context: Optional[bool] = False


class CaseSummary(BaseModel):
    id: int
    title: str
    facts: str


class ClaimRecord(BaseModel):
    claim: str
    citation: Optional[str] = None
    source_excerpt: Optional[str] = None
    status: str
    reason: Optional[str] = None


class GroundingStats(BaseModel):
    total_claims: int = 0
    supported_claims: int = 0
    unsupported_claims: int = 0
    invented_citations: int = 0
    wrong_propositions: int = 0
    stale_law_citations: int = 0
    pass_rate: float = 100.0


class SpottedIssue(BaseModel):
    issue: str
    jurisdiction: str
    governing_authorities: str


class MatterEvidenceItem(BaseModel):
    id: int
    matter_id: int
    filename: str
    doc_type: str
    page_number: Optional[int] = None
    section_locator: Optional[str] = None
    chunk_index: int
    content: str
    similarity: float
    created_at: Optional[str] = None


class ConsultResponse(BaseModel):
    case: CaseSummary
    retrieved_laws: List[LawItem]
    analysis: str
    disclaimer: str
    review_required: bool = True
    provisional_work_product: bool = True
    grounding_stats: Optional[GroundingStats] = None
    claims_audit: List[ClaimRecord] = []
    spotted_issues: List[SpottedIssue] = []


class ExportDocxRequest(BaseModel):
    brief_content: str
    matter_title: str
    matter_number: Optional[str] = None
    client_name: Optional[str] = None
    claims_audit: Optional[List[Dict[str, Any]]] = None
    retrieved_laws: Optional[List[Dict[str, Any]]] = None


class BriefDraftRequest(BaseModel):
    facts: Optional[str] = None
    case_id: Optional[int] = None
    title: Optional[str] = None
    state: Optional[str] = "CA"
    city: Optional[str] = "Oakland"
    matter_facts: Optional[Dict[str, Any]] = None


class VerifyAssertionsRequest(BaseModel):
    draft_text: str
    laws: Optional[List[Dict[str, Any]]] = None
    matter_facts: Optional[Dict[str, Any]] = None
    as_of_date: Optional[str] = None


class TraceabilityItem(BaseModel):
    id: int
    statute_id: str
    symbol_id: str
    repository: str
    file_path: str
    doctrine: str
    status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    statutory_digest: Optional[str] = None
    notes: Optional[str] = None


# --- API Endpoints ---

@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint with verified runtime security and inference inspection."""
    is_dev = getattr(settings, "ENVIRONMENT", "development").lower() in ("development", "dev", "test")
    ollama_local = is_loopback_or_private_host(settings.OLLAMA_BASE_URL)
    embed_local = is_loopback_or_private_host(settings.OLLAMA_EMBED_HOST)

    if not is_dev:
        return {
            "status": "healthy",
            "service": "kruschlaw-backend",
            "version": "0.3.0",
            "auth_enforced": True,
            "air_gap_verified": bool(ollama_local and embed_local)
        }

    return {
        "status": "healthy",
        "service": "kruschlaw-backend",
        "version": "0.3.0",
        "security": {
            "auth_enabled": bool(settings.API_KEY),
            "ollama_host_is_local_or_private": ollama_local,
            "embed_host_is_local_or_private": embed_local,
            "network_isolation_assessment": (
                "Verified loopback / private network inference endpoints."
                if (ollama_local and embed_local)
                else "Caution: One or more inference endpoints resolve outside private subnets."
            )
        },
        "models": {
            "embeddings": settings.OLLAMA_EMBED_MODEL,
            "reasoning": settings.OLLAMA_LLM_MODEL
        }
    }


@app.post("/api/cases", response_model=CaseResponse, status_code=201, tags=["Cases"])
def create_case(
    payload: CaseCreate,
    request: Request,
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """
    Log a new legal matter. Automatically generates a dense embedding of the factual narrative
    via the local Ollama node.
    """
    try:
        logger.info(f"Generating embedding for matter: '{payload.title}'...")
        vector = get_embedding(payload.facts)

        new_case = Case(
            title=payload.title,
            matter_number=payload.matter_number,
            client_name=payload.client_name,
            description=payload.description,
            facts=payload.facts,
            embedding=vector
        )
        db.add(new_case)
        db.commit()
        db.refresh(new_case)

        log_audit_event(
            db, action="create_matter", actor_key=_auth,
            client_ip=request.client.host if request.client else None,
            matter_id=new_case.id
        )

        return CaseResponse(
            id=new_case.id,
            matter_number=new_case.matter_number,
            client_name=new_case.client_name,
            title=new_case.title,
            description=new_case.description,
            facts=new_case.facts,
            created_at=new_case.created_at.isoformat() if new_case.created_at else "",
            updated_at=new_case.updated_at.isoformat() if new_case.updated_at else None
        )
    except ConnectionError as e:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating case: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to record matter: {str(e)}")


@app.get("/api/cases", response_model=List[CaseResponse], tags=["Cases"])
def get_cases(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """Retrieve all non-deleted client matters, with pagination."""
    try:
        cases = db.query(Case).filter(Case.is_deleted.is_(False)).order_by(Case.created_at.desc()).offset(offset).limit(limit).all()
        return [
            CaseResponse(
                id=c.id,
                matter_number=c.matter_number,
                client_name=c.client_name,
                title=c.title,
                description=c.description,
                facts=c.facts,
                created_at=c.created_at.isoformat() if c.created_at else "",
                updated_at=c.updated_at.isoformat() if c.updated_at else None
            ) for c in cases
        ]
    except Exception as e:
        logger.error(f"Error fetching cases: {e}")
        raise HTTPException(status_code=500, detail="Database retrieval error")


@app.get("/api/cases/{case_id}", response_model=CaseResponse, tags=["Cases"])
def get_case(
    case_id: int,
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """Retrieve a single matter by ID."""
    case = db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Matter #{case_id} not found")
    return CaseResponse(
        id=case.id,
        matter_number=case.matter_number,
        client_name=case.client_name,
        title=case.title,
        description=case.description,
        facts=case.facts,
        created_at=case.created_at.isoformat() if case.created_at else "",
        updated_at=case.updated_at.isoformat() if case.updated_at else None
    )


@app.patch("/api/cases/{case_id}", response_model=CaseResponse, tags=["Cases"])
def update_case(
    case_id: int,
    payload: CaseUpdate,
    request: Request,
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """Update fields on an existing matter. Automatically recalculates embedding if facts change."""
    case = db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Matter #{case_id} not found")

    try:
        if payload.title is not None:
            case.title = payload.title
        if payload.matter_number is not None:
            case.matter_number = payload.matter_number
        if payload.client_name is not None:
            case.client_name = payload.client_name
        if payload.description is not None:
            case.description = payload.description

        if payload.facts is not None and payload.facts != case.facts:
            case.facts = payload.facts
            logger.info(f"Recomputing embedding for updated matter #{case_id}...")
            case.embedding = get_embedding(payload.facts)

        db.commit()
        db.refresh(case)

        log_audit_event(
            db, action="update_matter", actor_key=_auth,
            client_ip=request.client.host if request.client else None,
            matter_id=case.id
        )

        return CaseResponse(
            id=case.id,
            matter_number=case.matter_number,
            client_name=case.client_name,
            title=case.title,
            description=case.description,
            facts=case.facts,
            created_at=case.created_at.isoformat() if case.created_at else "",
            updated_at=case.updated_at.isoformat() if case.updated_at else None
        )
    except ConnectionError as e:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating case #{case_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update matter: {str(e)}")


@app.delete("/api/cases/{case_id}", tags=["Cases"])
def delete_case(
    case_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """Soft-delete a matter record."""
    case = db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Matter #{case_id} not found")

    case.is_deleted = True
    db.commit()

    log_audit_event(
        db, action="delete_matter", actor_key=_auth,
        client_ip=request.client.host if request.client else None,
        matter_id=case_id
    )
    return {"status": "deleted", "message": f"Matter #{case_id} soft-deleted successfully"}


@app.delete("/api/cases/{case_id}/purge", tags=["Cases"])
def purge_case(
    case_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """
    Explicit enterprise matter purge.
    Permanently destroys the client matter, vector embeddings, attached evidence chunks,
    and associated grounding reports from the sovereign database.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Matter #{case_id} not found")

    db.query(MatterEvidence).filter(MatterEvidence.matter_id == case_id).delete()
    db.query(GroundingReport).filter(GroundingReport.case_id == case_id).delete()
    db.delete(case)
    db.commit()

    log_audit_event(
        db, action="purge_matter", actor_key=_auth,
        client_ip=request.client.host if request.client else None,
        matter_id=case_id
    )
    return {"status": "purged", "message": f"Matter #{case_id} and all associated embeddings permanently destroyed."}


@app.get("/api/laws", response_model=List[LawItem], tags=["Laws"])
def search_laws(
    q: Optional[str] = Query(None, description="Natural language search inquiry"),
    limit: Optional[int] = Query(10, ge=1, le=100, description="Max results to return"),
    offset: Optional[int] = Query(0, ge=0),
    state: Optional[str] = Query(None, description="Two-letter state postal filter (e.g. CA)"),
    city: Optional[str] = Query(None, description="City or county filter (e.g. Oakland)"),
    topic: Optional[str] = Query(None, description="Subject classification filter"),
    expand_query: bool = Query(False, description="Enable automated issue-spotting expansion"),
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """Search laws using hybrid vector and lexical ranking with authority hierarchy weighting."""
    try:
        results = retrieve_laws(
            text_query=q,
            limit=limit,
            state_filter=state,
            city_filter=city,
            topic_filter=topic,
            expand_query=expand_query,
            db_session=db
        )
        return [LawItem(**r) for r in results]
    except RetrievalError as e:
        logger.error(f"Law search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected search error: {e}")
        raise HTTPException(status_code=500, detail=f"Retrieval error: {str(e)}")


@app.get("/api/laws/search", tags=["Laws"])
def search_laws_alias(
    q: Optional[str] = Query(None, description="Natural language search inquiry"),
    limit: Optional[int] = Query(5, ge=1, le=20, description="Max results to return"),
    state: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    topic: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """Bridge endpoint for companion context agents querying statutory search."""
    try:
        results = retrieve_laws(
            text_query=q,
            limit=limit,
            state_filter=state,
            city_filter=city,
            topic_filter=topic,
            db_session=db
        )
        return {"results": results}
    except Exception as e:
        logger.error(f"Search laws alias error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/laws/section", tags=["Laws"])
def get_law_section(
    section: str = Query(..., description="Section identifier e.g. 'OMC 8.22.360'"),
    jurisdiction: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """Retrieve unabridged statutory text, parent/child relationships, and exception clauses."""
    clean_sec = section.strip()
    query = db.query(LawVector).filter(
        (LawVector.section == clean_sec) | 
        (LawVector.section == f"Section {clean_sec}") |
        (LawVector.section.like(f"%{clean_sec}%"))
    )
    if jurisdiction:
        query = query.filter(LawVector.jurisdiction == jurisdiction)
    law = query.first()
    if not law:
        raise HTTPException(status_code=404, detail=f"Section '{section}' not found in sovereign corpus.")

    return {
        "section": law.section,
        "title": law.title,
        "chapter": law.parent_section or "",
        "article": law.hierarchy_level or "section",
        "authority_tier": law.authority_class or "controlling_statute",
        "authority_weight": 1.0,
        "body": law.content,
        "content": law.content,
        "status": law.status,
        "effective_date": law.effective_date.isoformat() if law.effective_date else None,
        "repealed": law.repealed
    }


@app.post("/api/verify/assertions", tags=["Verification"])
def verify_assertions_endpoint(
    payload: VerifyAssertionsRequest,
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """
    Two-pass assertion grounding verifier:
      Pass A: Cheap deterministic mechanical verification.
      Pass B: Propositional entailment with numeric, negation, and statutory exception checks.
    """
    laws = payload.laws
    if not laws:
        laws = retrieve_laws(text_query=payload.draft_text, limit=5, db_session=db)

    is_g, claims, notice, stats = verify_assertion_grounding(
        analysis_text=payload.draft_text,
        laws=laws,
        matter_facts=payload.matter_facts,
        as_of_date=payload.as_of_date
    )

    return {
        "is_grounded": is_g,
        "claims": claims,
        "notice": notice,
        "stats": stats,
        "verified_draft": stats.get("verified_draft", payload.draft_text)
    }


@app.post("/api/cases/brief", tags=["Consultation"])
def draft_brief_endpoint(
    payload: BriefDraftRequest,
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """
    Stages an air-gapped legal brief with mandatory assertion-level grounding.
    Refuses to draft if governing authorities are absent. Hard verifier gate.
    """
    facts = payload.facts
    title = payload.title or "Preliminary Legal Consultation"
    case_id = payload.case_id

    if not facts and case_id:
        case = db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).first()
        if case:
            facts = case.facts
            title = case.title

    if not facts:
        raise HTTPException(status_code=400, detail="Factual narrative or valid case_id is required.")

    # Retrieve governing authorities
    matched_laws = retrieve_laws(
        text_query=facts,
        limit=5,
        state_filter=payload.state,
        city_filter=payload.city,
        matter_facts=payload.matter_facts,
        db_session=db
    )

    if not matched_laws:
        return {
            "status": "CANNOT_DRAFT_WITHOUT_AUTHORITIES",
            "message": f"No governing authorities found in the local corpus for {payload.city}, {payload.state}."
        }

    # Generate analysis
    res = generate_legal_analysis(
        case_facts=facts,
        case_title=title,
        laws=matched_laws,
        case_id=case_id,
        db_session=db
    )

    analysis_text = res[0] if isinstance(res, tuple) else str(res)

    # Hard gate: Verify assertion grounding
    is_g, claims, notice, stats = verify_assertion_grounding(
        analysis_text=analysis_text,
        laws=matched_laws,
        matter_facts=payload.matter_facts
    )

    verified_draft = stats.get("verified_draft", analysis_text)

    return {
        "status": "COMPLETED",
        "brief_markdown": verified_draft,
        "raw_analysis": analysis_text,
        "grounding_audit": {
            "supported_count": stats.get("supported_claims", 0),
            "divergent_count": stats.get("wrong_propositions", 0) + stats.get("contradicted_claims", 0),
            "stale_count": stats.get("stale_law_citations", 0),
            "refused_count": stats.get("refused_claims_count", 0),
            "pass_rate": stats.get("pass_rate", 100.0),
            "is_grounded": is_g
        },
        "is_grounded": is_g
    }


@app.get("/api/compliance/traceability", response_model=List[TraceabilityItem], tags=["Compliance & Traceability"])
def get_code_traceability(
    doctrine: Optional[str] = Query(None, description="Doctrine filter (e.g. 'Security Deposits', 'Just Cause')"),
    status: Optional[str] = Query(None, description="Status filter (e.g. 'manually_verified')"),
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """
    Curated statute-to-code traceability registry with attorney review dates and attestation notes.
    Provides verifiable compliance invariants for California residential housing doctrine.
    """
    query = db.query(StatuteCodeTraceability)
    if doctrine:
        query = query.filter(StatuteCodeTraceability.doctrine == doctrine)
    if status:
        query = query.filter(StatuteCodeTraceability.status == status)

    rows = query.order_by(StatuteCodeTraceability.id.asc()).all()
    return [
        TraceabilityItem(
            id=r.id,
            statute_id=r.statute_id,
            symbol_id=r.symbol_id,
            repository=r.repository,
            file_path=r.file_path,
            doctrine=r.doctrine,
            status=r.status,
            reviewed_by=r.reviewed_by,
            reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
            statutory_digest=r.statutory_digest,
            notes=r.notes
        )
        for r in rows
    ]


@app.post("/api/ingest/mock", response_model=IngestResponse, tags=["Ingestion"])
def ingest_mock(
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """Seed versioned California legal graph fixtures into the local store."""
    try:
        inserted = ingest_mock_data(db)
        return IngestResponse(status="success", inserted_records=inserted)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Mock ingestion error: {e}")
        raise HTTPException(status_code=500, detail=f"Mock ingestion failed: {str(e)}")


@app.post("/api/ingest/parquet", response_model=IngestResponse, tags=["Ingestion"])
def ingest_parquet(
    payload: ParquetIngestRequest,
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """Synchronously ingest municipal ordinances from a LOCUS-v1 Parquet file."""
    try:
        inserted = ingest_locus_parquet(payload.file_path, db=db, limit=payload.limit)
        return IngestResponse(status="success", inserted_records=inserted)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        logger.warning(f"Invalid Parquet ingest request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Parquet ingest error: {e}")
        raise HTTPException(status_code=500, detail=f"Parquet ingestion failed: {str(e)}")


@app.post("/api/ingest/document", response_model=DocumentIngestResponse, tags=["Ingestion"])
def ingest_document(
    payload: DocumentIngestRequest,
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """Ingest a lawyer's document (PDF with OCR, DOCX, EML, TXT, MD) via KruschNexus."""
    try:
        report = ingest_matter_document(
            file_path=payload.file_path,
            matter_id=payload.matter_id,
            doc_type=payload.doc_type,
            db=db
        )
        return DocumentIngestResponse(**report)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        logger.warning(f"Invalid document ingest request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Document ingest error: {e}")
        raise HTTPException(status_code=500, detail=f"Document ingestion failed: {str(e)}")


@app.post("/api/ingest/upload", response_model=DocumentIngestResponse, tags=["Ingestion"])
async def upload_document(
    file: UploadFile = File(...),
    matter_id: Optional[int] = Form(None),
    doc_type: str = Form("matter_facts"),
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """Directly upload a lawyer's document via KruschNexus's parsing and chunking pipeline."""
    try:
        contents = await file.read()
        report = ingest_uploaded_matter_file(
            file_bytes=contents,
            filename=file.filename or "uploaded_document",
            matter_id=matter_id,
            doc_type=doc_type,
            db=db
        )
        return DocumentIngestResponse(**report)
    except ValueError as e:
        logger.warning(f"Invalid uploaded document request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Document upload ingest error: {e}")
        raise HTTPException(status_code=500, detail=f"Document upload ingestion failed: {str(e)}")


@app.post("/api/ingest/parquet/async", response_model=AsyncIngestResponse, status_code=202, tags=["Ingestion"])
def ingest_parquet_async(
    payload: ParquetIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """Queue asynchronous background ingestion of a LOCUS-v1 Parquet file."""
    job_id = str(uuid.uuid4())
    job = IngestJob(
        id=job_id,
        file_path=payload.file_path,
        status="pending",
        stage="queued"
    )
    db.add(job)
    db.commit()

    background_tasks.add_task(process_parquet_job, job_id, payload.file_path, payload.limit)
    return AsyncIngestResponse(job_id=job_id, status="pending", file_path=payload.file_path)


@app.get("/api/ingest/jobs/{job_id}", response_model=IngestJobStatusResponse, tags=["Ingestion"])
def get_ingest_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """Check status and progress telemetry of a background Parquet ingestion job."""
    job = db.query(IngestJob).filter(IngestJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Ingest job '{job_id}' not found")

    return IngestJobStatusResponse(
        id=job.id,
        status=job.status,
        file_path=job.file_path,
        raw_file_hash=job.raw_file_hash,
        stage=job.stage or "queued",
        total_rows=job.total_rows,
        processed_rows=job.processed_rows,
        inserted_records=job.inserted_records,
        last_committed_offset=job.last_committed_offset,
        chunks_total=job.chunks_total,
        chunks_embedded=job.chunks_embedded,
        error_message=job.error_message,
        created_at=job.created_at.isoformat() if job.created_at else "",
        updated_at=job.updated_at.isoformat() if job.updated_at else None
    )


@app.get("/api/consult", response_model=ConsultResponse, tags=["Consultation"])
def consult_matter(
    case_id: int = Query(..., description="ID of the logged matter to consult"),
    limit: Optional[int] = Query(5, ge=1, le=20, description="Maximum number of laws to retrieve"),
    state: Optional[str] = Query(None, description="Two-letter state filter (e.g. CA)"),
    city: Optional[str] = Query(None, description="City or county filter (e.g. Oakland)"),
    topic: Optional[str] = Query(None, description="Topic filter (e.g. Housing)"),
    request: Request = None,
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """
    Perform hybrid vector + lexical matching against local laws, execute assertion-level grounding,
    and generate an auditable legal brief with side-by-side claim support spans.
    """
    start_time = time.time()
    case = db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Matter #{case_id} not found")

    if not case.embedding:
        try:
            logger.info(f"Generating missing embedding on-the-fly for matter #{case_id}...")
            case.embedding = get_embedding(case.facts)
            db.commit()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Ollama embedding failure: {str(e)}")

    try:
        matched_laws = retrieve_laws(
            query_vector=case.embedding,
            text_query=case.facts,
            limit=limit,
            state_filter=state,
            city_filter=city,
            topic_filter=topic,
            db_session=db
        )
    except RetrievalError as e:
        logger.error(f"Statutory retrieval failure for matter #{case_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database retrieval failure: {str(e)}")

    # Generate analysis and run assertion grounding (flexible to tuple or mocked string)
    res = generate_legal_analysis(
        case_facts=case.facts,
        case_title=case.title,
        laws=matched_laws,
        case_id=case.id,
        db_session=db
    )
    if isinstance(res, tuple):
        analysis_text = res[0]
        stats = res[1] if len(res) > 1 else {}
        claim_records = res[2] if len(res) > 2 else []
    else:
        analysis_text = str(res)
        is_grounded, claim_records, notice, stats = verify_assertion_grounding(analysis_text, matched_laws)

    elapsed_ms = int((time.time() - start_time) * 1000)
    verdict = "PASS" if stats.get("pass_rate", 100.0) == 100.0 else ("FAIL" if stats.get("invented_citations", 0) > 0 else "WARNING")

    client_ip = request.client.host if request and request.client else None
    sec_ids = [law_item.get("section") or str(law_item.get("id")) for law_item in matched_laws]
    log_audit_event(
        db, action="consult", actor_key=_auth,
        client_ip=client_ip, matter_id=case.id,
        retrieved_section_ids=sec_ids,
        grounding_verdict=verdict,
        duration_ms=elapsed_ms
    )

    _, spotted = expand_legal_query(case.facts)
    spotted_models = [SpottedIssue(**s) for s in spotted]

    return ConsultResponse(
        case=CaseSummary(id=case.id, title=case.title, facts=case.facts),
        retrieved_laws=[LawItem(**law_item) for law_item in matched_laws],
        analysis=analysis_text,
        disclaimer=UPL_DISCLAIMER,
        review_required=True,
        provisional_work_product=True,
        grounding_stats=GroundingStats(**stats) if stats else None,
        claims_audit=[ClaimRecord(**c) for c in claim_records],
        spotted_issues=spotted_models
    )


@app.get("/api/cases/{case_id}/evidence", response_model=List[MatterEvidenceItem], tags=["Discovery & Evidence"])
@app.get("/api/matters/{case_id}/evidence", response_model=List[MatterEvidenceItem], tags=["Discovery & Evidence"])
def get_matter_evidence(
    case_id: int,
    q: Optional[str] = Query(None, description="Semantic or keyword query within matter discovery"),
    limit: int = Query(10, ge=1, le=100, description="Max discovery chunks to retrieve"),
    doc_type: Optional[str] = Query(None, description="Optional doc_type filter (e.g. lease, notice, evidence)"),
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """
    Search client discovery documents, exhibits, and uploaded records strictly within the designated matter.
    Prevents cross-matter data contamination.
    """
    case = db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Matter #{case_id} not found.")

    try:
        results = retrieve_matter_evidence(
            matter_id=case_id,
            text_query=q,
            limit=limit,
            doc_type=doc_type,
            db_session=db
        )
        return [MatterEvidenceItem(**r) for r in results]
    except Exception as e:
        logger.error(f"Error querying matter evidence: {e}")
        raise HTTPException(status_code=500, detail=f"Evidence retrieval error: {str(e)}")


@app.post("/api/consult/export/docx", tags=["Consult & Synthesis"])
def export_consult_docx(
    payload: ExportDocxRequest,
    _auth: Optional[str] = Depends(verify_api_key)
):
    """Generate a court/client-ready Word (.docx) document from consult analysis and audit data."""
    try:
        from .export import generate_brief_docx
        docx_bytes = generate_brief_docx(
            brief_content=payload.brief_content,
            matter_title=payload.matter_title,
            matter_number=payload.matter_number,
            client_name=payload.client_name,
            claims_audit=payload.claims_audit,
            retrieved_laws=payload.retrieved_laws,
            disclaimer=UPL_DISCLAIMER
        )
        safe_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', payload.matter_title[:30])
        filename = f"KruschLaw_Brief_{safe_title}.docx"
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Error generating DOCX export: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate DOCX export: {e}")


@app.get("/api/consult/{case_id}/export/docx", tags=["Consult & Synthesis"])
def export_case_docx(
    case_id: int,
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """Export the latest consultation brief and grounding audit for a matter as Word (.docx)."""
    case = db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Matter #{case_id} not found.")

    report = db.query(GroundingReport).filter(GroundingReport.case_id == case_id).order_by(GroundingReport.created_at.desc()).first()
    claims_audit = json.loads(report.claims_json) if (report and report.claims_json) else []

    matched_laws = retrieve_laws(query_vector=case.embedding, text_query=case.facts, limit=5, db_session=db)

    brief_text = (
        f"### Executive Summary\nPreliminary legal evaluation for Matter #{case.id}: {case.title}.\n\n"
        f"### Factual Matrix\n{case.facts}\n\n"
        f"### Governing Authorities\nPrimary authorities identified in the sovereign graph are detailed in the appendix."
    )

    try:
        from .export import generate_brief_docx
        docx_bytes = generate_brief_docx(
            brief_content=brief_text,
            matter_title=case.title,
            matter_number=case.matter_number,
            client_name=case.client_name,
            claims_audit=claims_audit,
            retrieved_laws=matched_laws,
            disclaimer=UPL_DISCLAIMER
        )
        safe_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', case.title[:30])
        filename = f"KruschLaw_Brief_Matter_{case.id}_{safe_title}.docx"
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Error generating DOCX export for matter #{case_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate DOCX export: {e}")
