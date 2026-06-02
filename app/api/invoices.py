import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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

    plan_name = (client.plan or "free").capitalize()

    return [
        {
            "id": str(inv.id),
            "invoice_number": inv.invoice_number or str(inv.id)[:8].upper(),
            "status": inv.status,
            "total": float(inv.total),
            "subtotal": float(inv.subtotal),
            "tax": float(inv.tax),
            "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
            "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
            "payment_method": inv.payment_method,
            "plan": plan_name,
        }
        for inv in invoices
    ]


@router.get("/invoices/{invoice_id}/download")
def download_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.client_id == client.id)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            HRFlowable,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError:
        raise HTTPException(status_code=503, detail="PDF generation unavailable")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    blue = colors.HexColor("#1d4ed8")
    light_gray = colors.HexColor("#e5e7eb")
    dark_gray = colors.HexColor("#374151")

    title_style = ParagraphStyle(
        "sf_title", parent=styles["Heading1"], fontSize=26, textColor=blue, spaceAfter=2
    )
    sub_style = ParagraphStyle(
        "sf_sub", parent=styles["Normal"], fontSize=9, textColor=colors.grey
    )
    heading_style = ParagraphStyle(
        "sf_heading", parent=styles["Heading2"], fontSize=12, spaceAfter=4
    )
    small_style = ParagraphStyle(
        "sf_small", parent=styles["Normal"], fontSize=8, textColor=colors.grey
    )

    inv_date_str = invoice.invoice_date.strftime("%d %B %Y") if invoice.invoice_date else "—"
    paid_str = invoice.paid_at.strftime("%d %B %Y") if invoice.paid_at else "—"
    plan_name = (client.plan or "free").capitalize()
    inv_number = invoice.invoice_number or str(invoice.id)[:8].upper()

    story = []

    # Header
    story.append(Paragraph("SynapFlow", title_style))
    story.append(Paragraph("AI Complaint Intelligence Platform", sub_style))
    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=blue))
    story.append(Spacer(1, 6 * mm))

    # Invoice meta + billed-to side by side
    meta_rows = [
        [Paragraph("<b>Invoice Number</b>", styles["Normal"]), inv_number],
        [Paragraph("<b>Invoice Date</b>", styles["Normal"]), inv_date_str],
        [Paragraph("<b>Status</b>", styles["Normal"]), invoice.status.capitalize()],
        [Paragraph("<b>Payment Method</b>", styles["Normal"]), (invoice.payment_method or "—").capitalize()],
        [Paragraph("<b>Paid On</b>", styles["Normal"]), paid_str],
    ]
    billed_rows = [
        [Paragraph("<b>Billed To</b>", styles["Normal"])],
        [Paragraph(client.name or "—", styles["Normal"])],
    ]

    meta_table = Table(meta_rows, colWidths=[55 * mm, 85 * mm])
    meta_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), dark_gray),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8 * mm))

    # Line items table
    story.append(Paragraph("Invoice Details", heading_style))

    items_data = [["Description", "Amount (INR)"]]
    items_data.append([f"SynapFlow {plan_name} Plan (Monthly Subscription)", f"₹{int(invoice.subtotal):,}"])
    if invoice.tax and invoice.tax > 0:
        items_data.append(["GST (18%)", f"₹{int(invoice.tax):,}"])
    items_data.append(["", ""])
    items_data.append([Paragraph("<b>Total</b>", styles["Normal"]), Paragraph(f"<b>₹{int(invoice.total):,}</b>", ParagraphStyle("right", parent=styles["Normal"], alignment=TA_RIGHT))])

    col_widths = [120 * mm, 40 * mm]
    items_table = Table(items_data, colWidths=col_widths)
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), blue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f9fafb")]),
        ("GRID", (0, 0), (-1, -2), 0.5, light_gray),
        ("LINEABOVE", (0, -1), (-1, -1), 1.5, blue),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eff6ff")),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 10 * mm))

    # Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=light_gray))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Thank you for your business. For billing queries contact billing@synapflow.ai",
        small_style,
    ))

    doc.build(story)
    buffer.seek(0)

    filename = f"synapflow-invoice-{inv_number}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
