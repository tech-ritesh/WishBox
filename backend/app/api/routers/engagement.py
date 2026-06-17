"""Coupons (validate), reviews, wishlist, reminders, notifications, recommendations."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.api.deps import get_current_user
from app.core.database import get_db
from app.services.coupons import CouponError, evaluate_coupon
from app.services import recommendations as rec

router = APIRouter(tags=["Engagement"])


# --- Coupons ---
@router.post("/coupons/validate", response_model=schemas.CouponValidateResponse)
def validate_coupon(data: schemas.CouponValidateRequest, db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_current_user)):
    try:
        _, discount = evaluate_coupon(db, data.code, data.subtotal, current_user.id)
        return {"valid": True, "discount": discount, "message": f"Coupon applied — you save ₹{discount}"}
    except CouponError as e:
        return {"valid": False, "discount": 0, "message": str(e)}


# --- Reviews ---
@router.get("/reviews/{product_id}", response_model=List[schemas.ReviewOut])
def list_reviews(product_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(models.Review)
        .options(joinedload(models.Review.user))
        .filter(models.Review.product_id == product_id, models.Review.status == "approved")
        .order_by(models.Review.created_at.desc())
        .all()
    )
    out = []
    for r in rows:
        item = schemas.ReviewOut.model_validate(r)
        item.user_name = r.user.full_name if r.user else "Anonymous"
        out.append(item)
    return out


@router.post("/reviews", response_model=schemas.ReviewOut, status_code=201)
def create_review(data: schemas.ReviewCreate, current_user: models.User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    existing = db.query(models.Review).filter(
        models.Review.user_id == current_user.id, models.Review.product_id == data.product_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="You have already reviewed this product")
    # verified purchase check
    purchased = (
        db.query(models.OrderItem).join(models.Order)
        .filter(models.Order.user_id == current_user.id,
                models.OrderItem.product_id == data.product_id)
        .first()
    )
    review = models.Review(
        user_id=current_user.id, product_id=data.product_id, rating=data.rating,
        comment=data.comment, image_url=data.image_url, verified_purchase=bool(purchased),
    )
    db.add(review)
    db.flush()
    # recompute product rating aggregate
    avg, cnt = db.query(func.avg(models.Review.rating), func.count(models.Review.id)).filter(
        models.Review.product_id == data.product_id
    ).one()
    product = db.query(models.Product).get(data.product_id)
    if product:
        product.rating_avg = round(float(avg or 0), 2)
        product.rating_count = int(cnt or 0)
    db.commit()
    db.refresh(review)
    out = schemas.ReviewOut.model_validate(review)
    out.user_name = current_user.full_name
    return out


@router.post("/reviews/{review_id}/helpful")
def vote_helpful(review_id: int, current_user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """Toggle a 'helpful' vote (one per user per review)."""
    review = db.get(models.Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    vote = db.query(models.ReviewVote).filter(
        models.ReviewVote.user_id == current_user.id, models.ReviewVote.review_id == review_id
    ).first()
    if vote:
        db.delete(vote)
        review.helpful_count = max(0, (review.helpful_count or 0) - 1)
        voted = False
    else:
        db.add(models.ReviewVote(user_id=current_user.id, review_id=review_id))
        review.helpful_count = (review.helpful_count or 0) + 1
        voted = True
    db.commit()
    return {"helpful_count": review.helpful_count, "voted": voted}


# --- Product Q&A ---
@router.get("/products/{product_id}/questions", response_model=List[schemas.QuestionOut])
def list_questions(product_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.ProductQuestion)
        .options(joinedload(models.ProductQuestion.answers))
        .filter(models.ProductQuestion.product_id == product_id)
        .order_by(models.ProductQuestion.created_at.desc())
        .all()
    )


@router.post("/products/{product_id}/questions", response_model=schemas.QuestionOut, status_code=201)
def ask_question(product_id: int, data: schemas.QuestionCreate,
                 current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not db.get(models.Product, product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    q = models.ProductQuestion(product_id=product_id, user_id=current_user.id, body=data.body)
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


@router.post("/questions/{question_id}/answers", response_model=schemas.AnswerOut, status_code=201)
def answer_question(question_id: int, data: schemas.AnswerCreate,
                    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.get(models.ProductQuestion, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    is_staff = current_user.role in (models.UserRole.admin, models.UserRole.staff)
    ans = models.ProductAnswer(question_id=question_id, user_id=current_user.id,
                               body=data.body, is_staff_answer=is_staff)
    db.add(ans)
    db.commit()
    db.refresh(ans)
    return ans


# --- Wishlist ---
@router.get("/wishlist", response_model=List[schemas.WishlistItemOut])
def list_wishlist(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(models.WishlistItem)
        .options(joinedload(models.WishlistItem.product))
        .filter(models.WishlistItem.user_id == current_user.id)
        .all()
    )


@router.post("/wishlist/{product_id}", status_code=201)
def add_wishlist(product_id: int, current_user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    if not db.query(models.Product).get(product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    exists = db.query(models.WishlistItem).filter(
        models.WishlistItem.user_id == current_user.id,
        models.WishlistItem.product_id == product_id,
    ).first()
    if not exists:
        db.add(models.WishlistItem(user_id=current_user.id, product_id=product_id))
        db.commit()
    return {"status": "ok"}


@router.delete("/wishlist/{product_id}", status_code=204)
def remove_wishlist(product_id: int, current_user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    db.query(models.WishlistItem).filter(
        models.WishlistItem.user_id == current_user.id,
        models.WishlistItem.product_id == product_id,
    ).delete()
    db.commit()


# --- Reminders ---
@router.get("/reminders", response_model=List[schemas.ReminderOut])
def list_reminders(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Reminder).filter(
        models.Reminder.user_id == current_user.id
    ).order_by(models.Reminder.reminder_date).all()


@router.post("/reminders", response_model=schemas.ReminderOut, status_code=201)
def create_reminder(data: schemas.ReminderCreate, current_user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    r = models.Reminder(user_id=current_user.id, **data.model_dump())
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@router.delete("/reminders/{reminder_id}", status_code=204)
def delete_reminder(reminder_id: int, current_user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    db.query(models.Reminder).filter(
        models.Reminder.id == reminder_id, models.Reminder.user_id == current_user.id
    ).delete()
    db.commit()


# --- Notifications ---
@router.get("/notifications", response_model=List[schemas.NotificationOut])
def list_notifications(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id
    ).order_by(models.Notification.created_at.desc()).limit(50).all()


@router.post("/notifications/{notification_id}/read", status_code=204)
def mark_read(notification_id: int, current_user: models.User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    n = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == current_user.id,
    ).first()
    if n:
        n.is_read = True
        db.commit()


# --- Recommendations / Smart Finder ---
@router.post("/recommendations/smart", response_model=schemas.SmartFinderResponse)
def smart_finder(data: schemas.SmartFinderRequest, db: Session = Depends(get_db)):
    parsed = rec.parse_message(data.message) if data.message else {}
    occasion = data.occasion or parsed.get("occasion")
    relationship = data.relationship or parsed.get("relationship")
    emotion = data.emotion or parsed.get("emotion")
    budget = data.budget or parsed.get("budget")
    products = rec.recommend(db, occasion, relationship, emotion, budget)
    message, tags = rec.build_message(occasion, relationship, emotion, budget, products)
    return {
        "assistant_message": message,
        "insight_tags": tags,
        "products": products,
        "parsed_intent": {"occasion": occasion, "relationship": relationship,
                          "emotion": emotion, "budget": budget},
        "source": "local-engine",
    }


# --- Recently viewed ---
@router.post("/recently-viewed/{product_id}", status_code=204)
def record_recently_viewed(product_id: int, current_user: models.User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    if not db.get(models.Product, product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    row = db.query(models.RecentlyViewed).filter(
        models.RecentlyViewed.user_id == current_user.id,
        models.RecentlyViewed.product_id == product_id,
    ).first()
    if row:
        row.viewed_at = func.now()
    else:
        db.add(models.RecentlyViewed(user_id=current_user.id, product_id=product_id))
    db.commit()


@router.get("/recently-viewed", response_model=List[schemas.RecentlyViewedOut])
def list_recently_viewed(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(models.RecentlyViewed)
        .options(joinedload(models.RecentlyViewed.product))
        .filter(models.RecentlyViewed.user_id == current_user.id)
        .order_by(models.RecentlyViewed.viewed_at.desc())
        .limit(12)
        .all()
    )


# --- Back-in-stock alerts ---
@router.post("/products/{product_id}/notify-me", status_code=204)
def subscribe_back_in_stock(product_id: int, current_user: models.User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    product = db.get(models.Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.stock > 0:
        raise HTTPException(status_code=400, detail="Product is already in stock")
    existing = db.query(models.BackInStockSubscription).filter(
        models.BackInStockSubscription.user_id == current_user.id,
        models.BackInStockSubscription.product_id == product_id,
    ).first()
    if existing:
        existing.notified = False
    else:
        db.add(models.BackInStockSubscription(user_id=current_user.id, product_id=product_id))
    db.commit()


# --- Saved payment methods (no sensitive card data) ---
@router.get("/payment-methods", response_model=List[schemas.SavedPaymentMethodOut])
def list_payment_methods(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.SavedPaymentMethod).filter(
        models.SavedPaymentMethod.user_id == current_user.id
    ).order_by(models.SavedPaymentMethod.is_default.desc(), models.SavedPaymentMethod.id.desc()).all()


@router.post("/payment-methods", response_model=schemas.SavedPaymentMethodOut, status_code=201)
def add_payment_method(data: schemas.SavedPaymentMethodCreate,
                       current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.is_default:
        db.query(models.SavedPaymentMethod).filter(
            models.SavedPaymentMethod.user_id == current_user.id
        ).update({models.SavedPaymentMethod.is_default: False})
    pm = models.SavedPaymentMethod(user_id=current_user.id, **data.model_dump())
    db.add(pm)
    db.commit()
    db.refresh(pm)
    return pm


@router.delete("/payment-methods/{pm_id}", status_code=204)
def delete_payment_method(pm_id: int, current_user: models.User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    pm = db.query(models.SavedPaymentMethod).filter(
        models.SavedPaymentMethod.id == pm_id,
        models.SavedPaymentMethod.user_id == current_user.id,
    ).first()
    if pm:
        db.delete(pm)
        db.commit()
