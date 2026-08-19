"""Razorpay deposit + webhook endpoints."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import require_real_money_ready
from app.db.session import get_db
from app.models.payment import Deposit, PaymentStatus
from app.models.user import User
from app.models.wallet import TxnType, WalletKind
from app.schemas.wallet import DepositCreate, DepositOrderOut
from app.services import razorpay_service
from app.services.wallet import credit

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/deposit", response_model=DepositOrderOut)
def create_deposit(
    payload: DepositCreate,
    user: User = Depends(require_real_money_ready),
    db: Session = Depends(get_db),
) -> DepositOrderOut:
    deposit = Deposit(user_id=user.id, amount_paise=payload.amount_paise)
    db.add(deposit)
    db.flush()
    try:
        order = razorpay_service.create_order(
            amount_paise=payload.amount_paise, receipt=f"dep_{deposit.id}"
        )
    except razorpay_service.RazorpayError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    deposit.razorpay_order_id = order["id"]
    db.commit()
    return DepositOrderOut(
        deposit_id=deposit.id,
        razorpay_order_id=order["id"],
        razorpay_key_id=settings.razorpay_key_id,
        amount_paise=payload.amount_paise,
    )


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(default=""),
    db: Session = Depends(get_db),
) -> dict:
    """Razorpay calls this on payment events. We credit the wallet only here — never
    trusting the browser callback alone — and only after verifying the signature."""
    body = await request.body()
    if not razorpay_service.verify_webhook_signature(body, x_razorpay_signature):
        raise HTTPException(status_code=400, detail="invalid webhook signature")

    event = json.loads(body.decode())
    if event.get("event") != "payment.captured":
        return {"status": "ignored"}

    entity = event["payload"]["payment"]["entity"]
    order_id = entity["order_id"]
    payment_id = entity["id"]
    amount_paise = int(entity["amount"])

    deposit = (
        db.query(Deposit).filter(Deposit.razorpay_order_id == order_id).one_or_none()
    )
    if deposit is None:
        raise HTTPException(status_code=404, detail="unknown order")
    if deposit.status == PaymentStatus.PAID:
        return {"status": "already_processed"}

    deposit.status = PaymentStatus.PAID
    deposit.razorpay_payment_id = payment_id
    # idempotency key ties the credit to the unique payment id
    credit(
        db,
        user_id=deposit.user_id,
        amount_paise=amount_paise,
        txn_type=TxnType.DEPOSIT,
        idempotency_key=f"rzp_{payment_id}",
        kind=WalletKind.REAL,
        reference=order_id,
    )
    db.commit()
    return {"status": "ok"}
