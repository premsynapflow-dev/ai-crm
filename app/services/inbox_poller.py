from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.inboxes.models import Inbox
from app.services.unified_ingestion import IncomingMessage, process_incoming_message
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _store_inbox_poll_result(inbox_id: str, *, error: str | None) -> None:
    """Persist poll error/success state using a separate session so it survives rollbacks."""
    from app.inboxes.models import Inbox as _Inbox
    error_db = SessionLocal()
    try:
        target = error_db.query(_Inbox).filter(_Inbox.id == inbox_id).first()
        if target is None:
            return
        meta = dict(target.metadata_json or {})
        now_iso = _utcnow().isoformat()
        if error is None:
            meta["last_poll_error"] = None
            meta["last_poll_error_at"] = None
            meta["consecutive_poll_failures"] = 0
            meta["last_successful_poll_at"] = now_iso
        else:
            meta["last_poll_error"] = error[:500]
            meta["last_poll_error_at"] = now_iso
            meta["consecutive_poll_failures"] = int(meta.get("consecutive_poll_failures", 0)) + 1
            # Permanently deactivate after 5 consecutive failures so the UI shows reauth needed
            if int(meta["consecutive_poll_failures"]) >= 5:
                target.is_active = False
        target.metadata_json = meta
        error_db.commit()
    except Exception:
        logger.warning("Failed to persist poll result for inbox=%s", inbox_id, exc_info=True)
    finally:
        error_db.close()


def _process_messages(db: Session, messages: list[IncomingMessage]) -> tuple[int, int, int]:
    processed = 0
    duplicates = 0
    errors = 0
    for message in messages:
        try:
            result = process_incoming_message(db, message)
            if result.get("status") == "duplicate":
                duplicates += 1
            else:
                processed += 1
            db.commit()
        except Exception:
            db.rollback()
            errors += 1
            logger.exception(
                "Inbox message processing failed channel=%s external_message_id=%s",
                message.channel,
                message.external_message_id,
            )
    return processed, duplicates, errors


def poll_inbox(db: Session, inbox: Inbox, *, max_results: int = 20) -> dict[str, Any]:
    provider = (inbox.provider_type or "").lower()
    logger.info(
        "Polling inbox=%s tenant=%s provider=%s email=%s",
        inbox.id,
        inbox.tenant_id,
        provider,
        inbox.email_address,
    )

    if provider == "gmail":
        from app.integrations.gmail import poll_gmail_inbox

        messages = poll_gmail_inbox(inbox, max_results=max_results)
    elif provider == "imap":
        from app.inboxes.service import fetch_imap_messages

        messages = fetch_imap_messages(inbox, max_results=max_results)
    else:
        logger.warning("Skipping unsupported inbox provider=%s inbox=%s", provider, inbox.id)
        return {
            "inbox_id": str(inbox.id),
            "provider": provider,
            "fetched": 0,
            "processed": 0,
            "duplicates": 0,
        }

    logger.info("Fetched %s %s messages for inbox=%s", len(messages), provider, inbox.id)
    processed, duplicates, errors = _process_messages(db, messages)
    inbox.last_synced_at = _utcnow()
    logger.info(
        "Inbox poll complete inbox=%s provider=%s fetched=%s processed=%s duplicates=%s errors=%s",
        inbox.id,
        provider,
        len(messages),
        processed,
        duplicates,
        errors,
    )
    return {
        "inbox_id": str(inbox.id),
        "provider": provider,
        "fetched": len(messages),
        "processed": processed,
        "duplicates": duplicates,
        "errors": errors,
    }


def poll_all_inboxes(*, max_results: int = 20) -> dict[str, int]:
    db = SessionLocal()
    totals = {
        "inboxes": 0,
        "fetched": 0,
        "processed": 0,
        "duplicates": 0,
        "errors": 0,
    }
    try:
        try:
            inboxes = (
                db.query(Inbox)
                .filter(
                    Inbox.provider_type.in_(["gmail", "imap"]),
                    Inbox.is_active == True,
                )
                .order_by(Inbox.created_at.asc())
                .all()
            )
        except Exception as exc:
            db.rollback()
            if "does not exist" in str(exc).lower():
                logger.warning("inbox_poller: inboxes table not available yet, skipping: %s", exc)
                return totals
            raise

        totals["inboxes"] = len(inboxes)

        for inbox in inboxes:
            inbox_id = str(inbox.id)
            provider = inbox.provider_type
            email_address = inbox.email_address
            try:
                result = poll_inbox(db, inbox, max_results=max_results)
                totals["fetched"] += int(result["fetched"])
                totals["processed"] += int(result["processed"])
                totals["duplicates"] += int(result["duplicates"])
                totals["errors"] += int(result.get("errors", 0))
                # Clear any stored poll error on success
                _store_inbox_poll_result(inbox_id, error=None)
                db.commit()
            except Exception as exc:
                db.rollback()
                totals["errors"] += 1
                logger.exception(
                    "Inbox poll failed inbox=%s provider=%s email=%s: %s",
                    inbox_id,
                    provider,
                    email_address,
                    exc,
                )
                _store_inbox_poll_result(inbox_id, error=str(exc))
        return totals
    finally:
        db.close()
