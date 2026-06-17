"""Coupon validation & discount computation (single source of truth)."""
import datetime as dt
from decimal import Decimal
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app import models
from app.services.common import money


class CouponError(Exception):
    pass


def evaluate_coupon(
    db: Session, code: str, subtotal: Decimal, user_id: Optional[int]
) -> Tuple[models.Coupon, Decimal]:
    """Returns (coupon, discount). Raises CouponError with a user-facing message."""
    coupon = db.query(models.Coupon).filter(models.Coupon.code == code, models.Coupon.active.is_(True)).first()
    if not coupon:
        raise CouponError("Invalid coupon code")

    if coupon.expiry_date and coupon.expiry_date < dt.datetime.now(dt.timezone.utc).replace(tzinfo=None):
        raise CouponError("Coupon has expired")

    if subtotal < money(coupon.min_order_value):
        raise CouponError(f"Minimum order value for this coupon is ₹{coupon.min_order_value}")

    if coupon.usage_limit is not None and coupon.times_used >= coupon.usage_limit:
        raise CouponError("Coupon usage limit reached")

    if coupon.per_user_limit is not None and user_id is not None:
        used = (
            db.query(models.CouponRedemption)
            .filter(
                models.CouponRedemption.coupon_id == coupon.id,
                models.CouponRedemption.user_id == user_id,
            )
            .count()
        )
        if used >= coupon.per_user_limit:
            raise CouponError("You have already used this coupon")

    if coupon.discount_type == "flat":
        discount = money(coupon.discount_value)
    else:  # percentage
        discount = money(subtotal * money(coupon.discount_value) / Decimal(100))
        if coupon.max_discount:
            discount = min(discount, money(coupon.max_discount))

    discount = min(discount, subtotal)
    return coupon, discount
