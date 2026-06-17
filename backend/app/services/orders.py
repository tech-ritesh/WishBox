"""Order placement: pricing, inventory decrement, coupon redemption, timeline.

All of this lives in the service layer (the reference project inlined it in the
route handler). Stock is decremented inside the same transaction and recorded in
the StockMovement ledger, preventing oversell.
"""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models
from app.services import notifications
from app.services.common import generate_order_number, money
from app.services.coupons import CouponError, evaluate_coupon

FREE_SHIPPING_THRESHOLD = Decimal("999")
SHIPPING_FEE = Decimal("49")


def _line_price(item: models.CartItem, db: Session) -> Decimal:
    """Base effective price + customization add-on costs."""
    price = money(item.product.effective_price)
    details = item.customization_details or {}
    if item.product.is_customizable and details:
        for key in ("packaging", "card"):
            opt = details.get(key) or {}
            price += money(opt.get("price", 0))
        for addon in details.get("addons", []) or []:
            price += money(addon.get("price", 0))
    return price


def place_order(db: Session, user: models.User, data) -> models.Order:
    cart_items = db.query(models.CartItem).filter(models.CartItem.user_id == user.id).all()
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    address = (
        db.query(models.Address)
        .filter(models.Address.id == data.address_id, models.Address.user_id == user.id)
        .first()
    )
    if not address:
        raise HTTPException(status_code=400, detail="Invalid shipping address")

    # Validate stock up front (avoid partial commits)
    for item in cart_items:
        if not item.product.is_active:
            raise HTTPException(status_code=400, detail=f"'{item.product.name}' is no longer available")
        if item.product.stock < item.quantity:
            raise HTTPException(
                status_code=409,
                detail=f"Insufficient stock for '{item.product.name}' (have {item.product.stock})",
            )

    subtotal = Decimal(0)
    line_data = []
    for item in cart_items:
        unit = _line_price(item, db)
        subtotal += unit * item.quantity
        line_data.append((item, unit))
    subtotal = money(subtotal)

    # Coupon
    discount = Decimal(0)
    coupon = None
    if data.coupon_code:
        try:
            coupon, discount = evaluate_coupon(db, data.coupon_code, subtotal, user.id)
        except CouponError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Corporate discount stacks on top (flat % of subtotal)
    if user.corporate_account and user.corporate_account.discount_percentage:
        corp = money(subtotal * money(user.corporate_account.discount_percentage) / Decimal(100))
        discount = money(discount + corp)

    discounted = max(subtotal - discount, Decimal(0))
    shipping = Decimal(0) if discounted >= FREE_SHIPPING_THRESHOLD else SHIPPING_FEE
    total = money(discounted + shipping)

    order = models.Order(
        user_id=user.id,
        order_number=generate_order_number(),
        subtotal=subtotal,
        discount_amount=money(discount),
        shipping_fee=shipping,
        total_amount=total,
        recipient_name=address.recipient_name,
        recipient_phone=address.phone,
        ship_address_line1=address.address_line1,
        ship_address_line2=address.address_line2,
        ship_city=address.city,
        ship_state=address.state,
        ship_postal_code=address.postal_code,
        ship_country=address.country,
        is_gift=data.is_gift,
        gift_message=data.gift_message,
        scheduled_delivery_date=data.scheduled_delivery_date,
        delivery_slot=data.delivery_slot,
        payment_method=data.payment_method,
        payment_status=models.PaymentStatus.paid if data.payment_method == "cod" else models.PaymentStatus.pending,
        status=models.OrderStatus.confirmed if data.payment_method == "cod" else models.OrderStatus.pending,
        tracking_code=None,
        coupon_code=data.coupon_code,
    )
    db.add(order)
    db.flush()  # get order.id without committing

    for item, unit in line_data:
        db.add(models.OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            product_name=item.product.name,
            unit_price=unit,
            quantity=item.quantity,
            customization_details=item.customization_details,
        ))
        # Decrement stock + ledger entry
        item.product.stock -= item.quantity
        db.add(models.StockMovement(
            product_id=item.product_id,
            change=-item.quantity,
            reason="order",
            reference=order.order_number,
        ))

    db.add(models.OrderStatusHistory(order_id=order.id, status=order.status.value, note="Order placed"))

    if coupon:
        coupon.times_used += 1
        db.add(models.CouponRedemption(coupon_id=coupon.id, user_id=user.id, order_id=order.id))

    # In-app notification
    db.add(models.Notification(
        user_id=user.id, type="order",
        title="Order placed",
        body=f"Your order {order.order_number} has been placed successfully.",
        link=f"/orders/{order.order_number}",
    ))
    # Queue confirmation email (dispatched by the worker; console in offline mode)
    if user.email:
        notifications.queue_email(
            db, user.email, f"Order {order.order_number} confirmed",
            f"Hi {user.full_name}, your WishBox order {order.order_number} for "
            f"{order.total_amount} {('INR')} is confirmed. Track it any time in your account.",
            user_id=user.id,
        )

    # Clear cart
    db.query(models.CartItem).filter(models.CartItem.user_id == user.id).delete()
    db.commit()
    db.refresh(order)
    return order


def change_status(db: Session, order: models.Order, data, actor: models.User) -> models.Order:
    changed = []
    if data.status and data.status != order.status.value:
        order.status = models.OrderStatus(data.status)
        changed.append(f"status→{data.status}")
        # Restock on cancellation
        if data.status == models.OrderStatus.cancelled.value:
            for it in order.items:
                prod = db.query(models.Product).get(it.product_id)
                if prod:
                    prod.stock += it.quantity
                    db.add(models.StockMovement(
                        product_id=prod.id, change=it.quantity,
                        reason="cancel", reference=order.order_number,
                    ))
    if data.payment_status:
        order.payment_status = models.PaymentStatus(data.payment_status)
        changed.append(f"payment→{data.payment_status}")
    if data.tracking_code is not None:
        order.tracking_code = data.tracking_code

    db.add(models.OrderStatusHistory(
        order_id=order.id, status=order.status.value,
        note=data.note or (", ".join(changed) if changed else "Updated"),
        changed_by_id=actor.id,
    ))
    db.add(models.Notification(
        user_id=order.user_id, type="order",
        title=f"Order {order.order_number} updated",
        body=f"Status: {order.status.value}",
        link=f"/orders/{order.order_number}",
    ))
    db.commit()
    db.refresh(order)
    return order
