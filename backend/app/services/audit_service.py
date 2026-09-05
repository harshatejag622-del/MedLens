import json
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.audit import AuditLog, VerificationEvent

class AuditService:
    @staticmethod
    def log_action(
        db: Session,
        action: str,
        entity_type: str,
        entity_id: str,
        user_id: str = "clinician_user",
        details: dict = None,
        ip_address: str = "127.0.0.1"
    ) -> AuditLog:
        """
        Creates an immutable, append-only audit log entry.
        Never logs sensitive unencrypted passwords, API keys, or raw PHI unnecessarily.
        """
        details_str = json.dumps(details or {})
        entry = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            user_id=user_id,
            details=details_str,
            ip_address=ip_address,
            timestamp=datetime.utcnow()
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def record_verification(
        db: Session,
        target_id: str,
        target_type: str,
        original_value: str,
        corrected_value: str,
        change_reason: str = None,
        verified_by: str = "clinician_user"
    ) -> VerificationEvent:
        event = VerificationEvent(
            target_id=target_id,
            target_type=target_type,
            original_value=original_value,
            corrected_value=corrected_value,
            change_reason=change_reason,
            verified_by=verified_by,
            provenance="HUMAN_VERIFIED",
            timestamp=datetime.utcnow()
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
