import datetime as dt
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import (
    create_access_token, create_refresh_token, decode_token,
    hash_password, verify_password,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


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
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
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
