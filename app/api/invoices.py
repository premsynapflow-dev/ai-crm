from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_client
from app.db.models import Client, Invoice
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["billing"])


@router.get("/invoices")
def get_invoices(
    db: Session = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    invoices = (
        db.query(Invoice)
        .filter(Invoice.client_id == client.id)
        .order_by(Invoice.created_at.desc())
        .all()
    )

    return [
        {
            "id": str(inv.id),
            "invoice_number": inv.invoice_number,
            "status": inv.status,
            "total": float(inv.total),
            "subtotal": float(inv.subtotal),
            "tax": float(inv.tax),
            "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
            "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
            "payment_method": inv.payment_method,
        }
        for inv in invoices
    ]
