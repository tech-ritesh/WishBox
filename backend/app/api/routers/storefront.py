"""Public festivals & homepage collections."""
import datetime as dt
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db

router = APIRouter(tags=["Storefront"])


@router.get("/festivals/active")
def active_festivals(db: Session = Depends(get_db)):
    now = dt.datetime.utcnow()
    return (
        db.query(models.FestivalCampaign)
        .filter(models.FestivalCampaign.active.is_(True),
                models.FestivalCampaign.start_date <= now,
                models.FestivalCampaign.end_date >= now)
        .all()
    )


@router.get("/collections/active")
def active_collections(db: Session = Depends(get_db)):
    return (
        db.query(models.HomepageCollection)
        .filter(models.HomepageCollection.is_active.is_(True))
        .order_by(models.HomepageCollection.display_order)
        .all()
    )


@router.get("/collections/{slug}", response_model=List[schemas.ProductOut])
def collection_products(slug: str, db: Session = Depends(get_db)):
    coll = db.query(models.HomepageCollection).filter(
        models.HomepageCollection.slug == slug, models.HomepageCollection.is_active.is_(True)
    ).first()
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    if not coll.product_ids:
        return []
    return db.query(models.Product).filter(models.Product.id.in_(coll.product_ids)).all()
