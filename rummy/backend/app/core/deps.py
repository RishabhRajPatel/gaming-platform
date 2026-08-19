"""Shared FastAPI dependencies (current user, auth guards)."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    creds_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
    except Exception:
        raise creds_error
    if not user_id:
        raise creds_error
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise creds_error
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user


def require_real_money_ready(user: User = Depends(get_current_user)) -> User:
    """Gate real-money actions behind age + KYC checks."""
    if not settings.real_money_enabled:
        raise HTTPException(status_code=403, detail="Real money is disabled")
    if not user.is_18_plus:
        raise HTTPException(status_code=403, detail="18+ verification required")
    return user
