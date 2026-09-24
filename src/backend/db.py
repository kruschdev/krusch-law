import uuid
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime,
    Boolean, UniqueConstraint, func, text, Float
)
from sqlalchemy.orm import declarative_base, sessionmaker

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    from sqlalchemy.types import UserDefinedType
    import json
    class Vector(UserDefinedType):
        cache_ok = True
        def __init__(self, dim=1024):
            self.dim = dim
        def get_col_spec(self, **kw):
            return "TEXT"
        def bind_processor(self, dialect):
            def process(value):
                return json.dumps(value) if isinstance(value, list) else value
            return process
        def result_processor(self, dialect, coltype):
            def process(value):
                if isinstance(value, str):
                    try:
                        return json.loads(value)
                    except Exception:
                        return value
                return value
            return process

from sqlalchemy import event
from sqlalchemy.engine import Engine
from .config import settings

# Configure engine based on dialect
engine_kwargs = {}
if settings.is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

try:
    engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
except (ImportError, Exception) as exc:
    import logging
    logging.getLogger("kruschlaw.db").warning(
        f"Database engine initialization failed ({exc}). Falling back to local SQLite engine."
    )
    engine = create_engine("sqlite:///kruschlaw.db", connect_args={"check_same_thread": False})


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enforce foreign key constraints on SQLite connections."""
    if "sqlite" in str(type(dbapi_connection)).lower() or hasattr(dbapi_connection, "cursor"):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        except Exception:
            pass
        finally:
            cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Case(Base):
    """Client matter or legal inquiry with associated facts, metadata, and vector embedding."""
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    matter_number = Column(String(50), nullable=True, index=True)
    client_name = Column(String(255), nullable=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    facts = Column(Text, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=True)


class LawVector(Base):
    """
    Statutory, municipal ordinance, or regulatory provision in a hierarchical, versioned legal graph
    with dense vector embedding and hybrid search metadata.
    """
    __tablename__ = "laws_vectors"
    __table_args__ = (
        UniqueConstraint("jurisdiction", "state", "city", "section", "chunk_index", "source_hash", name="uq_law_section_hash"),
    )

    id = Column(Integer, primary_key=True, index=True)
    jurisdiction = Column(String(100), nullable=False, index=True)  # e.g., "California Civil Code", "Oakland Municipal Code"
    state = Column(String(50), nullable=True, index=True)           # e.g., "CA"
    city = Column(String(100), nullable=True, index=True)            # e.g., "Oakland"
    county = Column(String(100), nullable=True, index=True)          # e.g., "Alameda County"
    city_or_county = Column(String(100), nullable=True, index=True) # Backwards-compatible display string
    topic = Column(String(100), nullable=True, index=True)           # e.g., "Housing & Rent", "Zoning"
    title = Column(String(255), nullable=True)                      # e.g., "Rent Adjustment Program"
    section = Column(String(100), nullable=True, index=True)        # e.g., "Section 8.22.030"
    content = Column(Text, nullable=False)                          # Statutory or ordinance body text / chunk
    source_header = Column(Text, nullable=True)                     # Full source header from LOCUS / reporter
    source_hash = Column(String(64), nullable=True, index=True)     # SHA-256 hash of content chunk for deduplication
    chunk_index = Column(Integer, default=0, nullable=False)        # Chunk index within section
    is_substantive = Column(Boolean, default=True, nullable=False)  # False for TOC, editorial notes, enactments
    tags = Column(Text, nullable=True)                              # JSON list of semantic tags
    summary = Column(Text, nullable=True)                           # 1-sentence legal micro-digest
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=True)

    # --- Hierarchy & Legal Graph Structure ---
    parent_id = Column(Integer, nullable=True, index=True)          # Foreign key or self-referential ID
    parent_section = Column(String(100), nullable=True, index=True) # e.g. "Chapter 8.22" or "Section 8.22.030"
    hierarchy_level = Column(String(50), default="section", nullable=False, index=True) # code, title, chapter, article, section, subsection, definitions, exceptions, penalties
    definitions_ref = Column(String(100), nullable=True)            # Reference to section defining controlling terms (e.g. "Section 8.22.020")
    exceptions_ref = Column(String(100), nullable=True)             # Reference to explicit statutory exception provisions

    # --- Temporal Validity & Authority Hierarchy ---
    authority_class = Column(String(50), default="municipal_ordinance", nullable=False, index=True)
    # Options: "controlling_statute", "implementing_regulation", "municipal_ordinance", "secondary_commentary"
    instrument_type = Column(String(50), default="statute", nullable=False, index=True)
    # Options: "statute", "regulation", "ordinance", "opinion", "commentary"
    jurisdiction_level = Column(String(50), default="city", nullable=True, index=True)
    # Options: "federal", "state", "county", "city", "agency"
    effective_date = Column(DateTime(timezone=True), nullable=True) # Date statute became in force
    effective_from = Column(DateTime(timezone=True), nullable=True) # Synonym / formal start date
    effective_to = Column(DateTime(timezone=True), nullable=True)   # Formal sunset / amendment date
    amended_date = Column(DateTime(timezone=True), nullable=True)   # Date of most recent formal statutory amendment
    status = Column(String(50), default="enacted", nullable=False, index=True)
    # Options: "enacted", "amended", "repealed", "sunset", "enjoined"
    repealed = Column(Boolean, default=False, nullable=False, index=True) # True if repealed or superseded
    preempted_by = Column(String(255), nullable=True)               # e.g. "Cal. Civ. Code § 1946.2 (California Tenant Protection Act)"
    preempts = Column(Text, nullable=True)                          # JSON list of citations preempted by this node
    implements_ref = Column(String(255), nullable=True)             # Reference to parent statutory mandate
    defines_terms = Column(Text, nullable=True)                     # JSON list of terms formally defined
    exception_to = Column(String(255), nullable=True)               # Section for which this node is an exception
    applies_if = Column(Text, nullable=True)                        # JSON dict of spatial & fact preconditions
    superseded_by_id = Column(Integer, nullable=True)               # ID of amendment replacement node
    source_url = Column(String(500), nullable=True)                 # Official legal reporter / municipal code publishing URL


class GroundingReport(Base):
    """
    Immutable assertion-level grounding audit report tracking verified propositions,
    supporting textual excerpts, and detected failure modes across the 5-class taxonomy:
    (entailed, contradicted, exception_applies, insufficient_context, not_in_corpus).
    """
    __tablename__ = "grounding_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    total_claims = Column(Integer, default=0, nullable=False)
    supported_claims = Column(Integer, default=0, nullable=False)
    unsupported_claims = Column(Integer, default=0, nullable=False)
    invented_citations = Column(Integer, default=0, nullable=False)
    stale_law_citations = Column(Integer, default=0, nullable=False)
    contradicted_claims = Column(Integer, default=0, nullable=False)
    exception_applies_claims = Column(Integer, default=0, nullable=False)
    insufficient_context_claims = Column(Integer, default=0, nullable=False)
    not_in_corpus_claims = Column(Integer, default=0, nullable=False)
    refused_claims_count = Column(Integer, default=0, nullable=False)
    pass_rate = Column(Float, default=100.0, nullable=False)
    claims_json = Column(Text, nullable=False)                      # JSON list of verified claims & spans
    verified_draft = Column(Text, nullable=True)                    # Redacted/annotated draft with per-claim refusal
    advisory_markdown = Column(Text, nullable=True)


class AuditLog(Base):
    """
    Per-action regulatory and security audit trail.
    Tracks queries, matter consultations, retrieved statutory IDs, and model versions.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    actor_key_hash = Column(String(64), nullable=True, index=True)  # SHA-256 hash of API key
    client_ip = Column(String(50), nullable=True)
    action = Column(String(50), nullable=False, index=True)         # consult, search, ingest, delete_matter, purge_matter, export
    matter_id = Column(Integer, nullable=True, index=True)
    retrieved_section_ids = Column(Text, nullable=True)             # JSON list or comma-separated IDs
    model_name = Column(String(100), nullable=True)
    model_version = Column(String(50), nullable=True)
    prompt_hash = Column(String(64), nullable=True)
    grounding_verdict = Column(String(50), nullable=True)           # PASS, WARNING, FAIL
    duration_ms = Column(Integer, nullable=True)


class IngestJob(Base):
    """
    Persistent, crash-resilient queue job for statutory corpora ingestion.
    Supports transactional resumption, byte-level dedup, and stage telemetry.
    """
    __tablename__ = "ingest_jobs"

    id = Column(String(36), primary_key=True)
    file_path = Column(String(500), nullable=False)
    raw_file_hash = Column(String(64), nullable=True, index=True)   # SHA-256 of raw source bytes
    status = Column(String(20), default="pending", nullable=False, index=True)  # pending, running, completed, failed, cancelled
    stage = Column(String(50), default="queued", nullable=False)    # queued, validating, parsing, chunking, embedding, indexing, completed
    total_rows = Column(Integer, default=0, nullable=False)
    processed_rows = Column(Integer, default=0, nullable=False)
    inserted_records = Column(Integer, default=0, nullable=False)
    last_committed_offset = Column(Integer, default=0, nullable=False)
    worker_id = Column(String(100), nullable=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    ocr_pages = Column(Integer, default=0, nullable=False)
    total_pages = Column(Integer, default=0, nullable=False)
    chunks_total = Column(Integer, default=0, nullable=False)
    chunks_embedded = Column(Integer, default=0, nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MatterEvidence(Base):
    """
    Client discovery and case evidence documents (leases, notices, emails).
    Strictly isolated from the public laws_vectors table to prevent cross-matter fact contamination.
    """
    __tablename__ = "matter_evidence"

    id = Column(Integer, primary_key=True, index=True)
    matter_id = Column(Integer, nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    doc_type = Column(String(50), default="matter_facts", nullable=False) # matter_facts, evidence, lease, notice
    page_number = Column(Integer, nullable=True)
    section_locator = Column(String(100), nullable=True)
    chunk_index = Column(Integer, default=0, nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(Text, nullable=True)                              # JSON list of semantic tags (e.g. ["security-deposit", "ab-12"])
    summary = Column(Text, nullable=True)                           # 1-sentence legal micro-digest
    doctrine = Column(String(100), nullable=True, index=True)       # Legal doctrine classification (e.g. "Security Deposits")
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StatuteCodeTraceability(Base):
    """
    Manually curated statute-to-code traceability table with review dates and attorney attestations.
    Replaces fragile docstring/comment parsing with deterministic binding invariants.
    """
    __tablename__ = "statute_code_traceability"

    id = Column(Integer, primary_key=True, index=True)
    statute_id = Column(String(100), nullable=False, index=True)         # e.g., "Cal. Civ. Code § 1950.5(c)"
    symbol_id = Column(String(255), nullable=False, index=True)           # e.g., "deposit_validator.validate_deposit_cap"
    repository = Column(String(100), nullable=False, default="krusch-law")
    file_path = Column(String(255), nullable=False)
    doctrine = Column(String(100), nullable=False, default="Security Deposits") # Security Deposits, Habitability, Just Cause
    status = Column(String(50), nullable=False, default="manually_verified")   # manually_verified, suggested_candidate, deprecated
    reviewed_by = Column(String(100), nullable=True)                     # e.g., "attorney:krusch"
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    statutory_digest = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


def init_db(target_engine=None):
    """Initialize database tables, pgvector extension, HNSW vector indexes, and GIN full-text index."""
    eng = target_engine or engine
    dialect_name = eng.dialect.name

    if dialect_name == "postgresql":
        with eng.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()

    Base.metadata.create_all(bind=eng)

    if dialect_name == "postgresql":
        with eng.connect() as conn:
            # Create HNSW cosine indexes for sub-millisecond retrieval on large statutory dumps
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS laws_vectors_embedding_hnsw_idx
                ON laws_vectors USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS cases_embedding_hnsw_idx
                ON cases USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS matter_evidence_embedding_hnsw_idx
                ON matter_evidence USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """))
            # Functional GIN index for hybrid full-text lexical search
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS laws_vectors_search_tsv_idx
                ON laws_vectors USING gin (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(section, '') || ' ' || coalesce(content, '')));
            """))
            # Ensure semantic tagging columns exist
            conn.execute(text("ALTER TABLE matter_evidence ADD COLUMN IF NOT EXISTS tags TEXT;"))
            conn.execute(text("ALTER TABLE matter_evidence ADD COLUMN IF NOT EXISTS summary TEXT;"))
            conn.execute(text("ALTER TABLE matter_evidence ADD COLUMN IF NOT EXISTS doctrine VARCHAR(100);"))
            conn.execute(text("ALTER TABLE laws_vectors ADD COLUMN IF NOT EXISTS tags TEXT;"))
            conn.execute(text("ALTER TABLE laws_vectors ADD COLUMN IF NOT EXISTS summary TEXT;"))
            conn.commit()
