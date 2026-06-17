from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.api.deps import get_current_user
from app.core.database import get_db
from app.services.fulfillment import create_return
from app.services.orders import place_order
from app.services.tax import get_or_create_invoice

router = APIRouter(prefix="/orders", tags=["Orders"])


def _my_order(db: Session, user: models.User, order_number: str) -> models.Order:
    order = db.query(models.Order).filter(
        models.Order.order_number == order_number,
        models.Order.user_id == user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


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


@router.get("/{order_number}/shipment", response_model=schemas.ShipmentOut)
def get_shipment(order_number: str, current_user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    order = _my_order(db, current_user, order_number)
    shipment = db.query(models.Shipment).filter(models.Shipment.order_id == order.id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="No shipment yet")
    return shipment


@router.post("/{order_number}/returns", response_model=schemas.ReturnOut, status_code=201)
def request_return(order_number: str, data: schemas.ReturnCreate,
                   current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = _my_order(db, current_user, order_number)
    return create_return(db, current_user, order, data)


@router.get("/{order_number}/returns", response_model=List[schemas.ReturnOut])
def list_returns(order_number: str, current_user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    order = _my_order(db, current_user, order_number)
    return db.query(models.ReturnRequest).filter(
        models.ReturnRequest.order_id == order.id
    ).order_by(models.ReturnRequest.id.desc()).all()
