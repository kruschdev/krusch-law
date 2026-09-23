#!/usr/bin/env python3
"""
KruschLaw Ingestion Worker.
Durable, crash-resilient worker process polling the IngestJob queue using
PostgreSQL SKIP LOCKED (or atomic SQLite transaction lock) to execute asynchronous
statutory corpus ingestion without dropping or double-processing batches.
"""

import os
import time
import logging
import argparse
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import SessionLocal, IngestJob
from .ingest import process_parquet_job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Worker:%(process)d] %(levelname)s: %(message)s"
)
logger = logging.getLogger("kruschlaw.worker")


def claim_next_job(db: Session, worker_id: str) -> Optional[IngestJob]:
    """
    Atomically claim the next pending ingestion job from the queue.
    Uses 'FOR UPDATE SKIP LOCKED' on PostgreSQL to prevent race conditions across workers.
    """
    is_sqlite = db.bind.dialect.name == "sqlite"
    if is_sqlite:
        job = db.query(IngestJob).filter(IngestJob.status == "pending").order_by(IngestJob.created_at.asc()).first()
        if job:
            job.status = "running"
            job.worker_id = worker_id
            job.heartbeat_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(job)
            return job
        return None
    else:
        # PostgreSQL SKIP LOCKED
        sql = text("""
            SELECT id FROM ingest_jobs
            WHERE status = 'pending'
            ORDER BY created_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        """)
        row = db.execute(sql).fetchone()
        if row:
            job_id = row[0]
            job = db.query(IngestJob).filter(IngestJob.id == job_id).first()
            if job:
                job.status = "running"
                job.worker_id = worker_id
                job.heartbeat_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(job)
                return job
        return None


def run_worker_loop(poll_interval: float = 2.0, run_once: bool = False):
    """Main worker processing loop."""
    worker_id = f"worker-{os.getpid()}-{int(time.time())}"
    logger.info(f"Ingestion worker '{worker_id}' started. Polling every {poll_interval}s...")

    while True:
        db = SessionLocal()
        try:
            job = claim_next_job(db, worker_id)
            if job:
                logger.info(f"Claimed job {job.id} for file: {job.file_path}")
                process_parquet_job(job.id, job.file_path, limit=250)
            else:
                if run_once:
                    logger.info("No pending jobs found. Exiting (--once).")
                    break
                time.sleep(poll_interval)
        except Exception as e:
            logger.error(f"Worker iteration error: {e}", exc_info=True)
            time.sleep(poll_interval)
        finally:
            db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KruschLaw Background Ingestion Worker")
    parser.add_argument("--once", action="store_true", help="Process at most one job and exit")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Seconds between queue checks")
    args = parser.parse_args()

    run_worker_loop(poll_interval=args.poll_interval, run_once=args.once)
