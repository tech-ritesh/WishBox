"""Admin/staff endpoints: analytics, catalog CRUD, order management, coupons, vendors, uploads."""
import datetime as dt
import os
import uuid
from collections import defaultdict
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.api.deps import require_admin, require_staff
from app.core.config import settings
from app.core.database import get_db
from app.services.common import money, unique_slug
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
                   _: models.User = Depends(require_staff)):
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
def delete_product(product_id: int, db: Session = Depends(get_db), _: models.User = Depends(require_admin)):
    product = db.query(models.Product).get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.is_active = False  # soft delete preserves order history
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
