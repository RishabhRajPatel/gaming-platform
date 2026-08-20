"""Andar Bahar betting endpoint — server-authoritative, wallet-settled."""
from __future__ import annotations

import secrets
import string

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.andar_bahar import engine
from app.andar_bahar.manager import andar_bahar_manager
from app.andar_bahar.models import AndarBaharRound, AndarBaharTable, TableMode, TableStatus
from app.andar_bahar.schemas import BetRequest, BetResponse, TableCreate, TableOut
from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.wallet import TxnType, WalletKind
from app.services.wallet import (
    InsufficientFunds,
    credit,
    debit,
    get_or_create_wallet,
)

router = APIRouter(prefix="/andar-bahar", tags=["andar-bahar"])

WELCOME_CHIPS = 1000  # one-time free virtual chips so new players can try the game


def _balance_for(wallet, mode: str) -> int:
    return wallet.virtual_chips if mode == "virtual" else wallet.real_paise


@router.post("/bet", response_model=BetResponse)
def place_bet(
    body: BetRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BetResponse:
    kind = WalletKind.VIRTUAL if body.mode == "virtual" else WalletKind.REAL

    if body.mode == "real":
        if not settings.real_money_enabled:
            raise HTTPException(status_code=403, detail="real money is disabled")
        if not user.is_18_plus:
            raise HTTPException(status_code=403, detail="18+ verification required")

    wallet = get_or_create_wallet(db, user.id)

    # Idempotency: a repeated (client_seed, nonce) returns the stored round exactly,
    # replayed deterministically from the original server_seed. No re-charge, no new deal.
    existing = (
        db.query(AndarBaharRound)
        .filter(
            AndarBaharRound.user_id == user.id,
            AndarBaharRound.client_seed == body.client_seed,
            AndarBaharRound.nonce == body.nonce,
            AndarBaharRound.table_id.is_(None),
        )
        .one_or_none()
    )
    if existing is not None:
        replay = engine.play_provably_fair(
            existing.server_seed, existing.client_seed, existing.nonce
        )
        stlmt = engine.settle(existing.bet, existing.stake, existing.winner)
        return BetResponse(
            round=replay.as_dict(),
            settlement=stlmt,
            balance=_balance_for(wallet, existing.mode),
            server_seed=existing.server_seed,
            server_seed_hash=existing.server_seed_hash,
        )

    # One-time welcome grant so virtual players always have chips to start.
    if body.mode == "virtual":
        try:
            credit(db, user_id=user.id, amount_paise=WELCOME_CHIPS, txn_type=TxnType.BONUS,
                   idempotency_key=f"ab_welcome_{user.id}", kind=WalletKind.VIRTUAL,
                   reference="welcome")
        except ValueError:
            pass
        db.flush()

    base_key = f"ab_{user.id}_{body.client_seed}_{body.nonce}"

    # Reserve the stake.
    try:
        debit(db, user_id=user.id, amount_paise=body.stake, txn_type=TxnType.GAME_STAKE,
              idempotency_key=f"{base_key}_stake", kind=kind, reference="andar_bahar")
    except InsufficientFunds:
        raise HTTPException(status_code=400, detail="insufficient balance")

    # Run the provably-fair round.
    server_seed = engine.new_server_seed()
    result = engine.play_provably_fair(server_seed, body.client_seed, body.nonce)
    stlmt = engine.settle(body.bet, body.stake, result.winner)

    # Pay out on a win.
    if stlmt["returned"] > 0:
        credit(db, user_id=user.id, amount_paise=stlmt["returned"], txn_type=TxnType.GAME_PAYOUT,
               idempotency_key=f"{base_key}_payout", kind=kind, reference="andar_bahar")

    # Record history.
    db.add(AndarBaharRound(
        user_id=user.id, mode=body.mode, bet=body.bet, stake=body.stake,
        winner=result.winner, payout=stlmt["payout"], won=stlmt["won"],
        cards_dealt=len(result.steps), client_seed=body.client_seed, nonce=body.nonce,
        server_seed=server_seed, server_seed_hash=engine.server_seed_hash(server_seed),
    ))
    db.commit()

    wallet = get_or_create_wallet(db, user.id)
    return BetResponse(
        round=result.as_dict(),
        settlement=stlmt,
        balance=_balance_for(wallet, body.mode),
        server_seed=server_seed,
        server_seed_hash=engine.server_seed_hash(server_seed),
    )


# ---- Real-time table create/list/get (the WebSocket table connects to these ids) --------
# Mirrors teen_patti/router.py's table endpoints exactly, scoped to this module.

_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _generate_join_code(db: Session) -> str:
    for _ in range(10):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))
        if db.query(AndarBaharTable).filter(AndarBaharTable.join_code == code).one_or_none() is None:
            return code
    raise HTTPException(status_code=500, detail="could not allocate a join code, try again")


def _to_out(table: AndarBaharTable) -> TableOut:
    out = TableOut.model_validate(table)
    live = andar_bahar_manager.get(table.id)
    out.online_players = len(live.participants) if live else 0
    return out


@router.get("/tables", response_model=list[TableOut])
def list_tables(db: Session = Depends(get_db)) -> list[TableOut]:
    tables = (
        db.query(AndarBaharTable)
        .filter(AndarBaharTable.status != TableStatus.FINISHED, AndarBaharTable.is_private.is_(False))
        .order_by(AndarBaharTable.created_at.desc())
        .all()
    )
    return [_to_out(t) for t in tables]


@router.post("/tables", response_model=TableOut, status_code=201)
def create_table(
    payload: TableCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TableOut:
    if payload.mode == "real" and not settings.real_money_enabled:
        raise HTTPException(status_code=403, detail="real money is disabled")
    table = AndarBaharTable(
        name=payload.name,
        mode=TableMode(payload.mode),
        max_players=payload.max_players,
        betting_seconds=payload.betting_seconds,
        is_private=payload.is_private,
        join_code=_generate_join_code(db) if payload.is_private else None,
    )
    db.add(table)
    db.commit()
    db.refresh(table)
    return TableOut.model_validate(table)


@router.get("/tables/code/{join_code}", response_model=TableOut)
def get_table_by_code(
    join_code: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TableOut:
    table = (
        db.query(AndarBaharTable)
        .filter(AndarBaharTable.join_code == join_code.upper(), AndarBaharTable.status != TableStatus.FINISHED)
        .one_or_none()
    )
    if table is None:
        raise HTTPException(status_code=404, detail="no table with this code")
    return _to_out(table)


@router.get("/tables/{table_id}", response_model=TableOut)
def get_table(table_id: str, db: Session = Depends(get_db)) -> TableOut:
    table = db.get(AndarBaharTable, table_id)
    if table is None:
        raise HTTPException(status_code=404, detail="table not found")
    return _to_out(table)
