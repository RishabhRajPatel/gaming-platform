from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WalletOut(BaseModel):
    real_paise: int
    bonus_paise: int
    virtual_chips: int

    model_config = {"from_attributes": True}


class TransactionOut(BaseModel):
    id: str
    txn_type: str
    kind: str
    amount_paise: int
    balance_after: int
    reference: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DepositCreate(BaseModel):
    amount_paise: int = Field(gt=0, description="Amount to add, in paise (>=100 => >=₹1)")


class DepositOrderOut(BaseModel):
    deposit_id: str
    razorpay_order_id: str
    razorpay_key_id: str
    amount_paise: int
    currency: str = "INR"


class WithdrawCreate(BaseModel):
    amount_paise: int = Field(gt=0)


class WithdrawalOut(BaseModel):
    id: str
    amount_paise: int
    status: str
    payout_reference: str
    created_at: datetime

    model_config = {"from_attributes": True}
