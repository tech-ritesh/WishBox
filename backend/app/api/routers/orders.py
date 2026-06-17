from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.api.deps import get_current_user
from app.core.database import get_db
from app.services.orders import place_order
from app.services.tax import get_or_create_invoice

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("", response_model=schemas.OrderOut, status_code=201)
def create_order(data: schemas.OrderCreate, current_user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    return place_order(db, current_user, data)


@router.get("", response_model=List[schemas.OrderOut])
def my_orders(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(models.Order)
        .options(joinedload(models.Order.items), joinedload(models.Order.history))
        .filter(models.Order.user_id == current_user.id)
        .order_by(models.Order.created_at.desc())
        .all()
    )


@router.get("/{order_number}", response_model=schemas.OrderOut)
def get_order(order_number: str, current_user: models.User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(
        models.Order.order_number == order_number,
        models.Order.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/{order_number}/invoice", response_model=schemas.InvoiceOut)
def get_invoice(order_number: str, current_user: models.User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(
        models.Order.order_number == order_number,
        models.Order.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return get_or_create_invoice(db, order)
