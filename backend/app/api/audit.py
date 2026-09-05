from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.audit import AuditLog

router = APIRouter(prefix="/audit", tags=["Audit & Provenance Logging"])

@router.get("")
def get_audit_logs(
    limit: int = Query(50, le=100),
    entity_type: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type.upper())
    logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()

    return [
        {
            "id": log.id,
            "timestamp": log.timestamp.isoformat() + "Z",
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "user_id": log.user_id,
            "ip_address": log.ip_address,
            "details": log.details
        } for log in logs
    ]

@router.get("/export")
def export_audit_logs_csv(
    entity_type: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    HIPAA Compliance Audit Export:
    Provides an immutable, timestamped CSV export of all clinical actions,
    provenance modifications, and clinician review decisions.
    """
    import csv
    import io
    from fastapi.responses import Response

    query = db.query(AuditLog)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type.upper())
    logs = query.order_by(AuditLog.timestamp.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Audit ID",
        "Timestamp (UTC)",
        "Action Taken",
        "Entity Type",
        "Entity ID",
        "Clinician / User ID",
        "Source IP Address",
        "Audit Details"
    ])

    for log in logs:
        writer.writerow([
            log.id,
            log.timestamp.isoformat() + "Z" if log.timestamp else "",
            log.action,
            log.entity_type,
            log.entity_id,
            log.user_id or "SYSTEM",
            log.ip_address or "INTERNAL",
            log.details or ""
        ])

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=hipaa_clinical_audit_trail.csv"
        }
    )

