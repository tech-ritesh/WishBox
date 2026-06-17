from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.api.deps import get_current_user
from app.core.database import get_db
from app.services.common import money

router = APIRouter(prefix="/cart", tags=["Cart"])


def _summary(db: Session, user_id: int) -> dict:
    items = (
        db.query(models.CartItem)
        .options(joinedload(models.CartItem.product))
        .filter(models.CartItem.user_id == user_id)
        .all()
    )
    subtotal = sum((money(i.product.effective_price) * i.quantity for i in items), Decimal(0))
    return {"items": items, "subtotal": money(subtotal), "item_count": sum(i.quantity for i in items)}


@router.get("", response_model=schemas.CartSummary)
def get_cart(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _summary(db, current_user.id)


@router.post("", response_model=schemas.CartSummary, status_code=201)
def add_to_cart(data: schemas.CartItemCreate, current_user: models.User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(
        models.Product.id == data.product_id, models.Product.is_active.is_(True)
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.stock < data.quantity:
        raise HTTPException(status_code=409, detail="Not enough stock")

    existing = db.query(models.CartItem).filter(
        models.CartItem.user_id == current_user.id,
        models.CartItem.product_id == data.product_id,
    ).first()
    if existing and not data.customization_details:
        existing.quantity += data.quantity
    else:
        db.add(models.CartItem(
            user_id=current_user.id, product_id=data.product_id,
            quantity=data.quantity, customization_details=data.customization_details,
        ))
    db.commit()
    return _summary(db, current_user.id)


@router.put("/{item_id}", response_model=schemas.CartSummary)
def update_cart_item(item_id: int, data: schemas.CartItemUpdate,
                     current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(models.CartItem).filter(
        models.CartItem.id == item_id, models.CartItem.user_id == current_user.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    item.quantity = data.quantity
    if data.customization_details is not None:
        item.customization_details = data.customization_details
    db.commit()
    return _summary(db, current_user.id)


@router.delete("/{item_id}", response_model=schemas.CartSummary)
def remove_cart_item(item_id: int, current_user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    item = db.query(models.CartItem).filter(
        models.CartItem.id == item_id, models.CartItem.user_id == current_user.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    db.delete(item)
    db.commit()
    return _summary(db, current_user.id)


@router.delete("", status_code=204)
def clear_cart(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(models.CartItem).filter(models.CartItem.user_id == current_user.id).delete()
    db.commit()
