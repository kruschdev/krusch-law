import os
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, func, text
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
    """Client matter or legal inquiry with associated facts and vector embedding."""
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    facts = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=True)


class LawVector(Base):
    """Statutory, municipal ordinance, or regulatory provision with vector embedding."""
    __tablename__ = "laws_vectors"

    id = Column(Integer, primary_key=True, index=True)
    jurisdiction = Column(String(100), nullable=False, index=True)  # e.g., "U.S. Code", "Oakland Municipal Code"
    state = Column(String(50), nullable=True, index=True)           # e.g., "CA"
    city_or_county = Column(String(100), nullable=True, index=True) # e.g., "Oakland", "San Francisco"
    title = Column(String(255), nullable=True)                      # e.g., "Rent Adjustment Program"
    section = Column(String(100), nullable=True)                    # e.g., "Section 8.22.030"
    content = Column(Text, nullable=False)                          # Statutory or ordinance body text
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=True)


def init_db(target_engine=None):
    """Initialize database tables, pgvector extension, and HNSW indexes if PostgreSQL."""
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
            conn.commit()

