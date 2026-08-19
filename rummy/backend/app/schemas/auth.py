from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

_PHONE_RE = re.compile(r"^[6-9]\d{9}$")


def _normalize_phone(v: str) -> str:
    digits = v.strip()
    if digits.startswith("+91"):
        digits = digits[3:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if not _PHONE_RE.fullmatch(digits):
        raise ValueError("enter a valid 10-digit Indian mobile number")
    return digits


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=8, max_length=128)
    is_18_plus: bool = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class OtpPurposeIn(str, Enum):
    REGISTER = "register"
    RESET_PASSWORD = "reset_password"


class SendOtpRequest(BaseModel):
    phone: str
    purpose: OtpPurposeIn

    _validate_phone = field_validator("phone")(_normalize_phone)


class SendOtpResponse(BaseModel):
    sent: bool
    # Only populated in dev mode, when there's no real SMS provider to deliver it.
    dev_otp: Optional[str] = None


class PhoneRegisterRequest(BaseModel):
    phone: str
    password: str = Field(min_length=8, max_length=128)
    otp: str = Field(min_length=6, max_length=6)
    is_18_plus: bool = False

    _validate_phone = field_validator("phone")(_normalize_phone)


class PhoneLoginRequest(BaseModel):
    phone: str
    password: str

    _validate_phone = field_validator("phone")(_normalize_phone)


class ResetPasswordRequest(BaseModel):
    phone: str
    password: str = Field(min_length=8, max_length=128)
    otp: str = Field(min_length=6, max_length=6)

    _validate_phone = field_validator("phone")(_normalize_phone)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    username: str
    role: str
    kyc_status: str
    is_18_plus: bool

    model_config = {"from_attributes": True}
