"""Wallet, gift cards and referral endpoints."""
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import get_current_user
from app.core.database import get_db
from app.services import wallet as wallet_service

router = APIRouter(tags=["Wallet"])


@router.get("/wallet", response_model=schemas.WalletOut)
def get_wallet(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    txns = (
        db.query(models.WalletTransaction)
        .filter(models.WalletTransaction.user_id == current_user.id)
        .order_by(models.WalletTransaction.id.desc())
        .limit(50)
        .all()
    )
    return {"balance": wallet_service.balance(db, current_user.id), "transactions": txns}


@router.get("/wallet/referral", response_model=schemas.ReferralOut)
def my_referral(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    code = wallet_service.ensure_referral_code(db, current_user)
    return {"referral_code": code, "reward": wallet_service.REFERRAL_REWARD}


@router.get("/gift-cards", response_model=List[schemas.GiftCardOut])
def my_gift_cards(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.GiftCard).filter(
        models.GiftCard.purchaser_id == current_user.id
    ).order_by(models.GiftCard.id.desc()).all()


@router.post("/gift-cards", response_model=schemas.GiftCardOut, status_code=201)
def buy_gift_card(data: schemas.GiftCardCreate, current_user: models.User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    return wallet_service.buy_gift_card(db, current_user, data.amount, data.recipient_email, data.message)


@router.post("/gift-cards/redeem", response_model=schemas.WalletOut)
def redeem_gift_card(data: schemas.GiftCardRedeem, current_user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    wallet_service.redeem_gift_card(db, current_user, data.code)
    txns = (
        db.query(models.WalletTransaction)
        .filter(models.WalletTransaction.user_id == current_user.id)
        .order_by(models.WalletTransaction.id.desc()).limit(50).all()
    )
    return {"balance": wallet_service.balance(db, current_user.id), "transactions": txns}
