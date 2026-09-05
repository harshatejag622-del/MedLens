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
