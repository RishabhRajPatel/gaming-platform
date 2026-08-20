"""Teen Patti one-shot hand endpoint — server-authoritative, wallet-settled.

The requesting user's seat is auto-played by the exact same bot policy as the other
three seats (`engine.play_full_hand`) — there is no interactive turn-by-turn channel
over a single REST request; that's what the WebSocket table is for. The user's
downside is capped at their entry stake (`boot`), debited upfront, exactly like
andar_bahar's fixed-stake bet: whatever the auto-played hand does internally (chaal,
raise, side-show, pack) only affects how big the pot is, never what the user owes
beyond their boot. On a win the full pot — their boot back plus winnings — is
credited.
"""
from __future__ import annotations

import json
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.wallet import TxnType, WalletKind
from app.services.wallet import InsufficientFunds, credit, debit, get_or_create_wallet
from app.teen_patti import engine
from app.teen_patti.cards import new_server_seed, server_seed_hash
from app.teen_patti.manager import teen_patti_manager
from app.teen_patti.models import TableMode, TableStatus, TeenPattiHandHistory, TeenPattiTable
from app.teen_patti.schemas import PlayHandRequest, PlayHandResponse, TableCreate, TableOut

router = APIRouter(prefix="/teen-patti", tags=["teen-patti"])

WELCOME_CHIPS = 1000  # one-time free virtual chips so new players can try the game
USER_SEAT_INDEX = 0
_BOT_NAMES = ["Ravi", "Priya", "Sam"]


def _balance_for(wallet, mode: str) -> int:
    return wallet.virtual_chips if mode == "virtual" else wallet.real_paise


def _settle(won: bool, boot: int, pot: int) -> dict:
    payout = pot - boot if won else 0
    return {"won": won, "stake": boot, "payout": payout, "returned": pot if won else 0}


@router.post("/play-hand", response_model=PlayHandResponse)
def play_hand(
    body: PlayHandRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlayHandResponse:
    kind = WalletKind.VIRTUAL if body.mode == "virtual" else WalletKind.REAL

    if body.mode == "real":
        if not settings.real_money_enabled:
            raise HTTPException(status_code=403, detail="real money is disabled")
        if not user.is_18_plus:
            raise HTTPException(status_code=403, detail="18+ verification required")

    wallet = get_or_create_wallet(db, user.id)

    # Idempotency: a repeated (client_seed, nonce) returns the stored hand exactly,
    # replayed deterministically. No re-charge, no new hand.
    existing = (
        db.query(TeenPattiHandHistory)
        .filter(
            TeenPattiHandHistory.user_id == user.id,
            TeenPattiHandHistory.client_seed == body.client_seed,
            TeenPattiHandHistory.nonce == body.nonce,
            TeenPattiHandHistory.table_id.is_(None),
        )
        .one_or_none()
    )
    if existing is not None:
        stlmt = _settle(existing.won, existing.boot, existing.pot)
        return PlayHandResponse(
            hand=json.loads(existing.hand_json),
            settlement=stlmt,
            balance=_balance_for(wallet, existing.mode),
            server_seed=existing.server_seed,
            server_seed_hash=existing.server_seed_hash,
        )

    # One-time welcome grant so virtual players always have chips to start.
    if body.mode == "virtual":
        try:
            credit(db, user_id=user.id, amount_paise=WELCOME_CHIPS, txn_type=TxnType.BONUS,
                   idempotency_key=f"tp_welcome_{user.id}", kind=WalletKind.VIRTUAL,
                   reference="welcome")
        except ValueError:
            pass
        db.flush()

    base_key = f"tp_{user.id}_{body.client_seed}_{body.nonce}"

    # Reserve the entry stake.
    try:
        debit(db, user_id=user.id, amount_paise=body.boot, txn_type=TxnType.GAME_STAKE,
              idempotency_key=f"{base_key}_stake", kind=kind, reference="teen_patti")
    except InsufficientFunds:
        raise HTTPException(status_code=400, detail="insufficient balance")

    # Auto-play the whole hand: the user occupies seat 0, three bots fill the rest.
    server_seed = new_server_seed()
    seats = [(user.id, user.username)] + [(f"bot-{i}", name) for i, name in enumerate(_BOT_NAMES)]
    hand = engine.play_full_hand(
        server_seed, body.client_seed, body.nonce, seats, engine.GameConfig(boot=body.boot),
    )
    won = hand.winner_seat == USER_SEAT_INDEX
    stlmt = _settle(won, body.boot, hand.pot)

    if stlmt["returned"] > 0:
        credit(db, user_id=user.id, amount_paise=stlmt["returned"], txn_type=TxnType.GAME_PAYOUT,
               idempotency_key=f"{base_key}_payout", kind=kind, reference="teen_patti")

    hand_dict = hand.as_dict()
    db.add(TeenPattiHandHistory(
        user_id=user.id, mode=body.mode, boot=body.boot, pot=hand.pot,
        winner_seat=hand.winner_seat, won=won, payout=stlmt["payout"],
        hand_json=json.dumps(hand_dict), client_seed=body.client_seed, nonce=body.nonce,
        server_seed=server_seed, server_seed_hash=server_seed_hash(server_seed),
    ))
    db.commit()

    wallet = get_or_create_wallet(db, user.id)
    return PlayHandResponse(
        hand=hand_dict,
        settlement=stlmt,
        balance=_balance_for(wallet, body.mode),
        server_seed=server_seed,
        server_seed_hash=server_seed_hash(server_seed),
    )


# ---- Real-time table create/list/get (the WebSocket table connects to these ids) --------
# Mirrors routers/tables.py's Deals Rummy table endpoints exactly, scoped to this module.

_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _generate_join_code(db: Session) -> str:
    for _ in range(10):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))
        if db.query(TeenPattiTable).filter(TeenPattiTable.join_code == code).one_or_none() is None:
            return code
    raise HTTPException(status_code=500, detail="could not allocate a join code, try again")


def _to_out(table: TeenPattiTable) -> TableOut:
    out = TableOut.model_validate(table)
    hand = teen_patti_manager.get(table.id)
    out.online_players = len(hand.seats) if hand else 0
    return out


@router.get("/tables", response_model=list[TableOut])
def list_tables(db: Session = Depends(get_db)) -> list[TableOut]:
    tables = (
        db.query(TeenPattiTable)
        .filter(TeenPattiTable.status != TableStatus.FINISHED, TeenPattiTable.is_private.is_(False))
        .order_by(TeenPattiTable.created_at.desc())
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
    table = TeenPattiTable(
        name=payload.name,
        mode=TableMode(payload.mode),
        max_players=payload.max_players,
        boot_amount=payload.boot_amount,
        turn_seconds=payload.turn_seconds,
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
        db.query(TeenPattiTable)
        .filter(TeenPattiTable.join_code == join_code.upper(), TeenPattiTable.status != TableStatus.FINISHED)
        .one_or_none()
    )
    if table is None:
        raise HTTPException(status_code=404, detail="no table with this code")
    return _to_out(table)


@router.get("/tables/{table_id}", response_model=TableOut)
def get_table(table_id: str, db: Session = Depends(get_db)) -> TableOut:
    table = db.get(TeenPattiTable, table_id)
    if table is None:
        raise HTTPException(status_code=404, detail="table not found")
    return _to_out(table)
