import datetime as dt
import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token, create_refresh_token, decode_token,
    hash_password, verify_password,
)
from app.services import notifications
from app.services import wallet as wallet_service

router = APIRouter(prefix="/auth", tags=["Auth"])

VERIFY_TOKEN_HOURS = 48
RESET_TOKEN_HOURS = 2


def _issue_token(db: Session, user: models.User, kind: str, hours: int) -> models.AuthToken:
    token = secrets.token_urlsafe(32)
    row = models.AuthToken(
        user_id=user.id, token=token, kind=kind,
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours),
    )
    db.add(row)
    return row


def _consume_token(db: Session, token: str, kind: str) -> models.AuthToken:
    row = db.query(models.AuthToken).filter(
        models.AuthToken.token == token, models.AuthToken.kind == kind,
    ).first()
    now = dt.datetime.now(dt.timezone.utc)
    expires = row.expires_at if row is None else (
        row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=dt.timezone.utc)
    )
    if not row or row.used_at is not None or expires < now:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    row.used_at = now
    return row


def _tokens(user: models.User) -> dict:
    return {
        "access_token": create_access_token(user.email, user.role.value),
        "refresh_token": create_refresh_token(user.email, user.role.value),
        "token_type": "bearer",
        "role": user.role.value,
        "full_name": user.full_name,
    }


@router.post("/register", response_model=schemas.TokenPair, status_code=201)
def register(data: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == data.email).first()
    if existing and not existing.is_guest:
        raise HTTPException(status_code=400, detail="Email already registered")
    if existing and existing.is_guest:
        # Claim the guest account: keep its order history, set a real password.
        existing.password_hash = hash_password(data.password)
        existing.full_name = data.full_name
        existing.phone = data.phone or existing.phone
        existing.is_guest = False
        db.commit()
        if data.referral_code:
            wallet_service.apply_referral(db, existing, data.referral_code)
        db.refresh(existing)
        return _tokens(existing)
    # NOTE: unlike the reference, the first user is NOT auto-promoted to admin.
    user = models.User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
        role=models.UserRole.customer,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    if data.referral_code:
        wallet_service.apply_referral(db, user, data.referral_code)
    db.add(models.Notification(
        user_id=user.id, type="promo", title="Welcome to WishBox! 🎁",
        body="Here's 10% off your first order with code WELCOME10.",
    ))
    db.commit()
    return _tokens(user)


@router.post("/login", response_model=schemas.TokenPair)
def login_oauth(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    user.last_login_at = dt.datetime.utcnow()
    db.commit()
    return _tokens(user)


@router.post("/login-json", response_model=schemas.TokenPair)
def login_json(data: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    user.last_login_at = dt.datetime.utcnow()
    db.commit()
    return _tokens(user)


@router.post("/refresh", response_model=schemas.TokenPair)
def refresh(data: schemas.RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(data.refresh_token, expected_type="refresh")
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = db.query(models.User).filter(models.User.email == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return _tokens(user)


@router.get("/profile", response_model=schemas.UserOut)
def get_profile(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.put("/profile", response_model=schemas.UserOut)
def update_profile(data: schemas.UserUpdate, current_user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    if data.full_name is not None:
        current_user.full_name = data.full_name
    if data.phone is not None:
        current_user.phone = data.phone
    if data.password is not None:
        current_user.password_hash = hash_password(data.password)
    db.commit()
    db.refresh(current_user)
    return current_user


# --- Addresses ---
@router.get("/addresses", response_model=List[schemas.AddressOut])
def list_addresses(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Address).filter(models.Address.user_id == current_user.id).all()


@router.post("/addresses", response_model=schemas.AddressOut, status_code=201)
def create_address(data: schemas.AddressCreate, current_user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    count = db.query(models.Address).filter(models.Address.user_id == current_user.id).count()
    if data.is_default or count == 0:
        db.query(models.Address).filter(models.Address.user_id == current_user.id).update(
            {models.Address.is_default: False}
        )
    addr = models.Address(user_id=current_user.id, **data.model_dump())
    if count == 0:
        addr.is_default = True
    db.add(addr)
    db.commit()
    db.refresh(addr)
    return addr


@router.put("/addresses/{address_id}", response_model=schemas.AddressOut)
def update_address(address_id: int, data: schemas.AddressCreate,
                   current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    addr = db.query(models.Address).filter(
        models.Address.id == address_id, models.Address.user_id == current_user.id
    ).first()
    if not addr:
        raise HTTPException(status_code=404, detail="Address not found")
    if data.is_default:
        db.query(models.Address).filter(
            models.Address.user_id == current_user.id, models.Address.id != address_id
        ).update({models.Address.is_default: False})
    for k, v in data.model_dump().items():
        setattr(addr, k, v)
    db.commit()
    db.refresh(addr)
    return addr


@router.delete("/addresses/{address_id}", status_code=204)
def delete_address(address_id: int, current_user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    addr = db.query(models.Address).filter(
        models.Address.id == address_id, models.Address.user_id == current_user.id
    ).first()
    if not addr:
        raise HTTPException(status_code=404, detail="Address not found")
    db.delete(addr)
    db.commit()


# --- Email verification ---
@router.post("/verify-email/request", response_model=schemas.MessageResponse)
def request_email_verification(current_user: models.User = Depends(get_current_user),
                               db: Session = Depends(get_db)):
    if current_user.email_verified:
        return {"detail": "Email already verified"}
    row = _issue_token(db, current_user, "verify_email", VERIFY_TOKEN_HOURS)
    link = f"{settings.APP_BASE_URL}/verify-email?token={row.token}"
    notifications.queue_email(
        db, current_user.email, "Verify your WishBox email",
        f"Hi {current_user.full_name}, confirm your email by opening:\n{link}\n"
        f"This link expires in {VERIFY_TOKEN_HOURS} hours.",
        user_id=current_user.id,
    )
    db.commit()
    return {"detail": "Verification email queued"}


@router.post("/verify-email/confirm", response_model=schemas.MessageResponse)
def confirm_email_verification(data: schemas.TokenConfirm, db: Session = Depends(get_db)):
    row = _consume_token(db, data.token, "verify_email")
    user = db.get(models.User, row.user_id)
    user.email_verified = True
    db.commit()
    return {"detail": "Email verified"}


# --- Password reset ---
@router.post("/forgot-password", response_model=schemas.MessageResponse)
def forgot_password(data: schemas.EmailRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    # Always return the same response (no account enumeration).
    if user and user.is_active:
        row = _issue_token(db, user, "reset_password", RESET_TOKEN_HOURS)
        link = f"{settings.APP_BASE_URL}/reset-password?token={row.token}"
        notifications.queue_email(
            db, user.email, "Reset your WishBox password",
            f"Reset your password by opening:\n{link}\nThis link expires in {RESET_TOKEN_HOURS} hours. "
            f"If you didn't request this, ignore this email.",
            user_id=user.id,
        )
        db.commit()
    return {"detail": "If that email exists, a reset link has been sent."}


@router.post("/reset-password", response_model=schemas.MessageResponse)
def reset_password(data: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    row = _consume_token(db, data.token, "reset_password")
    user = db.get(models.User, row.user_id)
    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"detail": "Password updated. You can now log in."}
