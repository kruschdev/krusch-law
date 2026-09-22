import logging
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from .config import settings
from .db import init_db, SessionLocal, Case
from .rag import get_embedding, retrieve_laws, generate_legal_analysis, UPL_DISCLAIMER
from .ingest import ingest_mock_data, ingest_locus_parquet

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("kruschlaw.api")

app = FastAPI(
    title="KruschLaw API",
    description="Air-Gapped, Privacy-First Legal RAG & Ordinance Intelligence Engine",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.on_event("startup")
def on_startup():
    """Initialize database schemas and extensions on service boot."""
    logger.info("Initializing KruschLaw database schemas...")
    try:
        init_db()
        logger.info("Database schemas initialized successfully.")
    except Exception as e:
        logger.error(f"Error during database startup initialization: {e}")


# --- Pydantic Request & Response Schemas ---

class CaseCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255, description="Short title of the client matter")
    description: Optional[str] = Field(None, max_length=500, description="Brief classification, tags, or client reference")
    facts: str = Field(..., min_length=10, description="Detailed narrative of facts and circumstances")


class CaseResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    facts: str
    created_at: str

    class Config:
        from_attributes = True


class ParquetIngestRequest(BaseModel):
    file_path: str = Field(..., description="Absolute path to a LOCUS-v1 or compatible Parquet file")
    limit: Optional[int] = Field(100, ge=1, le=10000, description="Maximum number of sections to ingest")


class IngestResponse(BaseModel):
    status: str
    inserted_records: int


class LawItem(BaseModel):
    id: int
    jurisdiction: str
    state: Optional[str] = None
    city_or_county: Optional[str] = None
    title: Optional[str] = None
    section: Optional[str] = None
    content: str
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
    """Health check endpoint for container probes and uptime monitors."""
    return {
        "status": "healthy",
        "service": "kruschlaw-backend",
        "air_gapped": True,
        "models": {
            "embeddings": settings.OLLAMA_EMBED_MODEL,
            "reasoning": settings.OLLAMA_LLM_MODEL
        }
    }


@app.post("/api/cases", response_model=CaseResponse, status_code=201, tags=["Cases"])
def create_case(payload: CaseCreate, db: Session = Depends(get_db)):
    """
    Log a new legal matter. Automatically generates a 1024-dim embedding of the factual narrative
    via the local Ollama node.
    """
    try:
        logger.info(f"Generating embedding for matter: '{payload.title}'...")
        vector = get_embedding(payload.facts)

        new_case = Case(
            title=payload.title,
            description=payload.description,
            facts=payload.facts,
            embedding=vector
        )
        db.add(new_case)
        db.commit()
        db.refresh(new_case)

        return CaseResponse(
            id=new_case.id,
            title=new_case.title,
            description=new_case.description,
            facts=new_case.facts,
            created_at=new_case.created_at.isoformat() if new_case.created_at else ""
        )
    except ConnectionError as e:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating case: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to record matter: {str(e)}")


@app.get("/api/cases", response_model=List[CaseResponse], tags=["Cases"])
def get_cases(db: Session = Depends(get_db)):
    """Retrieve all previously logged client matters, ordered by creation date."""
    try:
        cases = db.query(Case).order_by(Case.created_at.desc()).all()
        return [
            CaseResponse(
                id=c.id,
                title=c.title,
                description=c.description,
                facts=c.facts,
                created_at=c.created_at.isoformat() if c.created_at else ""
            ) for c in cases
        ]
    except Exception as e:
        logger.error(f"Error fetching cases: {e}")
        raise HTTPException(status_code=500, detail="Database retrieval error")


@app.post("/api/ingest/mock", response_model=IngestResponse, tags=["Ingestion"])
def ingest_mock_ordinances(db: Session = Depends(get_db)):
    """Seed the database with verified California municipal ordinances and tenant rights statutes."""
    try:
        inserted = ingest_mock_data(db)
        return IngestResponse(status="success", inserted_records=inserted)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Mock ingestion error: {e}")
        raise HTTPException(status_code=500, detail=f"Mock ingestion failed: {str(e)}")


@app.post("/api/ingest/parquet", response_model=IngestResponse, tags=["Ingestion"])
def ingest_parquet(payload: ParquetIngestRequest, db: Session = Depends(get_db)):
    """Ingest municipal ordinances from an on-premise LOCUS-v1 Parquet file."""
    try:
        inserted = ingest_locus_parquet(payload.file_path, db=db, limit=payload.limit)
        return IngestResponse(status="success", inserted_records=inserted)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Parquet ingest error: {e}")
        raise HTTPException(status_code=500, detail=f"Parquet ingestion failed: {str(e)}")


@app.get("/api/consult", response_model=ConsultResponse, tags=["Consultation"])
def consult_matter(
    case_id: int = Query(..., description="ID of the logged matter to consult"),
    limit: Optional[int] = Query(5, ge=1, le=20, description="Maximum number of laws to retrieve"),
    state: Optional[str] = Query(None, description="Two-letter state filter (e.g. CA)"),
    city: Optional[str] = Query(None, description="City or county filter (e.g. Oakland)"),
    db: Session = Depends(get_db)
):
    """
    Perform semantic vector matching against local laws and generate a 4-part legal analysis brief
    grounded strictly in retrieved statutes.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
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

    # Retrieve vector matches
    matched_laws = retrieve_laws(
        query_vector=case.embedding,
        limit=limit,
        state_filter=state,
        city_filter=city,
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
