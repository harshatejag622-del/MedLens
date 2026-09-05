import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, File, Form, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models.document import Document, DocumentProcessingJob
from app.models.patient import Patient
from app.schemas.document import (
    DocumentResponse,
    DocumentDetailResponse,
    DocumentUploadResponse,
    DocumentProcessingJobResponse,
    DocumentRetryResponse,
    DocumentStatusResponse
)
from app.services.storage_service import StorageService
from app.services.audit_service import AuditService
from app.services.document_processor import process_document

router = APIRouter(prefix="/documents", tags=["Medical Reports"])

@router.get("", response_model=List[DocumentResponse])
def list_documents(
    patient_id: Optional[str] = Query(None, description="Filter documents by Patient ID"),
    status: Optional[str] = Query(None, description="Filter by status: QUEUED, PROCESSING, COMPLETED, FAILED, REVIEW_REQUIRED"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    search: Optional[str] = Query(None, description="Search by filename, checksum, or facility"),
    db: Session = Depends(get_db)
):
    """
    Lists medical documents with optional patient, status, and search filters.
    """
    query = db.query(Document)
    if patient_id:
        query = query.filter(Document.patient_id == patient_id)
    if status:
        query = query.filter(Document.processing_status == status.strip().upper())
    if document_type:
        query = query.filter(Document.document_type == document_type.strip().upper())
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Document.original_filename.ilike(term),
                Document.sha256_checksum.ilike(term),
                Document.facility.ilike(term),
                Document.source.ilike(term)
            )
        )
    return query.order_by(Document.created_at.desc()).all()


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(document_id: str, db: Session = Depends(get_db)):
    """
    Returns complete document metadata along with processing job audit history.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Medical document record not found")
    return doc


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(..., description="Document binary payload (PDF, PNG, JPG, JPEG, TIFF, WEBP, TXT)"),
    patient_id: str = Form(..., description="Target Patient ID"),
    document_type: str = Form("LABORATORY_REPORT", description="Report classification"),
    facility: Optional[str] = Form(None, description="Originating diagnostic facility or hospital"),
    source: Optional[str] = Form(None, description="Clinical data source name"),
    report_date: Optional[str] = Form(None, description="Clinical report collection or generation date"),
    db: Session = Depends(get_db)
):
    """
    Uploads and validates a clinical report document.
    Enforces MIME and magic bytes validation, size limits, safe filename sanitization,
    duplicate checksum detection, and creates an asynchronous processing job in QUEUED status.
    The original file is stored separately in isolated storage and NEVER overwritten.
    """
    # 1. Verify Patient authorization / existence
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID '{patient_id}' not found. Unauthorized document upload."
        )

    # 2. Read file content safely
    content = await file.read()

    # 3. Comprehensive file validation (Size, Extension, Magic bytes, Corruption)
    filename = file.filename or "uploaded_report.pdf"
    mime_type = StorageService.validate_file_upload(filename, content, file.content_type)

    # 4. Duplicate Checksum Detection (SHA-256)
    checksum = StorageService.compute_sha256(content)
    duplicate = db.query(Document).filter(
        Document.patient_id == patient_id,
        Document.sha256_checksum == checksum
    ).first()

    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Duplicate document detected. This report (SHA-256: {checksum[:12]}...) "
                f"has already been ingested for patient '{patient.mrn}' as '{duplicate.original_filename}' "
                f"(Document ID: {duplicate.id})."
            )
        )

    # 5. Store original document separately (Never overwrites existing files)
    stored_filename, dest_path, file_size, checksum = StorageService.store_document(
        patient_id=patient_id,
        original_filename=filename,
        content=content
    )

    clean_filename = StorageService.sanitize_filename(filename)
    source_val = source or facility or "Clinical Diagnostic Center"
    facility_val = facility or source_val

    # 6. Create Document record
    document = Document(
        patient_id=patient_id,
        original_filename=clean_filename,
        stored_filename=stored_filename,
        file_type=mime_type,
        file_size_bytes=file_size,
        sha256_checksum=checksum,
        report_date=report_date or datetime.utcnow().strftime("%Y-%m-%d"),
        document_type=document_type.upper(),
        facility=facility_val,
        source=source_val,
        processing_status="QUEUED"
    )
    db.add(document)
    db.flush()

    # 7. Create Document Processing Job in QUEUED state
    job = DocumentProcessingJob(
        document_id=document.id,
        status="QUEUED",
        current_step="INGESTION_COMPLETED",
        started_at=datetime.utcnow(),
        log_messages=(
            f"[{datetime.utcnow().isoformat()}] Document '{clean_filename}' validated and stored. "
            f"SHA-256: {checksum}. Processing job initialized in QUEUED state."
        )
    )
    db.add(job)
    db.commit()
    db.refresh(document)
    db.refresh(job)

    # 8. Audit Log
    AuditService.log_action(
        db=db,
        action="DOCUMENT_UPLOADED",
        entity_type="DOCUMENT",
        entity_id=document.id,
        details={
            "mrn": patient.mrn,
            "filename": document.original_filename,
            "sha256": document.sha256_checksum,
            "file_size": document.file_size_bytes
        }
    )

    return DocumentUploadResponse(
        document=document,
        job=job,
        message="Medical document uploaded, validated, and queued for processing."
    )


@router.get("/{document_id}/download")
def download_document(document_id: str, db: Session = Depends(get_db)):
    """
    Securely streams the original stored file with proper MIME headers.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Medical document record not found")

    content = StorageService.read_document_bytes(doc.patient_id, doc.stored_filename)
    return Response(
        content=content,
        media_type=doc.file_type,
        headers={
            "Content-Disposition": f'inline; filename="{doc.original_filename}"',
            "X-Document-Checksum": doc.sha256_checksum
        }
    )


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
def get_document_status(document_id: str, db: Session = Depends(get_db)):
    """
    Returns live processing status and pipeline execution logs.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Medical document record not found")

    latest_job = db.query(DocumentProcessingJob).filter(
        DocumentProcessingJob.document_id == document_id
    ).order_by(DocumentProcessingJob.started_at.desc()).first()

    return DocumentStatusResponse(
        document_id=doc.id,
        processing_status=doc.processing_status,
        processing_error=doc.processing_error,
        current_step=latest_job.current_step if latest_job else "N/A",
        started_at=latest_job.started_at if latest_job else doc.created_at,
        completed_at=latest_job.completed_at if latest_job else None,
        log_messages=latest_job.log_messages if latest_job else ""
    )


@router.post("/{document_id}/retry", response_model=DocumentRetryResponse)
def retry_document_processing(document_id: str, db: Session = Depends(get_db)):
    """
    Retries a failed or stalled document processing job.
    Resets status to QUEUED and updates audit trail.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Medical document record not found")

    # Reset status
    doc.processing_status = "QUEUED"
    doc.processing_error = None
    doc.updated_at = datetime.utcnow()

    # Create new job execution or update current
    job = DocumentProcessingJob(
        document_id=doc.id,
        status="QUEUED",
        current_step="RETRY_QUEUED",
        started_at=datetime.utcnow(),
        log_messages=f"[{datetime.utcnow().isoformat()}] Processing retry requested by clinician."
    )
    db.add(job)
    db.commit()

    AuditService.log_action(
        db=db,
        action="DOCUMENT_RETRY_REQUESTED",
        entity_type="DOCUMENT",
        entity_id=doc.id,
        details={"status": "QUEUED"}
    )

    return DocumentRetryResponse(
        document_id=doc.id,
        status="QUEUED",
        current_step="RETRY_QUEUED",
        message="Document processing retry queued."
    )


@router.post("/{document_id}/fail", response_model=DocumentResponse)
def mark_document_failed(
    document_id: str,
    reason: str = Query("Pipeline failure simulated or reported", description="Failure reason description"),
    db: Session = Depends(get_db)
):
    """
    Explicitly marks document processing as FAILED with descriptive error message.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Medical document record not found")

    doc.processing_status = "FAILED"
    doc.processing_error = reason
    doc.updated_at = datetime.utcnow()

    latest_job = db.query(DocumentProcessingJob).filter(
        DocumentProcessingJob.document_id == document_id
    ).order_by(DocumentProcessingJob.started_at.desc()).first()

    if latest_job:
        latest_job.status = "FAILED"
        latest_job.current_step = "EXECUTION_HALTED"
        latest_job.completed_at = datetime.utcnow()
        latest_job.log_messages += f"\n[{datetime.utcnow().isoformat()}] ERROR: {reason}"

    db.commit()
    db.refresh(doc)

    AuditService.log_action(
        db=db,
        action="DOCUMENT_PROCESSING_FAILED",
        entity_type="DOCUMENT",
        entity_id=doc.id,
        details={"reason": reason}
    )

    return doc


@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
def delete_document(document_id: str, db: Session = Depends(get_db)):
    """
    Deletes medical document record and removes stored physical file.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Medical document record not found")

    # Delete physical file from storage
    StorageService.delete_document(doc.patient_id, doc.stored_filename)

    doc_id = doc.id
    filename = doc.original_filename
    db.delete(doc)
    db.commit()

    AuditService.log_action(
        db=db,
        action="DOCUMENT_DELETED",
        entity_type="DOCUMENT",
        entity_id=doc_id,
        details={"filename": filename}
    )

    return {"success": True, "message": f"Document '{filename}' successfully deleted."}


@router.post("/{document_id}/process")
def process_document_endpoint(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Trigger AI clinical extraction for a QUEUED or FAILED document.

    Starts the full pipeline in the background:
      OCR → AI Extraction → Business Validation → Database Persistence

    The document processing_status transitions to PROCESSING immediately.
    Poll GET /api/documents/{id}/status for completion.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if doc.processing_status not in {"QUEUED", "FAILED", "REVIEW_REQUIRED"}:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Document is in '{doc.processing_status}' state. "
                "Only QUEUED, FAILED, or REVIEW_REQUIRED documents can be processed."
            ),
        )

    # Run extraction in background so the API returns immediately
    background_tasks.add_task(process_document, db, document_id)

    return {
        "document_id": document_id,
        "message": "AI extraction pipeline started. Poll /status for progress.",
        "processing_status": "PROCESSING",
    }

