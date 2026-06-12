"""Upload Intelligence Pipeline — POST /api/v1/upload-intelligence/...

Three-step workflow:
  1. POST /upload                       — parse file, create complaints, enqueue classification
  2. POST /jobs/{id}/analyze            — run root-cause + pulse on ingested data
  3. POST /jobs/{id}/generate-artifact  — generate Weekly Operational Digest artifact
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import get_current_client_user
from app.connectors.file_mapper import detect_format, parse_file
from app.db.models import Artifact, Client, UploadIntelligenceJob
from app.db.session import SessionLocal, get_db
from app.services.artifact_service import ArtifactService
from app.services.unified_ingestion import process_incoming_message
from app.utils.logging import get_logger

router = APIRouter(prefix="/api/v1/upload-intelligence", tags=["upload-intelligence"])
logger = get_logger(__name__)

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
VALID_DATA_TYPES = {"reviews", "support_tickets", "complaints", "refunds"}


# ---------------------------------------------------------------------------
# Serialiser
# ---------------------------------------------------------------------------

def _serialize(job: UploadIntelligenceJob) -> dict:
    return {
        "id": str(job.id),
        "filename": job.filename,
        "file_format": job.file_format,
        "data_type": job.data_type,
        "status": job.status,
        "total_rows": job.total_rows,
        "mapped_rows": job.mapped_rows,
        "failed_rows": job.failed_rows,
        "errors": (job.error_log or [])[:20],
        "analysis_status": job.analysis_status,
        "analysis_results": job.analysis_results,
        "artifact_id": str(job.artifact_id) if job.artifact_id else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


# ---------------------------------------------------------------------------
# Background processing
# ---------------------------------------------------------------------------

def _process_upload(job_id: str, content: bytes, client_id: str, filename: str, data_type: str) -> None:
    db = SessionLocal()
    try:
        job = db.query(UploadIntelligenceJob).filter(
            UploadIntelligenceJob.id == uuid.UUID(job_id)
        ).first()
        if job is None:
            return

        try:
            messages, parse_errors = parse_file(content, filename, data_type, client_id)
        except ValueError as exc:
            job.status = "failed"
            job.error_log = [{"row": 0, "reason": str(exc)}]
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        total = len(messages) + len(parse_errors)
        job.total_rows = total
        job.failed_rows = len(parse_errors)
        job.error_log = parse_errors
        db.commit()

        mapped = 0
        for msg in messages:
            try:
                result = process_incoming_message(db, msg)
                db.commit()
                if result.get("status") not in ("duplicate",):
                    mapped += 1
            except Exception as exc:
                db.rollback()
                job.failed_rows = (job.failed_rows or 0) + 1
                errs = list(job.error_log or [])
                errs.append({
                    "row": msg.raw_payload.get("csv_row"),
                    "reason": str(exc)[:200],
                })
                job.error_log = errs
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                logger.warning("Upload job %s: row failed: %s", job_id, exc)

        db_job = db.query(UploadIntelligenceJob).filter(
            UploadIntelligenceJob.id == uuid.UUID(job_id)
        ).first()
        if db_job:
            db_job.mapped_rows = mapped
            db_job.status = "queued"
            db_job.completed_at = datetime.now(timezone.utc)
            db.commit()
    except Exception:
        logger.exception("Upload job %s crashed", job_id)
        try:
            j = db.query(UploadIntelligenceJob).filter(
                UploadIntelligenceJob.id == uuid.UUID(job_id)
            ).first()
            if j:
                j.status = "failed"
                j.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/upload", status_code=202)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    data_type: str = Form(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_client_user),
):
    """
    Step 1: Upload a CSV / Excel / JSON file of customer feedback.

    data_type must be one of: reviews | support_tickets | complaints | refunds
    """
    if data_type not in VALID_DATA_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"data_type must be one of: {', '.join(sorted(VALID_DATA_TYPES))}",
        )

    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("csv", "xlsx", "xls", "json"):
        raise HTTPException(
            status_code=400,
            detail="Only .csv, .xlsx, and .json files are accepted",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 20 MB limit")
    if not content.strip():
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    client_id = current_user.client_id
    file_format = detect_format(filename)

    job = UploadIntelligenceJob(
        client_id=client_id,
        filename=filename,
        file_format=file_format,
        data_type=data_type,
        status="processing",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(
        _process_upload,
        str(job.id),
        content,
        str(client_id),
        filename,
        data_type,
    )

    return {
        "job_id": str(job.id),
        "status": "processing",
        "message": "Upload started. Poll /api/v1/upload-intelligence/jobs/{job_id} for status.",
    }


@router.get("/jobs")
def list_jobs(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_client_user),
):
    """List recent upload jobs for the authenticated client (newest first)."""
    jobs = (
        db.query(UploadIntelligenceJob)
        .filter(UploadIntelligenceJob.client_id == current_user.client_id)
        .order_by(UploadIntelligenceJob.created_at.desc())
        .limit(20)
        .all()
    )
    return [_serialize(j) for j in jobs]


@router.get("/jobs/{job_id}")
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_client_user),
):
    """Poll upload job status and progress."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id")

    job = db.query(UploadIntelligenceJob).filter(
        UploadIntelligenceJob.id == job_uuid,
        UploadIntelligenceJob.client_id == current_user.client_id,
    ).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _serialize(job)


@router.post("/jobs/{job_id}/analyze")
def analyze_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_client_user),
):
    """
    Step 2: Run root-cause analysis + customer pulse on the ingested complaint data.

    Can be called once upload status is 'queued' or 'done'.
    Results are stored in analysis_results and returned in the response.
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id")

    job = db.query(UploadIntelligenceJob).filter(
        UploadIntelligenceJob.id == job_uuid,
        UploadIntelligenceJob.client_id == current_user.client_id,
    ).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == "processing":
        raise HTTPException(
            status_code=409,
            detail="Upload is still processing. Wait until status is 'queued' or 'done'.",
        )

    job.analysis_status = "running"
    db.commit()

    try:
        from app.services.root_cause import generate_root_cause_report
        from app.analytics.customer_pulse import generate_customer_pulse

        client_id = str(current_user.client_id)
        root_cause = generate_root_cause_report(db, client_id, period_days=30)
        pulse = generate_customer_pulse(db, client_id)

        analysis = {
            "root_cause": root_cause,
            "pulse": pulse,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        job.analysis_status = "done"
        job.analysis_results = analysis
        job.status = "done"
        db.commit()

        return {**_serialize(job), "analysis_results": analysis}

    except Exception as exc:
        logger.exception("Analysis failed for job %s", job_id)
        job.analysis_status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc


@router.post("/jobs/{job_id}/generate-artifact")
def generate_artifact(
    job_id: str,
    recipient: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_client_user),
):
    """
    Step 3: Generate a Weekly Operational Digest artifact from the ingested data.

    Links the artifact to this upload job. The artifact is created in 'draft' status
    and can be reviewed/approved in the Artifacts page.
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id")

    job = db.query(UploadIntelligenceJob).filter(
        UploadIntelligenceJob.id == job_uuid,
        UploadIntelligenceJob.client_id == current_user.client_id,
    ).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == "processing":
        raise HTTPException(
            status_code=409,
            detail="Upload is still processing. Wait until status is 'queued' or 'done'.",
        )

    client = db.query(Client).filter(Client.id == current_user.client_id).first()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    svc = ArtifactService(db)
    artifact = svc.generate_weekly_digest(client, recipient=recipient)

    job.artifact_id = artifact.id
    db.commit()

    return {
        "artifact_id": str(artifact.id),
        "artifact_status": artifact.status,
        "artifact_title": artifact.title,
        "job_id": str(job.id),
        "message": "Digest artifact created. Review and approve it in the Artifacts page.",
    }
