from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.core.database import get_db

router = APIRouter(prefix="/products", tags=["Products"])


def _effective_price():
    return func.coalesce(models.Product.discount_price, models.Product.price)


def _descendant_ids(db: Session, category: models.Category) -> List[int]:
    all_cats = db.query(models.Category.id, models.Category.parent_id).all()
    children = {}
    for cid, pid in all_cats:
        children.setdefault(pid, []).append(cid)
    collected, stack = [], [category.id]
    while stack:
        cur = stack.pop()
        collected.append(cur)
        stack.extend(children.get(cur, []))
    return collected


@router.get("", response_model=schemas.PaginatedProducts)
def list_products(
    category: Optional[str] = None,
    occasion: Optional[str] = None,
    tag: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    customizable: Optional[bool] = None,
    type: Optional[str] = None,
    q: Optional[str] = None,
    sort: Optional[str] = None,
    in_stock: Optional[bool] = None,
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(models.Product).filter(models.Product.is_active.is_(True))

    if category:
        cat = db.query(models.Category).filter(models.Category.slug == category).first()
        if cat:
            query = query.filter(models.Product.category_id.in_(_descendant_ids(db, cat)))
        else:
            return {"total": 0, "limit": limit, "offset": offset, "items": []}

    if tag or occasion:
        wanted = (tag or occasion).lower()
        query = query.join(models.Product.tags).filter(func.lower(models.Tag.name) == wanted)

    eff = _effective_price()
    if price_min is not None:
        query = query.filter(eff >= price_min)
    if price_max is not None:
        query = query.filter(eff <= price_max)
    if customizable is not None:
        query = query.filter(models.Product.is_customizable.is_(customizable))
    if type:
        query = query.filter(models.Product.type == type)
    if in_stock:
        query = query.filter(models.Product.stock > 0)
    if q:
        query = query.filter(or_(
            models.Product.name.ilike(f"%{q}%"),
            models.Product.description.ilike(f"%{q}%"),
        ))

    if sort == "price_asc":
        query = query.order_by(eff.asc())
    elif sort == "price_desc":
        query = query.order_by(eff.desc())
    elif sort == "newest":
        query = query.order_by(models.Product.created_at.desc())
    elif sort == "rating":
        query = query.order_by(models.Product.rating_avg.desc())
    else:
        query = query.order_by(models.Product.id.asc())

    total = query.distinct().count()
    items = query.distinct().offset(offset).limit(limit).all()
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/quick-delivery", response_model=List[schemas.ProductOut])
def quick_delivery(db: Session = Depends(get_db)):
    return (
        db.query(models.Product)
        .filter(models.Product.is_quick_delivery.is_(True),
                models.Product.stock > 0, models.Product.is_active.is_(True))
        .all()
    )


@router.get("/{slug}", response_model=schemas.ProductDetailOut)
def product_detail(slug: str, db: Session = Depends(get_db)):
    product = (
        db.query(models.Product)
        .options(joinedload(models.Product.images), joinedload(models.Product.tags),
                 joinedload(models.Product.category))
        .filter(models.Product.slug == slug)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.view_count = (product.view_count or 0) + 1
    db.commit()
    return product
