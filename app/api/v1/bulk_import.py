"""CSV bulk import API — POST /api/v1/bulk-import/csv"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import get_current_client_user
from app.connectors.csv_importer import parse_csv_rows
from app.db.models import BulkImportJob, Client
from app.db.session import SessionLocal, get_db
from app.dependencies.auth import require_api_key
from app.services.unified_ingestion import process_incoming_message
from app.utils.logging import get_logger

router = APIRouter(prefix="/api/v1/bulk-import", tags=["bulk-import"])
logger = get_logger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _process_job(job_id: str, content: bytes, client_id: str) -> None:
    """Background task: parse CSV rows and ingest each message."""
    db = SessionLocal()
    try:
        job = db.query(BulkImportJob).filter(BulkImportJob.id == uuid.UUID(job_id)).first()
        if job is None:
            return

        try:
            messages, parse_errors = parse_csv_rows(content, client_id)
        except ValueError as exc:
            job.status = "failed"
            job.error_log = [{"row": 0, "reason": str(exc)}]
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        job.total_rows = len(messages) + len(parse_errors)
        job.failed_rows = len(parse_errors)
        job.error_log = parse_errors
        db.commit()

        imported = 0
        for msg in messages:
            try:
                result = process_incoming_message(db, msg)
                db.commit()
                if result.get("status") not in ("duplicate",):
                    imported += 1
            except Exception as exc:
                db.rollback()
                job.failed_rows = (job.failed_rows or 0) + 1
                errs = list(job.error_log or [])
                errs.append({"row": msg.raw_payload.get("csv_row"), "reason": str(exc)[:200]})
                job.error_log = errs
                db.add(job)
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                logger.warning("CSV import row failed for job %s: %s", job_id, exc)

        db_job = db.query(BulkImportJob).filter(BulkImportJob.id == uuid.UUID(job_id)).first()
        if db_job:
            db_job.imported_rows = imported
            db_job.status = "done"
            db_job.completed_at = datetime.now(timezone.utc)
            db.commit()
    except Exception:
        logger.exception("CSV import job %s crashed", job_id)
        try:
            j = db.query(BulkImportJob).filter(BulkImportJob.id == uuid.UUID(job_id)).first()
            if j:
                j.status = "failed"
                j.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


@router.post("/csv", status_code=202)
async def upload_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    client: Client = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")
    if not content.strip():
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    job = BulkImportJob(
        client_id=client.id,
        filename=file.filename,
        status="processing",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(_process_job, str(job.id), content, str(client.id))

    return {
        "job_id": str(job.id),
        "status": "processing",
        "message": "CSV import started. Poll /api/v1/bulk-import/jobs/{job_id} for status.",
    }


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    client: Client = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id")

    job = db.query(BulkImportJob).filter(
        BulkImportJob.id == job_uuid,
        BulkImportJob.client_id == client.id,
    ).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": str(job.id),
        "status": job.status,
        "filename": job.filename,
        "total_rows": job.total_rows,
        "imported_rows": job.imported_rows,
        "failed_rows": job.failed_rows,
        "errors": (job.error_log or [])[:20],
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
