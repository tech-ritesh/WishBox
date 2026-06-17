"""Smart hamper builder + curated templates."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.api.deps import get_current_user
from app.core.database import get_db

router = APIRouter(prefix="/hampers", tags=["Hampers"])


@router.get("/templates", response_model=List[schemas.HamperOut])
def list_templates(db: Session = Depends(get_db)):
    return (
        db.query(models.Hamper)
        .options(joinedload(models.Hamper.items).joinedload(models.HamperItem.product))
        .filter(models.Hamper.is_template.is_(True))
        .all()
    )


@router.get("", response_model=List[schemas.HamperOut])
def my_hampers(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(models.Hamper)
        .options(joinedload(models.Hamper.items).joinedload(models.HamperItem.product))
        .filter(models.Hamper.user_id == current_user.id)
        .all()
    )


@router.post("", response_model=schemas.HamperOut, status_code=201)
def create_hamper(data: schemas.HamperCreate, current_user: models.User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    hamper = models.Hamper(
        user_id=current_user.id, name=data.name, occasion=data.occasion,
        box_style=data.box_style, gift_message=data.gift_message,
    )
    db.add(hamper)
    db.flush()
    for it in data.items:
        if not db.query(models.Product).get(it.product_id):
            raise HTTPException(status_code=404, detail=f"Product {it.product_id} not found")
        db.add(models.HamperItem(hamper_id=hamper.id, product_id=it.product_id, quantity=it.quantity))
    db.commit()
    db.refresh(hamper)
    return hamper


@router.delete("/{hamper_id}", status_code=204)
def delete_hamper(hamper_id: int, current_user: models.User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    h = db.query(models.Hamper).filter(
        models.Hamper.id == hamper_id, models.Hamper.user_id == current_user.id
    ).first()
    if not h:
        raise HTTPException(status_code=404, detail="Hamper not found")
    db.delete(h)
    db.commit()
