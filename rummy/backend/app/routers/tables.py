from __future__ import annotations

import secrets
import string

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.game import GameTable, TableMode, TableStatus
from app.models.user import User
from app.schemas.game import TableCreate, TableOut
from app.services.game_manager import game_manager

router = APIRouter(prefix="/tables", tags=["tables"])

_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _generate_join_code(db: Session) -> str:
    for _ in range(10):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))
        if db.query(GameTable).filter(GameTable.join_code == code).one_or_none() is None:
            return code
    raise HTTPException(status_code=500, detail="could not allocate a join code, try again")


def _to_out(table: GameTable) -> TableOut:
    out = TableOut.model_validate(table)
    game = game_manager.get(table.id)
    out.online_players = len(game.players) if game else 0
    return out


@router.get("", response_model=list[TableOut])
def list_tables(db: Session = Depends(get_db)) -> list[TableOut]:
    tables = (
        db.query(GameTable)
        .filter(GameTable.status != TableStatus.FINISHED, GameTable.is_private.is_(False))
        .order_by(GameTable.created_at.desc())
        .all()
    )
    return [_to_out(t) for t in tables]


@router.post("", response_model=TableOut, status_code=201)
def create_table(
    payload: TableCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TableOut:
    if payload.mode == "real_money" and payload.entry_fee_paise <= 0:
        raise HTTPException(status_code=400, detail="real-money tables need an entry fee")
    table = GameTable(
        name=payload.name,
        mode=TableMode(payload.mode),
        max_players=payload.max_players,
        num_deals=payload.num_deals,
        entry_fee_paise=payload.entry_fee_paise,
        pool_limit=payload.pool_limit,
        turn_seconds=payload.turn_seconds,
        starting_chips=payload.starting_chips,
        is_private=payload.is_private,
        join_code=_generate_join_code(db) if payload.is_private else None,
    )
    db.add(table)
    db.commit()
    db.refresh(table)
    return TableOut.model_validate(table)


@router.get("/code/{join_code}", response_model=TableOut)
def get_table_by_code(
    join_code: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TableOut:
    table = (
        db.query(GameTable)
        .filter(GameTable.join_code == join_code.upper(), GameTable.status != TableStatus.FINISHED)
        .one_or_none()
    )
    if table is None:
        raise HTTPException(status_code=404, detail="no table with this code")
    return _to_out(table)


@router.get("/{table_id}", response_model=TableOut)
def get_table(table_id: str, db: Session = Depends(get_db)) -> TableOut:
    table = db.get(GameTable, table_id)
    if table is None:
        raise HTTPException(status_code=404, detail="table not found")
    return _to_out(table)
