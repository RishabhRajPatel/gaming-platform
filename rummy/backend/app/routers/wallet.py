from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_real_money_ready
from app.db.session import get_db
from app.models.payment import Withdrawal
from app.models.user import User
from app.models.wallet import TxnType, WalletKind, WalletTransaction
from app.schemas.wallet import TransactionOut, WalletOut, WithdrawCreate, WithdrawalOut
from app.services.wallet import InsufficientFunds, debit, get_or_create_wallet

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("", response_model=WalletOut)
def my_wallet(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> WalletOut:
    wallet = get_or_create_wallet(db, user.id)
    db.commit()
    return WalletOut.model_validate(wallet)


@router.get("/transactions", response_model=list[TransactionOut])
def my_transactions(
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TransactionOut]:
    wallet = get_or_create_wallet(db, user.id)
    txns = (
        db.query(WalletTransaction)
        .filter(WalletTransaction.wallet_id == wallet.id)
        .order_by(WalletTransaction.created_at.desc())
        .limit(min(limit, 200))
        .all()
    )
    return [TransactionOut.model_validate(t) for t in txns]


@router.post("/withdraw", response_model=WithdrawalOut, status_code=201)
def request_withdrawal(
    payload: WithdrawCreate,
    user: User = Depends(require_real_money_ready),
    db: Session = Depends(get_db),
) -> WithdrawalOut:
    withdrawal = Withdrawal(user_id=user.id, amount_paise=payload.amount_paise)
    db.add(withdrawal)
    db.flush()
    try:
        debit(
            db,
            user_id=user.id,
            amount_paise=payload.amount_paise,
            txn_type=TxnType.WITHDRAWAL,
            idempotency_key=f"wd_{withdrawal.id}",
            kind=WalletKind.REAL,
            reference=withdrawal.id,
        )
    except InsufficientFunds as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    withdrawal.payout_reference = f"pending-{uuid.uuid4().hex[:10]}"
    db.commit()
    db.refresh(withdrawal)
    return WithdrawalOut.model_validate(withdrawal)


@router.get("/withdrawals", response_model=list[WithdrawalOut])
def my_withdrawals(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[WithdrawalOut]:
    withdrawals = (
        db.query(Withdrawal)
        .filter(Withdrawal.user_id == user.id)
        .order_by(Withdrawal.created_at.desc())
        .all()
    )
    return [WithdrawalOut.model_validate(w) for w in withdrawals]
