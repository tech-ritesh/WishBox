"""Online payment endpoints (Razorpay / local mock).

COD orders do not use these routes — they are confirmed at placement time.
For online orders (payment_method != 'cod'), the order is created in `pending`
state, the frontend calls /payments/create, runs the gateway checkout, then
calls /payments/verify to confirm.
"""
from fastapi import APIRouter, Depends, Request

from app import models, schemas
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.services import payments as payment_service
from sqlalchemy.orm import Session

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.get("/config")
def payment_config():
    """Public: tells the frontend which gateway is active + the publishable key."""
    return {
        "provider": "razorpay" if settings.razorpay_enabled else "mock",
        "key_id": settings.RAZORPAY_KEY_ID if settings.razorpay_enabled else "mock",
    }


@router.post("/create", response_model=schemas.PaymentCreateResponse)
def create_payment(data: schemas.PaymentCreateRequest,
                   current_user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    return payment_service.create_payment(db, current_user, data.order_number)


@router.post("/verify", response_model=schemas.OrderOut)
def verify_payment(data: schemas.PaymentVerifyRequest,
                   current_user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    return payment_service.verify_payment(db, current_user, data)


@router.post("/webhook")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """Razorpay server-to-server webhook (no-op in mock mode). Best-effort idempotent."""
    payload = await request.json()
    entity = (payload.get("payload", {}).get("payment", {}).get("entity", {}))
    provider_order_id = entity.get("order_id")
    provider_payment_id = entity.get("id")
    if provider_order_id and provider_payment_id:
        payment = (
            db.query(models.Payment)
            .filter(models.Payment.provider_order_id == provider_order_id)
            .first()
        )
        if payment and payment.status != models.PaymentStatus.paid:
            payment.provider_payment_id = provider_payment_id
            payment.status = models.PaymentStatus.paid
            order = payment.order
            order.payment_status = models.PaymentStatus.paid
            if order.status == models.OrderStatus.pending:
                order.status = models.OrderStatus.confirmed
            db.add(models.OrderStatusHistory(
                order_id=order.id, status=order.status.value, note="Payment confirmed (webhook)",
            ))
            db.commit()
    return {"status": "ok"}
