"""GST tax calculation + lazy invoice generation.

Listed prices are GST-inclusive (Indian retail norm), so this module back-computes
the embedded GST from the order total — guaranteeing invoice.total == order.total
and leaving the existing order/pricing flow completely untouched.

Intra-state supply (ship state == seller state) splits into CGST+SGST; inter-state
uses IGST.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app import models
from app.core.config import settings
from app.services.common import money

SELLER_STATE_CODES = {"MH", "MAHARASHTRA"}  # GSTIN 27 => Maharashtra (demo seller)


def _is_intra_state(ship_state: str | None) -> bool:
    return (ship_state or "").strip().upper() in SELLER_STATE_CODES


def compute_gst(goods_incl_tax: Decimal, percent: Decimal, intra_state: bool) -> dict:
    """Split a GST-inclusive goods amount into taxable value + tax components."""
    rate = percent / Decimal(100)
    taxable = money(goods_incl_tax / (Decimal(1) + rate)) if rate > 0 else money(goods_incl_tax)
    gst = money(goods_incl_tax - taxable)
    if intra_state:
        cgst = money(gst / 2)
        sgst = money(gst - cgst)  # absorb rounding remainder into sgst
        igst = Decimal("0.00")
    else:
        cgst = sgst = Decimal("0.00")
        igst = gst
    return {"taxable_value": taxable, "cgst": cgst, "sgst": sgst, "igst": igst, "gst": gst}


def get_or_create_invoice(db: Session, order: models.Order) -> models.Invoice:
    existing = db.query(models.Invoice).filter(models.Invoice.order_id == order.id).first()
    if existing:
        return existing

    percent = money(settings.GST_PERCENT)
    # Goods value (GST-inclusive) = discounted subtotal; shipping kept tax-neutral here.
    goods_incl = money(money(order.subtotal) - money(order.discount_amount))
    parts = compute_gst(goods_incl, percent, _is_intra_state(order.ship_state))

    invoice = models.Invoice(
        order_id=order.id,
        invoice_number=f"INV-{order.order_number}",
        seller_gstin=settings.STORE_GSTIN,
        place_of_supply=order.ship_state,
        gst_percent=percent,
        subtotal=money(order.subtotal),
        discount_amount=money(order.discount_amount),
        shipping_fee=money(order.shipping_fee),
        taxable_value=parts["taxable_value"],
        cgst=parts["cgst"],
        sgst=parts["sgst"],
        igst=parts["igst"],
        total_amount=money(order.total_amount),
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice
