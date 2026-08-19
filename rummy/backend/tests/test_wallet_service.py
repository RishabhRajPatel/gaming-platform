import pytest

from app.models.wallet import TxnType, WalletKind
from app.services.wallet import InsufficientFunds, credit, debit, get_or_create_wallet


_counter = {"n": 0}


def _user(client):
    from conftest import register_and_login
    import jwt
    from app.core.config import settings
    _counter["n"] += 1
    n = _counter["n"]
    tok = register_and_login(client, f"wal{n}@example.com", f"walletuser{n}")
    return jwt.decode(tok, settings.secret_key, algorithms=["HS256"])["sub"]


def test_credit_debit_and_ledger(client):
    from app.db.session import SessionLocal
    uid = _user(client)
    with SessionLocal() as db:
        credit(db, user_id=uid, amount_paise=10000, txn_type=TxnType.DEPOSIT,
               idempotency_key="k1", kind=WalletKind.REAL)
        db.commit()
        w = get_or_create_wallet(db, uid)
        assert w.real_paise == 10000

        debit(db, user_id=uid, amount_paise=4000, txn_type=TxnType.GAME_STAKE,
              idempotency_key="k2", kind=WalletKind.REAL)
        db.commit()
        assert get_or_create_wallet(db, uid).real_paise == 6000


def test_idempotency_prevents_double_credit(client):
    from app.db.session import SessionLocal
    uid = _user(client)
    with SessionLocal() as db:
        credit(db, user_id=uid, amount_paise=5000, txn_type=TxnType.DEPOSIT,
               idempotency_key="same-key")
        credit(db, user_id=uid, amount_paise=5000, txn_type=TxnType.DEPOSIT,
               idempotency_key="same-key")  # duplicate, ignored
        db.commit()
        # only the first applied
        assert get_or_create_wallet(db, uid).real_paise == 5000


def test_overdraw_raises(client):
    from app.db.session import SessionLocal
    uid = _user(client)
    with SessionLocal() as db:
        with pytest.raises(InsufficientFunds):
            debit(db, user_id=uid, amount_paise=999999, txn_type=TxnType.GAME_STAKE,
                  idempotency_key="over")
