"""Matchmaking queue: pairs two searching players into a fresh table before either
of them ever sees a game screen.

Client -> server (first message after connecting):
    {"mode": "free"|"real_money", "entry_fee_paise": int, "max_players": int,
     "num_deals": int, "pool_limit": int|null, "turn_seconds": int,
     "starting_chips": int, "name": str}

Client -> server (to cancel a search in progress):
    {"action": "cancel"}

Server -> client:
    {"type": "matched", "table_id": "...", "solo": bool}   # solo=true: no real
                                                            # opponent turned up in
                                                            # time, table is yours alone
                                                            # (free tables auto-fill a
                                                            # bot shortly after you connect)
    {"type": "no_opponent"}   # real-money only: search timed out, nobody to refund —
                               # entry fees are never held before a deal actually starts
    {"type": "cancelled"}
    {"type": "error", "message": "..."}

Two searchers match when (mode, entry_fee_paise, max_players, num_deals, pool_limit)
are identical — same game, same stake, same table size. Whoever arrives second
creates the table and hands both sides its id; from there both clients just open the
normal `/ws/game/{table_id}` socket exactly like a manually-created table.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.game import GameTable, TableMode
from app.models.user import User
from app.schemas.game import TableCreate

router = APIRouter()

_MATCHMAKING_TIMEOUT_SECONDS = 15

_QueueKey = tuple
_queue: dict[_QueueKey, list["asyncio.Future[str]"]] = defaultdict(list)
_queue_lock = asyncio.Lock()


def _authenticate(token: Optional[str]) -> Optional[tuple[str, str]]:
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
    except Exception:
        return None
    if not user_id:
        return None
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            return None
        return user.id, user.username


def _queue_key(cfg: TableCreate) -> _QueueKey:
    return (cfg.mode, cfg.entry_fee_paise, cfg.max_players, cfg.num_deals, cfg.pool_limit)


def _create_table(cfg: TableCreate) -> str:
    with SessionLocal() as db:
        table = GameTable(
            name=cfg.name,
            mode=TableMode(cfg.mode),
            max_players=cfg.max_players,
            num_deals=cfg.num_deals,
            entry_fee_paise=cfg.entry_fee_paise,
            pool_limit=cfg.pool_limit,
            turn_seconds=cfg.turn_seconds,
            starting_chips=cfg.starting_chips,
            is_private=False,
        )
        db.add(table)
        db.commit()
        db.refresh(table)
        return table.id


async def _dequeue(key: _QueueKey, fut: "asyncio.Future[str]") -> None:
    async with _queue_lock:
        bucket = _queue.get(key)
        if bucket and fut in bucket:
            bucket.remove(fut)


@router.websocket("/ws/matchmaking")
async def matchmaking_socket(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    auth = _authenticate(token)
    if auth is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    try:
        criteria = await websocket.receive_json()
    except WebSocketDisconnect:
        return

    try:
        cfg = TableCreate(**{**criteria, "is_private": False})
    except ValidationError as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})
        await websocket.close()
        return

    if cfg.mode == "real_money" and cfg.entry_fee_paise <= 0:
        await websocket.send_json({"type": "error", "message": "real-money tables need an entry fee"})
        await websocket.close()
        return

    key = _queue_key(cfg)
    loop = asyncio.get_event_loop()
    my_future: "asyncio.Future[str]" = loop.create_future()

    matched_table_id: Optional[str] = None
    async with _queue_lock:
        bucket = _queue[key]
        if bucket:
            opponent_future = bucket.pop(0)
            matched_table_id = _create_table(cfg)
            if not opponent_future.done():
                opponent_future.set_result(matched_table_id)
        else:
            bucket.append(my_future)

    if matched_table_id:
        await websocket.send_json({"type": "matched", "table_id": matched_table_id, "solo": False})
        await websocket.close()
        return

    recv_task = asyncio.create_task(websocket.receive_json())
    try:
        done, _pending = await asyncio.wait(
            {my_future, recv_task}, timeout=_MATCHMAKING_TIMEOUT_SECONDS,
            return_when=asyncio.FIRST_COMPLETED,
        )

        if my_future in done:
            recv_task.cancel()
            await websocket.send_json({"type": "matched", "table_id": my_future.result(), "solo": False})
            return

        if recv_task in done:
            await _dequeue(key, my_future)
            recv_task.result()  # raises WebSocketDisconnect if that's what happened
            if my_future.done():
                await websocket.send_json({"type": "matched", "table_id": my_future.result(), "solo": False})
            else:
                await websocket.send_json({"type": "cancelled"})
            return

        # Timed out — no opponent, no cancel.
        recv_task.cancel()
        await _dequeue(key, my_future)
        if my_future.done():
            await websocket.send_json({"type": "matched", "table_id": my_future.result(), "solo": False})
        elif cfg.mode == "free":
            table_id = _create_table(cfg)
            await websocket.send_json({"type": "matched", "table_id": table_id, "solo": True})
        else:
            await websocket.send_json({"type": "no_opponent"})
    except WebSocketDisconnect:
        recv_task.cancel()
        await _dequeue(key, my_future)
        return
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
