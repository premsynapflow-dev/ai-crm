from datetime import timedelta

from app.db.models import Complaint, EventLog


def build_ticket_timeline(db, client_id, ticket_id: str):
    complaints = (
        db.query(Complaint)
        .filter(
            Complaint.client_id == client_id,
            Complaint.ticket_id == ticket_id,
        )
        .order_by(Complaint.created_at.asc())
        .all()
    )
    complaint_ids = {str(item.id) for item in complaints}
    timeline = []
    earliest_timestamp = complaints[0].created_at - timedelta(days=1) if complaints else None

    for complaint in complaints:
        event_type = "chat_message" if complaint.source == "chatbot" else "customer_message"
        timeline.append(
            {
                "type": event_type,
                "timestamp": complaint.created_at,
                "complaint_id": str(complaint.id),
                "ticket_id": complaint.ticket_id,
                "summary": complaint.summary,
                "source": complaint.source,
                "status": complaint.status,
                "resolution_status": complaint.resolution_status,
                "priority": complaint.priority,
            }
        )

        if complaint.ai_reply:
            timeline.append(
                {
                    "type": "ai_reply",
                    "timestamp": complaint.ai_reply_sent_at or complaint.first_response_at or complaint.created_at,
                    "complaint_id": str(complaint.id),
                    "ticket_id": complaint.ticket_id,
                    "summary": complaint.ai_reply,
                    "status": complaint.ai_reply_status,
                    "confidence": complaint.ai_reply_confidence,
                }
            )

        if complaint.resolved_at:
            timeline.append(
                {
                    "type": "status_change",
                    "timestamp": complaint.resolved_at,
                    "complaint_id": str(complaint.id),
                    "ticket_id": complaint.ticket_id,
                    "summary": "Ticket marked resolved",
                    "status": complaint.resolution_status,
                }
            )

    event_logs = (
        db.query(EventLog)
        .filter(
            EventLog.client_id == client_id,
            EventLog.created_at >= earliest_timestamp if earliest_timestamp is not None else True,
        )
        .order_by(EventLog.created_at.asc())
        .limit(500)
        .all()
    )
    for event in event_logs:
        payload = event.payload or {}
        payload_ticket_id = payload.get("ticket_id")
        payload_complaint_id = str(payload.get("complaint_id")) if payload.get("complaint_id") else None
        if payload_ticket_id != ticket_id and payload_complaint_id not in complaint_ids:
            continue
        timeline.append(
            {
                "type": event.event_type,
                "timestamp": event.created_at,
                "ticket_id": payload_ticket_id or ticket_id,
                "complaint_id": payload_complaint_id,
                "summary": payload.get("summary") or payload.get("message") or event.event_type,
                "payload": payload,
            }
        )

    timeline.sort(key=lambda item: item.get("timestamp") or "")
    return timeline
