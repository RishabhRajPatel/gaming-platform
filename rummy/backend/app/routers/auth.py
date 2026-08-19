from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.otp import OtpPurpose
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.auth import (
    LoginRequest,
    OtpPurposeIn,
    PhoneLoginRequest,
    PhoneRegisterRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SendOtpRequest,
    SendOtpResponse,
    TokenResponse,
    UserOut,
)
from app.services import otp_service

router = APIRouter(prefix="/auth", tags=["auth"])

_PURPOSE_MAP = {
    OtpPurposeIn.REGISTER: OtpPurpose.REGISTER,
    OtpPurposeIn.RESET_PASSWORD: OtpPurpose.RESET_PASSWORD,
}


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    exists = (
        db.query(User)
        .filter((User.email == payload.email) | (User.username == payload.username))
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail="email or username already taken")
    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        is_18_plus=payload.is_18_plus,
    )
    db.add(user)
    try:
        db.flush()
        db.add(Wallet(user_id=user.id))  # every user gets a wallet
        db.commit()
    except IntegrityError:
        # Two concurrent registrations for the same email/username both passed the
        # `exists` check above before either committed (classic check-then-insert
        # race — e.g. React StrictMode double-firing a guest-bootstrap effect).
        # The DB's unique constraint is the real guard; report it the same way as
        # the check above instead of leaking a raw 500.
        db.rollback()
        raise HTTPException(status_code=409, detail="email or username already taken")
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email).one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
        )
    token = create_access_token(subject=user.id, extra={"role": user.role.value})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


# ---- mobile + OTP (main site) ---------------------------------------------------------

@router.post("/otp/send", response_model=SendOtpResponse)
def send_otp(payload: SendOtpRequest, db: Session = Depends(get_db)) -> SendOtpResponse:
    purpose = _PURPOSE_MAP[payload.purpose]
    existing = db.query(User).filter(User.phone == payload.phone).one_or_none()
    if purpose == OtpPurpose.REGISTER and existing is not None:
        raise HTTPException(status_code=409, detail="phone already registered")
    if purpose == OtpPurpose.RESET_PASSWORD and existing is None:
        raise HTTPException(status_code=404, detail="no account with this phone")

    dev_otp = otp_service.send_otp(db, payload.phone, purpose)
    return SendOtpResponse(sent=True, dev_otp=dev_otp)


@router.post("/register-phone", response_model=UserOut, status_code=201)
def register_phone(payload: PhoneRegisterRequest, db: Session = Depends(get_db)) -> User:
    if db.query(User).filter(User.phone == payload.phone).one_or_none() is not None:
        raise HTTPException(status_code=409, detail="phone already registered")
    if not otp_service.verify_otp(db, payload.phone, OtpPurpose.REGISTER, payload.otp):
        raise HTTPException(status_code=400, detail="invalid or expired OTP")

    user = User(
        phone=payload.phone,
        username=f"user{payload.phone[-6:]}",
        hashed_password=hash_password(payload.password),
        is_18_plus=payload.is_18_plus,
    )
    db.add(user)
    try:
        db.flush()
        db.add(Wallet(user_id=user.id))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="phone already registered")
    db.refresh(user)
    return user


@router.post("/login-phone", response_model=TokenResponse)
def login_phone(payload: PhoneLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.phone == payload.phone).one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
        )
    token = create_access_token(subject=user.id, extra={"role": user.role.value})
    return TokenResponse(access_token=token)


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter(User.phone == payload.phone).one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="no account with this phone")
    if not otp_service.verify_otp(db, payload.phone, OtpPurpose.RESET_PASSWORD, payload.otp):
        raise HTTPException(status_code=400, detail="invalid or expired OTP")
    user.hashed_password = hash_password(payload.password)
    db.commit()
    return {"reset": True}
