from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.database import get_db

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=List[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return (
        db.query(models.Category)
        .filter(models.Category.is_active.is_(True))
        .order_by(models.Category.sort_order, models.Category.name)
        .all()
    )


@router.get("/tree", response_model=List[schemas.CategoryTreeOut])
def category_tree(db: Session = Depends(get_db)):
    """Nested category hierarchy (parent -> children -> leaves), active only."""
    cats = (
        db.query(models.Category)
        .filter(models.Category.is_active.is_(True))
        .order_by(models.Category.sort_order, models.Category.name)
        .all()
    )
    children_map: dict = {}
    for c in cats:
        children_map.setdefault(c.parent_id, []).append(c)

    def build(node) -> schemas.CategoryTreeOut:
        return schemas.CategoryTreeOut(
            id=node.id, name=node.name, slug=node.slug, parent_id=node.parent_id,
            occasion_group=node.occasion_group, mega_menu_group=node.mega_menu_group,
            is_badge_new=node.is_badge_new,
            children=[build(child) for child in children_map.get(node.id, [])],
        )

    return [build(root) for root in children_map.get(None, [])]


@router.get("/{slug}", response_model=schemas.CategoryOut)
def get_category(slug: str, db: Session = Depends(get_db)):
    cat = db.query(models.Category).filter(models.Category.slug == slug).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return cat
