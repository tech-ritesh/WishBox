"""Admin/staff endpoints: analytics, catalog CRUD, order management, coupons, vendors, uploads."""
import csv
import datetime as dt
import io
import os
import uuid
from collections import defaultdict
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.api.deps import require_admin, require_staff
from app.core.config import settings
from app.core.database import get_db
from app.services import notifications
from app.services.common import audit, money, unique_slug
from app.services.fulfillment import update_return, upsert_shipment
from app.services.orders import change_status

router = APIRouter(prefix="/admin", tags=["Admin"])


# --- Analytics ---
@router.get("/analytics", response_model=schemas.AdminSummaryOut)
def analytics(db: Session = Depends(get_db), _: models.User = Depends(require_staff)):
    paid_orders = db.query(models.Order).filter(
        models.Order.payment_status == models.PaymentStatus.paid
    )
    total_revenue = db.query(func.coalesce(func.sum(models.Order.total_amount), 0)).filter(
        models.Order.payment_status == models.PaymentStatus.paid
    ).scalar() or 0

    sales_by_category = defaultdict(float)
    monthly_sales = defaultdict(float)
    for order in paid_orders.options(joinedload(models.Order.items)).all():
        month = order.created_at.strftime("%Y-%m")
        monthly_sales[month] += float(order.total_amount)
        for it in order.items:
            prod = db.query(models.Product).get(it.product_id)
            if prod and prod.category:
                sales_by_category[prod.category.name] += float(it.unit_price) * it.quantity

    orders_by_status = defaultdict(int)
    for status_val, count in db.query(models.Order.status, func.count(models.Order.id)).group_by(
        models.Order.status
    ).all():
        orders_by_status[status_val.value if hasattr(status_val, "value") else str(status_val)] = count

    recent = (
        db.query(models.Order).options(joinedload(models.Order.items))
        .order_by(models.Order.created_at.desc()).limit(8).all()
    )
    low_stock = db.query(models.Product).filter(
        models.Product.stock <= models.Product.low_stock_threshold, models.Product.is_active.is_(True)
    ).count()

    return {
        "total_revenue": money(total_revenue),
        "total_orders": db.query(models.Order).count(),
        "total_products": db.query(models.Product).count(),
        "total_users": db.query(models.User).filter(models.User.role == models.UserRole.customer).count(),
        "low_stock_count": low_stock,
        "sales_by_category": dict(sales_by_category),
        "monthly_sales": dict(sorted(monthly_sales.items())),
        "orders_by_status": dict(orders_by_status),
        "recent_orders": recent,
    }


# --- Customers ---
@router.get("/customers", response_model=List[schemas.AdminCustomerOut])
def list_customers(db: Session = Depends(get_db), _: models.User = Depends(require_staff)):
    users = db.query(models.User).filter(models.User.role == models.UserRole.customer).all()
    out = []
    for u in users:
        agg = db.query(func.count(models.Order.id), func.coalesce(func.sum(models.Order.total_amount), 0)).filter(
            models.Order.user_id == u.id
        ).one()
        item = schemas.AdminCustomerOut.model_validate(u)
        item.order_count = agg[0]
        item.total_spent = money(agg[1])
        out.append(item)
    return out


# --- Orders ---
@router.get("/orders", response_model=List[schemas.OrderOut])
def all_orders(db: Session = Depends(get_db), _: models.User = Depends(require_staff)):
    return (
        db.query(models.Order)
        .options(joinedload(models.Order.items), joinedload(models.Order.history))
        .order_by(models.Order.created_at.desc()).all()
    )


@router.put("/orders/{order_id}", response_model=schemas.OrderOut)
def update_order(order_id: int, data: schemas.OrderStatusUpdate,
                 db: Session = Depends(get_db), actor: models.User = Depends(require_staff)):
    order = db.query(models.Order).get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return change_status(db, order, data, actor)


# --- Products CRUD ---
def _apply_tags(db: Session, product: models.Product, names: List[str]):
    product.tags.clear()
    for name in names:
        name = name.strip()
        if not name:
            continue
        tag = db.query(models.Tag).filter(func.lower(models.Tag.name) == name.lower()).first()
        if not tag:
            tag = models.Tag(name=name)
            db.add(tag)
            db.flush()
        product.tags.append(tag)


@router.post("/products", response_model=schemas.ProductOut, status_code=201)
def create_product(data: schemas.ProductCreate, db: Session = Depends(get_db),
                   actor: models.User = Depends(require_staff)):
    slug = unique_slug(data.name, lambda s: db.query(models.Product).filter(models.Product.slug == s).first() is not None)
    product = models.Product(
        slug=slug, name=data.name, description=data.description, price=data.price,
        discount_price=data.discount_price, image_url=data.image_url, stock=data.stock,
        category_id=data.category_id, vendor_id=data.vendor_id, sku=data.sku,
        is_customizable=data.is_customizable, type=data.type, is_quick_delivery=data.is_quick_delivery,
    )
    db.add(product)
    db.flush()
    _apply_tags(db, product, data.tags)
    if data.stock:
        db.add(models.StockMovement(product_id=product.id, change=data.stock, reason="restock", reference="initial"))
    audit(db, actor.id, "create_product", entity="product", entity_id=product.id, detail={"name": product.name})
    db.commit()
    db.refresh(product)
    return product


@router.put("/products/{product_id}", response_model=schemas.ProductOut)
def update_product(product_id: int, data: schemas.ProductUpdate, db: Session = Depends(get_db),
                   _: models.User = Depends(require_staff)):
    product = db.query(models.Product).get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    payload = data.model_dump(exclude_unset=True)
    tags = payload.pop("tags", None)
    if "stock" in payload and payload["stock"] != product.stock:
        delta = payload["stock"] - product.stock
        db.add(models.StockMovement(product_id=product.id, change=delta, reason="adjustment", reference="admin"))
    for key, value in payload.items():
        setattr(product, key, value)
    if tags is not None:
        _apply_tags(db, product, tags)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/products/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    product = db.query(models.Product).get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.is_active = False  # soft delete preserves order history
    audit(db, actor.id, "delete_product", entity="product", entity_id=product.id, detail={"name": product.name})
    db.commit()


# --- Categories CRUD ---
@router.post("/categories", response_model=schemas.CategoryOut, status_code=201)
def create_category(data: schemas.CategoryCreate, db: Session = Depends(get_db),
                    _: models.User = Depends(require_staff)):
    slug = unique_slug(data.name, lambda s: db.query(models.Category).filter(models.Category.slug == s).first() is not None)
    cat = models.Category(slug=slug, **data.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.put("/categories/{category_id}", response_model=schemas.CategoryOut)
def update_category(category_id: int, data: schemas.CategoryUpdate, db: Session = Depends(get_db),
                    _: models.User = Depends(require_staff)):
    cat = db.query(models.Category).get(category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(cat, key, value)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: int, db: Session = Depends(get_db), _: models.User = Depends(require_admin)):
    cat = db.query(models.Category).get(category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    cat.is_active = False
    db.commit()


# --- Coupons CRUD ---
@router.get("/coupons", response_model=List[schemas.CouponOut])
def list_coupons(db: Session = Depends(get_db), _: models.User = Depends(require_staff)):
    return db.query(models.Coupon).order_by(models.Coupon.created_at.desc()).all()


@router.post("/coupons", response_model=schemas.CouponOut, status_code=201)
def create_coupon(data: schemas.CouponCreate, db: Session = Depends(get_db),
                  _: models.User = Depends(require_staff)):
    if db.query(models.Coupon).filter(models.Coupon.code == data.code).first():
        raise HTTPException(status_code=400, detail="Coupon code already exists")
    coupon = models.Coupon(**data.model_dump())
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.delete("/coupons/{coupon_id}", status_code=204)
def delete_coupon(coupon_id: int, db: Session = Depends(get_db), _: models.User = Depends(require_admin)):
    coupon = db.query(models.Coupon).get(coupon_id)
    if coupon:
        db.delete(coupon)
        db.commit()


# --- Vendors CRUD ---
@router.get("/vendors", response_model=List[schemas.VendorOut])
def list_vendors(db: Session = Depends(get_db), _: models.User = Depends(require_staff)):
    return db.query(models.Vendor).all()


@router.post("/vendors", response_model=schemas.VendorOut, status_code=201)
def create_vendor(data: schemas.VendorCreate, db: Session = Depends(get_db),
                  _: models.User = Depends(require_admin)):
    vendor = models.Vendor(**data.model_dump())
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


# --- Inventory ---
@router.get("/inventory/low-stock", response_model=List[schemas.ProductOut])
def low_stock(db: Session = Depends(get_db), _: models.User = Depends(require_staff)):
    return db.query(models.Product).filter(
        models.Product.stock <= models.Product.low_stock_threshold,
        models.Product.is_active.is_(True),
    ).all()


# --- FAQ management ---
@router.post("/faqs", response_model=schemas.FaqOut, status_code=201)
def create_faq(data: schemas.FaqCreate, db: Session = Depends(get_db), _: models.User = Depends(require_staff)):
    faq = models.FaqEntry(**data.model_dump())
    db.add(faq); db.commit(); db.refresh(faq)
    return faq


@router.put("/faqs/{faq_id}", response_model=schemas.FaqOut)
def update_faq(faq_id: int, data: schemas.FaqCreate, db: Session = Depends(get_db), _: models.User = Depends(require_staff)):
    faq = db.get(models.FaqEntry, faq_id)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    for k, v in data.model_dump().items():
        setattr(faq, k, v)
    db.commit(); db.refresh(faq)
    return faq


@router.delete("/faqs/{faq_id}", status_code=204)
def delete_faq(faq_id: int, db: Session = Depends(get_db), _: models.User = Depends(require_staff)):
    faq = db.get(models.FaqEntry, faq_id)
    if faq:
        db.delete(faq); db.commit()


# --- Support tickets ---
@router.get("/tickets", response_model=List[schemas.TicketOut])
def list_tickets(status: str = None, db: Session = Depends(get_db), _: models.User = Depends(require_staff)):
    q = db.query(models.SupportTicket).options(joinedload(models.SupportTicket.messages))
    if status:
        q = q.filter(models.SupportTicket.status == status)
    return q.order_by(models.SupportTicket.created_at.desc()).all()


@router.post("/tickets/{ticket_id}/reply", response_model=schemas.TicketOut)
def staff_reply(ticket_id: int, data: schemas.TicketReply, db: Session = Depends(get_db),
                actor: models.User = Depends(require_staff)):
    ticket = db.get(models.SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    db.add(models.TicketMessage(ticket_id=ticket.id, user_id=actor.id, body=data.body, is_staff=True))
    ticket.status = "pending"
    user = db.get(models.User, ticket.user_id)
    db.add(models.Notification(user_id=ticket.user_id, type="info",
                               title=f"Reply to '{ticket.subject}'", body=data.body[:120], link="/account"))
    if user and user.email:
        notifications.queue_email(db, user.email, f"Re: {ticket.subject}", data.body, user_id=user.id)
    db.commit(); db.refresh(ticket)
    return ticket


@router.put("/tickets/{ticket_id}", response_model=schemas.TicketOut)
def update_ticket(ticket_id: int, data: schemas.TicketStatusUpdate, db: Session = Depends(get_db),
                  _: models.User = Depends(require_staff)):
    ticket = db.get(models.SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.status = data.status
    db.commit(); db.refresh(ticket)
    return ticket


# --- Review moderation ---
@router.get("/reviews", response_model=List[schemas.ReviewOut])
def list_all_reviews(status: str = None, db: Session = Depends(get_db), _: models.User = Depends(require_staff)):
    q = db.query(models.Review)
    if status:
        q = q.filter(models.Review.status == status)
    rows = q.order_by(models.Review.created_at.desc()).limit(200).all()
    out = []
    for r in rows:
        item = schemas.ReviewOut.model_validate(r)
        item.user_name = r.user.full_name if r.user else "Anonymous"
        out.append(item)
    return out


@router.put("/reviews/{review_id}", response_model=schemas.ReviewOut)
def moderate_review(review_id: int, data: schemas.ReviewModerate,
                    db: Session = Depends(get_db), _: models.User = Depends(require_staff)):
    review = db.get(models.Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    review.status = data.status
    db.flush()
    # keep product aggregate in sync with only-approved reviews
    avg, cnt = db.query(func.avg(models.Review.rating), func.count(models.Review.id)).filter(
        models.Review.product_id == review.product_id, models.Review.status == "approved"
    ).one()
    product = db.get(models.Product, review.product_id)
    if product:
        product.rating_avg = round(float(avg or 0), 2)
        product.rating_count = int(cnt or 0)
    db.commit()
    db.refresh(review)
    out = schemas.ReviewOut.model_validate(review)
    out.user_name = review.user.full_name if review.user else "Anonymous"
    return out


# --- Product variants ---
@router.get("/products/{product_id}/variants", response_model=List[schemas.ProductVariantOut])
def list_variants(product_id: int, db: Session = Depends(get_db), _: models.User = Depends(require_staff)):
    return db.query(models.ProductVariant).filter(
        models.ProductVariant.product_id == product_id
    ).order_by(models.ProductVariant.id.asc()).all()


@router.post("/products/{product_id}/variants", response_model=schemas.ProductVariantOut, status_code=201)
def create_variant(product_id: int, data: schemas.ProductVariantCreate,
                   db: Session = Depends(get_db), _: models.User = Depends(require_admin)):
    if not db.get(models.Product, product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    variant = models.ProductVariant(product_id=product_id, **data.model_dump())
    db.add(variant)
    db.commit()
    db.refresh(variant)
    return variant


@router.delete("/variants/{variant_id}", status_code=204)
def delete_variant(variant_id: int, db: Session = Depends(get_db), _: models.User = Depends(require_admin)):
    v = db.get(models.ProductVariant, variant_id)
    if v:
        db.delete(v)
        db.commit()


# --- Shipping ---
@router.post("/orders/{order_id}/shipment", response_model=schemas.ShipmentOut)
def upsert_order_shipment(order_id: int, data: schemas.ShipmentUpdate,
                          db: Session = Depends(get_db), _: models.User = Depends(require_staff)):
    order = db.get(models.Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return upsert_shipment(db, order, data)


# --- Returns ---
@router.get("/returns", response_model=List[schemas.ReturnOut])
def list_all_returns(status: str = None, db: Session = Depends(get_db),
                     _: models.User = Depends(require_staff)):
    q = db.query(models.ReturnRequest)
    if status:
        q = q.filter(models.ReturnRequest.status == status)
    return q.order_by(models.ReturnRequest.id.desc()).all()


@router.put("/returns/{return_id}", response_model=schemas.ReturnOut)
def update_return_request(return_id: int, data: schemas.ReturnUpdate,
                          db: Session = Depends(get_db), actor: models.User = Depends(require_staff)):
    rr = db.get(models.ReturnRequest, return_id)
    if not rr:
        raise HTTPException(status_code=404, detail="Return not found")
    return update_return(db, rr, data, actor)


# --- Outbox (email/SMS) + worker ---
@router.get("/outbox", response_model=List[schemas.OutboxMessageOut])
def list_outbox(status: str = None, limit: int = 100,
                db: Session = Depends(get_db), _: models.User = Depends(require_staff)):
    q = db.query(models.OutboxMessage)
    if status:
        q = q.filter(models.OutboxMessage.status == status)
    return q.order_by(models.OutboxMessage.id.desc()).limit(min(limit, 200)).all()


@router.post("/worker/run-tick")
def run_worker_tick(db: Session = Depends(get_db), _: models.User = Depends(require_admin)):
    """Manually run one worker tick (fire due reminders + flush outbox). Handy for demos."""
    from app.services.worker import run_tick
    return run_tick(db)


# --- CMS banners ---
@router.get("/banners", response_model=List[schemas.BannerOut])
def admin_list_banners(db: Session = Depends(get_db), _: models.User = Depends(require_staff)):
    return db.query(models.Banner).order_by(models.Banner.sort_order.asc(), models.Banner.id.desc()).all()


@router.post("/banners", response_model=schemas.BannerOut, status_code=201)
def create_banner(data: schemas.BannerCreate, db: Session = Depends(get_db), _: models.User = Depends(require_admin)):
    banner = models.Banner(**data.model_dump())
    db.add(banner); db.commit(); db.refresh(banner)
    return banner


@router.delete("/banners/{banner_id}", status_code=204)
def delete_banner(banner_id: int, db: Session = Depends(get_db), _: models.User = Depends(require_admin)):
    b = db.get(models.Banner, banner_id)
    if b:
        db.delete(b); db.commit()


# --- Audit log viewer ---
@router.get("/audit-logs", response_model=List[schemas.AuditLogOut])
def list_audit_logs(limit: int = 100, db: Session = Depends(get_db), _: models.User = Depends(require_admin)):
    return db.query(models.AuditLog).order_by(models.AuditLog.id.desc()).limit(min(limit, 500)).all()


# --- Bulk product import (CSV) ---
@router.post("/products/bulk-import")
async def bulk_import_products(file: UploadFile = File(...), db: Session = Depends(get_db),
                               actor: models.User = Depends(require_admin)):
    """CSV columns: name, price, stock, category_id[, description, sku, discount_price, type]."""
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    created, errors = 0, []
    for i, row in enumerate(reader, start=2):  # row 1 is the header
        try:
            name = (row.get("name") or "").strip()
            if not name:
                raise ValueError("missing name")
            cat_id = int(row["category_id"])
            if not db.get(models.Category, cat_id):
                raise ValueError(f"category_id {cat_id} not found")
            slug = unique_slug(name, lambda s: db.query(models.Product).filter(models.Product.slug == s).first() is not None)
            db.add(models.Product(
                name=name, slug=slug, description=row.get("description") or None,
                price=money(row.get("price") or 0),
                discount_price=money(row["discount_price"]) if row.get("discount_price") else None,
                stock=int(row.get("stock") or 0), category_id=cat_id,
                sku=row.get("sku") or None, type=row.get("type") or "hamper",
            ))
            created += 1
        except Exception as e:  # collect per-row errors, keep importing
            errors.append({"row": i, "error": str(e)})
    audit(db, actor.id, "bulk_import_products", entity="product", detail={"created": created, "errors": len(errors)})
    db.commit()
    return {"created": created, "errors": errors}


# --- Sales report (CSV export) ---
@router.get("/reports/sales.csv")
def sales_report_csv(db: Session = Depends(get_db), _: models.User = Depends(require_staff)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["order_number", "created_at", "status", "payment_status", "subtotal", "discount", "shipping", "total"])
    for o in db.query(models.Order).order_by(models.Order.created_at.desc()).all():
        w.writerow([o.order_number, o.created_at.isoformat(), o.status.value, o.payment_status.value,
                    o.subtotal, o.discount_amount, o.shipping_fee, o.total_amount])
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=wishbox-sales.csv"})


# --- Image upload (validated) ---
@router.post("/upload")
def upload_image(file: UploadFile = File(...), _: models.User = Depends(require_staff)):
    if file.content_type not in settings.ALLOWED_UPLOAD_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    contents = file.file.read()
    if len(contents) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")
    ext = os.path.splitext(file.filename or "")[1].lower() or ".png"
    name = f"{uuid.uuid4().hex}{ext}"
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(os.path.join(settings.UPLOAD_DIR, name), "wb") as f:
        f.write(contents)
    return {"image_url": f"/static/uploads/{name}"}
