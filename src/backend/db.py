import os
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, UniqueConstraint, func, text
from sqlalchemy.orm import declarative_base, sessionmaker
from pgvector.sqlalchemy import Vector

from .config import settings

# Configure engine based on dialect
engine_kwargs = {}
if settings.is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
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
    """Statutory, municipal ordinance, or regulatory provision with vector embedding and hybrid search metadata."""
    __tablename__ = "laws_vectors"
    __table_args__ = (
        UniqueConstraint("jurisdiction", "state", "city", "section", "chunk_index", name="uq_law_section_chunk"),
    )

    id = Column(Integer, primary_key=True, index=True)
    jurisdiction = Column(String(100), nullable=False, index=True)  # e.g., "U.S. Code", "Oakland Municipal Code"
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
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=True)


class IngestJob(Base):
    """Tracks asynchronous background ingestion jobs for LOCUS Parquet corpora."""
    __tablename__ = "ingest_jobs"

    id = Column(String(36), primary_key=True)
    file_path = Column(String(500), nullable=False)
    status = Column(String(20), default="pending", nullable=False)  # pending, running, completed, failed
    total_rows = Column(Integer, default=0, nullable=False)
    processed_rows = Column(Integer, default=0, nullable=False)
    inserted_records = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
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
            # Functional GIN index for hybrid full-text lexical search
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS laws_vectors_search_tsv_idx
                ON laws_vectors USING gin (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(section, '') || ' ' || coalesce(content, '')));
            """))
            conn.commit()

