import uuid
import logging
from contextlib import asynccontextmanager
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Query, Security, BackgroundTasks, status
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from .config import settings, is_loopback_or_private_host
from .db import init_db, SessionLocal, Case, IngestJob
from .rag import get_embedding, retrieve_laws, generate_legal_analysis, UPL_DISCLAIMER
from .ingest import ingest_mock_data, ingest_locus_parquet, process_parquet_job

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
    version="0.2.0-dev",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> Optional[str]:
    """Verify optional API Key authentication. Enforced if API_KEY is configured in settings."""
    if not settings.API_KEY:
        return None  # Unauthenticated in local development mode
    if not api_key or api_key.strip() != settings.API_KEY.strip():
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Missing or invalid X-API-Key header. Client matter data is protected."
        )
    return api_key


# Enable CORS restricted to configured internal origins
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
    id: int
    matter_number: Optional[str] = None
    client_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    facts: str
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


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
    total_rows: int
    processed_rows: int
    inserted_records: int
    error_message: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None


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


class CaseSummary(BaseModel):
    id: int
    title: str
    facts: str


class ConsultResponse(BaseModel):
    case: CaseSummary
    retrieved_laws: List[LawItem]
    analysis: str
    disclaimer: str


# --- API Endpoints ---

@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint with verified runtime security and inference inspection."""
    ollama_local = is_loopback_or_private_host(settings.OLLAMA_BASE_URL)
    embed_local = is_loopback_or_private_host(settings.OLLAMA_EMBED_HOST)
    return {
        "status": "healthy",
        "service": "kruschlaw-backend",
        "version": "0.2.0-dev",
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
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """Retrieve all non-deleted client matters, ordered by creation date."""
    try:
        cases = db.query(Case).filter(Case.is_deleted == False).order_by(Case.created_at.desc()).all()
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
    case = db.query(Case).filter(Case.id == case_id, Case.is_deleted == False).first()
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
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """Update matter details. If facts narrative is modified, recomputes vector embedding."""
    case = db.query(Case).filter(Case.id == case_id, Case.is_deleted == False).first()
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
        if payload.facts is not None and payload.facts.strip() != case.facts.strip():
            case.facts = payload.facts
            logger.info(f"Recomputing embedding for updated matter #{case_id}...")
            case.embedding = get_embedding(payload.facts)

        db.commit()
        db.refresh(case)

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


@app.delete("/api/cases/{case_id}", status_code=200, tags=["Cases"])
def delete_case(
    case_id: int,
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """Soft-delete a matter record from the active portfolio."""
    case = db.query(Case).filter(Case.id == case_id, Case.is_deleted == False).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Matter #{case_id} not found")
    case.is_deleted = True
    db.commit()
    return {"status": "deleted", "id": case_id}


@app.get("/api/laws", response_model=List[LawItem], tags=["Statutes & Ordinances"])
def search_laws(
    q: Optional[str] = Query(None, description="Natural language search query or statutory keywords"),
    state: Optional[str] = Query(None, description="Two-letter state filter (e.g. CA)"),
    city: Optional[str] = Query(None, description="City or county filter (e.g. Oakland)"),
    topic: Optional[str] = Query(None, description="Topic classification filter"),
    limit: Optional[int] = Query(10, ge=1, le=50, description="Max results to return"),
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """
    Explore and search ingested statutes, municipal codes, and ordinances.
    Uses hybrid search (full-text lexical + pgvector cosine similarity).
    """
    try:
        results = retrieve_laws(
            text_query=q,
            limit=limit,
            state_filter=state,
            city_filter=city,
            topic_filter=topic,
            db_session=db
        )
        return [LawItem(**r) for r in results]
    except Exception as e:
        logger.error(f"Error exploring laws: {e}")
        raise HTTPException(status_code=500, detail=f"Statutory search failed: {str(e)}")


@app.post("/api/ingest/mock", response_model=IngestResponse, tags=["Ingestion"])
def ingest_mock_ordinances(
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """Seed the database with paraphrased California demo fixtures for testing."""
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


@app.post("/api/ingest/parquet/async", response_model=AsyncIngestResponse, status_code=202, tags=["Ingestion"])
def ingest_parquet_async(
    payload: ParquetIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """
    Queue asynchronous background ingestion of a LOCUS-v1 Parquet file.
    Returns a job_id to monitor progress.
    """
    job_id = str(uuid.uuid4())
    job = IngestJob(
        id=job_id,
        file_path=payload.file_path,
        status="pending"
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
    """Check status and progress of a background Parquet ingestion job."""
    job = db.query(IngestJob).filter(IngestJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Ingest job '{job_id}' not found")

    return IngestJobStatusResponse(
        id=job.id,
        status=job.status,
        file_path=job.file_path,
        total_rows=job.total_rows,
        processed_rows=job.processed_rows,
        inserted_records=job.inserted_records,
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
    db: Session = Depends(get_db),
    _auth: Optional[str] = Depends(verify_api_key)
):
    """
    Perform hybrid vector + lexical matching against local laws and generate a 4-part legal brief
    grounded strictly in retrieved authorities with citation verification.
    """
    case = db.query(Case).filter(Case.id == case_id, Case.is_deleted == False).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Matter #{case_id} not found")

    # If missing vector embedding, generate one on-demand
    if not case.embedding:
        try:
            logger.info(f"Generating missing embedding on-the-fly for matter #{case_id}...")
            case.embedding = get_embedding(case.facts)
            db.commit()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Ollama embedding failure: {str(e)}")

    # Retrieve matching laws using hybrid search
    matched_laws = retrieve_laws(
        query_vector=case.embedding,
        text_query=case.facts,
        limit=limit,
        state_filter=state,
        city_filter=city,
        topic_filter=topic,
        db_session=db
    )

    # Generate structured analysis
    analysis_text = generate_legal_analysis(
        case_facts=case.facts,
        case_title=case.title,
        laws=matched_laws
    )

    return ConsultResponse(
        case=CaseSummary(id=case.id, title=case.title, facts=case.facts),
        retrieved_laws=[LawItem(**l) for l in matched_laws],
        analysis=analysis_text,
        disclaimer=UPL_DISCLAIMER
    )
