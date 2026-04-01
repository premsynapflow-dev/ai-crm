from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditLog


def _json_safe(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def append_audit_log(
    db: Session,
    *,
    entity_type: str,
    entity_id: uuid.UUID | str,
    action: str,
    performed_by: str | None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        entity_type=entity_type,
        entity_id=uuid.UUID(str(entity_id)),
        action=action,
        performed_by=performed_by,
        old_value=_json_safe(old_value) if old_value is not None else None,
        new_value=_json_safe(new_value) if new_value is not None else None,
    )
    db.add(audit_log)
    db.flush()
    return audit_log


def list_entity_audit_logs(
    db: Session,
    *,
    entity_type: str,
    entity_id: uuid.UUID | str,
) -> list[AuditLog]:
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == uuid.UUID(str(entity_id)),
        )
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .all()
    )


def serialize_audit_log(entry: AuditLog) -> dict[str, Any]:
    return {
        "id": str(entry.id),
        "entity_type": entry.entity_type,
        "entity_id": str(entry.entity_id),
        "action": entry.action,
        "performed_by": entry.performed_by,
        "old_value": entry.old_value or {},
        "new_value": entry.new_value or {},
        "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
    }
