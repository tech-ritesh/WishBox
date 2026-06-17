"""Shipment tracking + returns/exchange workflow (service layer)."""
from __future__ import annotations

import datetime as dt
import random
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models
from app.services import notifications
from app.services.common import money

RETURN_WINDOW_DAYS = 7


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# --- Shipping ----------------------------------------------------------------
def upsert_shipment(db: Session, order: models.Order, data) -> models.Shipment:
    shipment = db.query(models.Shipment).filter(models.Shipment.order_id == order.id).first()
    if not shipment:
        shipment = models.Shipment(
            order_id=order.id,
            tracking_number=f"WB{random.randint(10**9, 10**10 - 1)}",
        )
        db.add(shipment)
        db.flush()

    if data.carrier:
        shipment.carrier = data.carrier
    if data.tracking_number:
        shipment.tracking_number = data.tracking_number
    if data.estimated_delivery:
        shipment.estimated_delivery = data.estimated_delivery
    if data.status:
        shipment.status = data.status
        if data.status == "in_transit" and not shipment.shipped_at:
            shipment.shipped_at = _utcnow()
        if data.status == "delivered":
            shipment.delivered_at = _utcnow()
        db.add(models.ShipmentEvent(
            shipment_id=shipment.id, status=data.status,
            location=data.location, note=data.note,
        ))
        # Mirror onto the order's tracking_code so existing UI keeps working.
        order.tracking_code = shipment.tracking_number

    db.commit()
    db.refresh(shipment)
    return shipment


# --- Returns -----------------------------------------------------------------
def create_return(db: Session, user: models.User, order: models.Order, data) -> models.ReturnRequest:
    if order.status.value != "delivered":
        raise HTTPException(status_code=400, detail="Only delivered orders can be returned")

    # Return window check (based on the most recent 'delivered' history entry, else order age).
    delivered_at = next((h.created_at for h in reversed(order.history) if h.status == "delivered"), order.created_at)
    if delivered_at and delivered_at.tzinfo is None:
        delivered_at = delivered_at.replace(tzinfo=dt.timezone.utc)
    if delivered_at and (_utcnow() - delivered_at).days > RETURN_WINDOW_DAYS:
        raise HTTPException(status_code=400, detail=f"Return window of {RETURN_WINDOW_DAYS} days has passed")

    if db.query(models.ReturnRequest).filter(
        models.ReturnRequest.order_id == order.id,
        models.ReturnRequest.status.notin_(["rejected", "completed"]),
    ).first():
        raise HTTPException(status_code=400, detail="An active return already exists for this order")

    order_items = {oi.id: oi for oi in order.items}
    if not data.items:
        raise HTTPException(status_code=400, detail="Select at least one item to return")

    rr = models.ReturnRequest(
        order_id=order.id, user_id=user.id, kind=data.kind, reason=data.reason, status="requested",
    )
    db.add(rr)
    db.flush()

    refund = Decimal(0)
    for line in data.items:
        oi = order_items.get(line.order_item_id)
        if not oi:
            raise HTTPException(status_code=400, detail="Item is not part of this order")
        if line.quantity < 1 or line.quantity > oi.quantity:
            raise HTTPException(status_code=400, detail="Invalid return quantity")
        db.add(models.ReturnItem(return_id=rr.id, order_item_id=oi.id, quantity=line.quantity))
        refund += money(oi.unit_price) * line.quantity

    rr.refund_amount = money(refund) if data.kind == "return" else Decimal(0)

    db.add(models.Notification(
        user_id=user.id, type="order",
        title=f"{data.kind.title()} request received",
        body=f"We received your {data.kind} request for order {order.order_number}.",
        link=f"/orders/{order.order_number}",
    ))
    db.commit()
    db.refresh(rr)
    return rr


def update_return(db: Session, rr: models.ReturnRequest, data, actor: models.User) -> models.ReturnRequest:
    new_status = data.status
    if new_status:
        rr.status = new_status
        # On refund: restock the returned units + flag the order refunded.
        if new_status == "refunded":
            for ri in rr.items:
                prod = db.get(models.Product, ri.order_item.product_id)
                if prod:
                    prod.stock += ri.quantity
                    db.add(models.StockMovement(
                        product_id=prod.id, change=ri.quantity,
                        reason="return", reference=rr.order.order_number,
                    ))
            rr.order.payment_status = models.PaymentStatus.refunded
            db.add(models.OrderStatusHistory(
                order_id=rr.order_id, status=rr.order.status.value,
                note=f"Refund processed for return #{rr.id}", changed_by_id=actor.id,
            ))
    if data.resolution_note is not None:
        rr.resolution_note = data.resolution_note

    user = db.get(models.User, rr.user_id)
    db.add(models.Notification(
        user_id=rr.user_id, type="order",
        title=f"Return #{rr.id} {rr.status}",
        body=f"Your {rr.kind} for order {rr.order.order_number} is now '{rr.status}'.",
        link=f"/orders/{rr.order.order_number}",
    ))
    if user and user.email:
        notifications.queue_email(
            db, user.email, f"Update on your {rr.kind} (order {rr.order.order_number})",
            f"Status: {rr.status}." + (f"\nNote: {rr.resolution_note}" if rr.resolution_note else ""),
            user_id=user.id,
        )
    db.commit()
    db.refresh(rr)
    return rr
