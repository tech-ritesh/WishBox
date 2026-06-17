"""Payment gateway integration with a pluggable adapter.

By default WishBox runs a fully-local MOCK gateway (no network, no keys) so the
checkout flow works offline. Set WISHBOX_PAYMENT_PROVIDER=razorpay and supply
WISHBOX_RAZORPAY_KEY_ID / WISHBOX_RAZORPAY_KEY_SECRET in .env to switch to the
real Razorpay API — no code change required (adapter is selected at runtime).

The COD flow is untouched: COD orders never enter this module.
"""
from __future__ import annotations

import hashlib
import hmac
import random
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models
from app.core.config import settings
from app.services.common import money


# --- Adapters ----------------------------------------------------------------
class MockGateway:
    """Deterministic offline gateway. Verifies a signature we generate ourselves."""

    provider = "mock"

    def create_order(self, amount: Decimal, currency: str, receipt: str) -> dict:
        # amount in minor units (paise), mirroring Razorpay's contract
        oid = f"mock_order_{receipt}_{random.randint(1000, 9999)}"
        return {"id": oid, "amount": int(money(amount) * 100), "currency": currency, "status": "created"}

    def verify_signature(self, provider_order_id: str, provider_payment_id: str, signature: str) -> bool:
        expected = self._sign(provider_order_id, provider_payment_id)
        return hmac.compare_digest(expected, signature or "")

    def _sign(self, order_id: str, payment_id: str) -> str:
        msg = f"{order_id}|{payment_id}".encode()
        key = (settings.SECRET_KEY or "mock").encode()
        return hmac.new(key, msg, hashlib.sha256).hexdigest()

    def simulate_payment_id(self, provider_order_id: str) -> dict:
        """Helper used by the mock 'pay now' endpoint to produce a valid pair."""
        pid = f"mock_pay_{random.randint(100000, 999999)}"
        return {"payment_id": pid, "signature": self._sign(provider_order_id, pid)}


class RazorpayGateway:
    """Thin wrapper over the razorpay SDK. Only imported when keys are configured."""

    provider = "razorpay"

    def __init__(self):
        import razorpay  # lazy import; only needed in real mode
        self._client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    def create_order(self, amount: Decimal, currency: str, receipt: str) -> dict:
        return self._client.order.create({
            "amount": int(money(amount) * 100),
            "currency": currency,
            "receipt": receipt,
            "payment_capture": 1,
        })

    def verify_signature(self, provider_order_id: str, provider_payment_id: str, signature: str) -> bool:
        try:
            self._client.utility.verify_payment_signature({
                "razorpay_order_id": provider_order_id,
                "razorpay_payment_id": provider_payment_id,
                "razorpay_signature": signature,
            })
            return True
        except Exception:
            return False


def get_gateway():
    if settings.razorpay_enabled:
        return RazorpayGateway()
    return MockGateway()


# --- Service API -------------------------------------------------------------
def _order_for_user(db: Session, user: models.User, order_number: str) -> models.Order:
    order = db.query(models.Order).filter(
        models.Order.order_number == order_number,
        models.Order.user_id == user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def create_payment(db: Session, user: models.User, order_number: str) -> dict:
    """Create a gateway order for an existing (unpaid) WishBox order."""
    order = _order_for_user(db, user, order_number)
    if order.payment_status == models.PaymentStatus.paid:
        raise HTTPException(status_code=400, detail="Order is already paid")

    gw = get_gateway()
    g_order = gw.create_order(money(order.total_amount), "INR", order.order_number)

    payment = models.Payment(
        order_id=order.id,
        provider=gw.provider,
        amount=money(order.total_amount),
        currency="INR",
        provider_order_id=g_order["id"],
        status=models.PaymentStatus.pending,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    resp = {
        "provider": gw.provider,
        "provider_order_id": g_order["id"],
        "amount": g_order["amount"],          # minor units (paise)
        "currency": g_order.get("currency", "INR"),
        "order_number": order.order_number,
        "key_id": settings.RAZORPAY_KEY_ID if gw.provider == "razorpay" else "mock",
    }
    # Convenience for the mock gateway: hand the frontend a valid payment_id+signature
    if gw.provider == "mock":
        resp["mock"] = gw.simulate_payment_id(g_order["id"])
    return resp


def verify_payment(db: Session, user: models.User, data) -> models.Order:
    """Verify a gateway callback and, on success, mark the order paid + confirmed."""
    payment = (
        db.query(models.Payment)
        .filter(models.Payment.provider_order_id == data.provider_order_id)
        .join(models.Order)
        .filter(models.Order.user_id == user.id)
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    gw = get_gateway()
    ok = gw.verify_signature(data.provider_order_id, data.provider_payment_id, data.provider_signature)
    order = payment.order

    if not ok:
        payment.status = models.PaymentStatus.failed
        payment.error_reason = "Signature verification failed"
        db.add(models.OrderStatusHistory(
            order_id=order.id, status=order.status.value, note="Payment verification failed",
        ))
        db.commit()
        raise HTTPException(status_code=400, detail="Payment verification failed")

    payment.provider_payment_id = data.provider_payment_id
    payment.provider_signature = data.provider_signature
    payment.status = models.PaymentStatus.paid

    order.payment_status = models.PaymentStatus.paid
    if order.status == models.OrderStatus.pending:
        order.status = models.OrderStatus.confirmed
    db.add(models.OrderStatusHistory(
        order_id=order.id, status=order.status.value, note="Payment received",
    ))
    db.add(models.Notification(
        user_id=order.user_id, type="order",
        title="Payment successful",
        body=f"We received your payment for order {order.order_number}.",
        link=f"/orders/{order.order_number}",
    ))
    db.commit()
    db.refresh(order)
    return order
