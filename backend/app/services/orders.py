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
from app.core.security import hash_password
import secrets

FREE_SHIPPING_THRESHOLD = Decimal("999")
SHIPPING_FEE = Decimal("49")


def _line_price(item: models.CartItem, db: Session) -> Decimal:
    """Base effective price (+ variant delta) + customization add-on costs."""
    price = money(item.product.effective_price)
    if item.variant is not None:
        price += money(item.variant.price_delta)
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

    # Validate stock up front (avoid partial commits). Variant stock when present.
    for item in cart_items:
        if not item.product.is_active:
            raise HTTPException(status_code=400, detail=f"'{item.product.name}' is no longer available")
        available = item.variant.stock if item.variant else item.product.stock
        if available < item.quantity:
            raise HTTPException(
                status_code=409,
                detail=f"Insufficient stock for '{item.product.name}' (have {available})",
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
            variant_id=item.variant_id,
            product_name=item.product.name,
            variant_name=item.variant.name if item.variant else None,
            unit_price=unit,
            quantity=item.quantity,
            customization_details=item.customization_details,
        ))
        # Decrement stock (variant if present, else product) + ledger entry
        if item.variant is not None:
            item.variant.stock -= item.quantity
        else:
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


def place_guest_order(db: Session, data) -> models.Order:
    """Guest checkout: reuses the authenticated order path via a shadow account.

    A lightweight is_guest user (keyed by email) is created/reused, the posted
    items are staged as its cart + a transient address, then the normal
    place_order runs — so pricing, coupons, stock, invoice and emails all behave
    identically to a logged-in order.
    """
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if user and not user.is_guest:
        raise HTTPException(status_code=409, detail="An account exists for this email — please log in to check out")
    if not user:
        user = models.User(
            email=data.email,
            password_hash=hash_password(secrets.token_urlsafe(16)),  # unusable until claimed
            full_name=data.full_name,
            phone=data.phone,
            role=models.UserRole.customer,
            is_guest=True,
        )
        db.add(user)
        db.flush()

    if not data.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Transient shipping address
    address = models.Address(
        user_id=user.id, recipient_name=data.recipient_name or data.full_name,
        phone=data.phone or "", address_line1=data.address_line1, address_line2=data.address_line2,
        city=data.city, state=data.state, postal_code=data.postal_code, country=data.country or "India",
    )
    db.add(address)
    db.flush()

    # Stage the posted items as the guest's cart
    db.query(models.CartItem).filter(models.CartItem.user_id == user.id).delete()
    for it in data.items:
        db.add(models.CartItem(
            user_id=user.id, product_id=it.product_id, variant_id=it.variant_id,
            quantity=it.quantity, customization_details=it.customization_details,
        ))
    db.flush()

    order_input = OrderInput(
        address_id=address.id, payment_method=data.payment_method, coupon_code=data.coupon_code,
        is_gift=data.is_gift, gift_message=data.gift_message,
        scheduled_delivery_date=data.scheduled_delivery_date, delivery_slot=data.delivery_slot,
    )
    return place_order(db, user, order_input)


class OrderInput:
    """Lightweight adapter so place_order can consume guest data unchanged."""
    def __init__(self, address_id, payment_method, coupon_code, is_gift, gift_message,
                 scheduled_delivery_date, delivery_slot):
        self.address_id = address_id
        self.payment_method = payment_method
        self.coupon_code = coupon_code
        self.is_gift = is_gift
        self.gift_message = gift_message
        self.scheduled_delivery_date = scheduled_delivery_date
        self.delivery_slot = delivery_slot


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
