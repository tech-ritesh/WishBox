"""Wallet: loyalty earn, redemption, gift cards and referral credit.

The wallet is a simple append-only ledger (WalletTransaction); the balance is
SUM(amount). Used for loyalty cashback, store credit, gift-card redemption and
referral rewards — all in rupees.
"""
from __future__ import annotations

import secrets
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.services.common import money

EARN_RATE = Decimal("0.02")          # 2% of order total back as wallet credit
REFERRAL_REWARD = Decimal("100")     # credit to both parties when a referee's account is claimed
GIFT_CARD_MIN = Decimal("100")


def balance(db: Session, user_id: int) -> Decimal:
    total = db.query(func.coalesce(func.sum(models.WalletTransaction.amount), 0)).filter(
        models.WalletTransaction.user_id == user_id
    ).scalar()
    return money(total)


def credit(db: Session, user_id: int, amount: Decimal, reason: str, reference: str = None) -> None:
    if money(amount) <= 0:
        return
    db.add(models.WalletTransaction(user_id=user_id, amount=money(amount), reason=reason, reference=reference))


def debit(db: Session, user_id: int, amount: Decimal, reason: str, reference: str = None) -> None:
    amount = money(amount)
    if amount <= 0:
        return
    if balance(db, user_id) < amount:
        raise HTTPException(status_code=400, detail="Insufficient wallet balance")
    db.add(models.WalletTransaction(user_id=user_id, amount=-amount, reason=reason, reference=reference))


def earn_on_order(db: Session, user: models.User, order: models.Order) -> None:
    if user.is_guest:
        return
    reward = money(money(order.total_amount) * EARN_RATE)
    if reward > 0:
        credit(db, user.id, reward, "earn", order.order_number)


# --- Gift cards --------------------------------------------------------------
def buy_gift_card(db: Session, purchaser: models.User, amount: Decimal, recipient_email=None, message=None) -> models.GiftCard:
    amount = money(amount)
    if amount < GIFT_CARD_MIN:
        raise HTTPException(status_code=400, detail=f"Minimum gift card value is ₹{int(GIFT_CARD_MIN)}")
    code = "GC-" + secrets.token_hex(5).upper()
    card = models.GiftCard(
        code=code, initial_amount=amount, balance=amount,
        purchaser_id=purchaser.id, recipient_email=recipient_email, message=message,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def redeem_gift_card(db: Session, user: models.User, code: str) -> Decimal:
    card = db.query(models.GiftCard).filter(models.GiftCard.code == code.strip().upper()).first()
    if not card or not card.is_active:
        raise HTTPException(status_code=404, detail="Invalid gift card code")
    if money(card.balance) <= 0:
        raise HTTPException(status_code=400, detail="Gift card has no balance left")
    amount = money(card.balance)
    card.balance = Decimal("0.00")
    card.is_active = False
    credit(db, user.id, amount, "giftcard", card.code)
    db.commit()
    return amount


# --- Referral ----------------------------------------------------------------
def ensure_referral_code(db: Session, user: models.User) -> str:
    if not user.referral_code:
        user.referral_code = "WB" + secrets.token_hex(3).upper()
        db.commit()
    return user.referral_code


def apply_referral(db: Session, new_user: models.User, code: str) -> None:
    """Credit both the referrer and the new user. Called when an account is created/claimed."""
    if not code:
        return
    referrer = db.query(models.User).filter(models.User.referral_code == code.strip().upper()).first()
    if not referrer or referrer.id == new_user.id or new_user.referred_by_id:
        return
    new_user.referred_by_id = referrer.id
    credit(db, referrer.id, REFERRAL_REWARD, "referral", f"referred:{new_user.email}")
    credit(db, new_user.id, REFERRAL_REWARD, "referral", f"by:{referrer.referral_code}")
    db.commit()
