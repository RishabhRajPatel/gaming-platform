"""Wallet service — all money mutations go through here.

Invariants:
* All amounts are **integer paise** (or integer chips for virtual). Never floats.
* Every mutation writes an append-only `WalletTransaction` with an idempotency key.
* Balances can never go negative for a debit (raises ValueError).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.wallet import TxnType, Wallet, WalletKind, WalletTransaction


class InsufficientFunds(Exception):
    pass


def get_or_create_wallet(db: Session, user_id: str) -> Wallet:
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).one_or_none()
    if wallet is None:
        wallet = Wallet(user_id=user_id)
        db.add(wallet)
        db.flush()
    return wallet


def _balance_field(kind: WalletKind) -> str:
    return {
        WalletKind.REAL: "real_paise",
        WalletKind.BONUS: "bonus_paise",
        WalletKind.VIRTUAL: "virtual_chips",
    }[kind]


def _existing(db: Session, idempotency_key: str) -> WalletTransaction | None:
    return (
        db.query(WalletTransaction)
        .filter(WalletTransaction.idempotency_key == idempotency_key)
        .one_or_none()
    )


def apply_transaction(
    db: Session,
    *,
    user_id: str,
    txn_type: TxnType,
    amount_paise: int,
    idempotency_key: str,
    kind: WalletKind = WalletKind.REAL,
    reference: str = "",
) -> WalletTransaction:
    """Apply a signed amount (credit >0, debit <0) atomically with a ledger entry.

    Idempotent on `idempotency_key`: a repeat call returns the original entry.
    """
    prior = _existing(db, idempotency_key)
    if prior is not None:
        return prior

    wallet = get_or_create_wallet(db, user_id)
    field = _balance_field(kind)
    current = getattr(wallet, field)
    new_balance = current + amount_paise
    if new_balance < 0:
        raise InsufficientFunds(
            f"insufficient {kind.value} balance: have {current}, need {-amount_paise}"
        )
    setattr(wallet, field, new_balance)

    txn = WalletTransaction(
        wallet_id=wallet.id,
        txn_type=txn_type,
        kind=kind,
        amount_paise=amount_paise,
        balance_after=new_balance,
        reference=reference,
        idempotency_key=idempotency_key,
    )
    db.add(txn)
    db.flush()
    return txn


def credit(db: Session, *, user_id: str, amount_paise: int, txn_type: TxnType,
           idempotency_key: str, kind: WalletKind = WalletKind.REAL, reference: str = "") -> WalletTransaction:
    if amount_paise <= 0:
        raise ValueError("credit amount must be positive")
    return apply_transaction(db, user_id=user_id, txn_type=txn_type, amount_paise=amount_paise,
                             idempotency_key=idempotency_key, kind=kind, reference=reference)


def debit(db: Session, *, user_id: str, amount_paise: int, txn_type: TxnType,
          idempotency_key: str, kind: WalletKind = WalletKind.REAL, reference: str = "") -> WalletTransaction:
    if amount_paise <= 0:
        raise ValueError("debit amount must be positive")
    return apply_transaction(db, user_id=user_id, txn_type=txn_type, amount_paise=-amount_paise,
                             idempotency_key=idempotency_key, kind=kind, reference=reference)
