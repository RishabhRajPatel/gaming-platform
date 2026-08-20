"""Real-time Andar Bahar WebSocket table.

Unlike Teen Patti's turn-based table, this is a **shared-outcome** table: every
connected player bets independently (Andar or Bahar) during one open betting window;
the server deals once and settles everyone against that single result. There's no
turn order and no bots — a lone connected player can bet and the round still
resolves normally.

Client -> server (JSON):
    {"action": "bet", "side": "andar"|"bahar", "stake": 50, "action_id": "<uuid>"}
    {"action": "sync"}

Server -> client (JSON):
    {"type": "state", "state": {...}}     # public table state (broadcast)
    {"type": "event", "event": "...", ...}
    {"type": "error", "message": "..."}

The server is authoritative: clients send bet intents only, never results.
"""
from __future__ import annotations

import asyncio
from collections import OrderedDict, defaultdict
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.andar_bahar import engine
from app.andar_bahar.manager import andar_bahar_manager
from app.andar_bahar.models import AndarBaharRound, AndarBaharTable
from app.andar_bahar.table import Phase, TableConfig
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.user import User
from app.models.wallet import TxnType, WalletKind
from app.services.wallet import InsufficientFunds, credit, debit, get_or_create_wallet
from app.websocket.manager import manager

router = APIRouter()

_SETTLE_PAUSE_SECONDS = 4  # time the result stays visible before the next betting window opens

_betting_timers: dict[str, asyncio.Task] = {}
_settle_timers: dict[str, asyncio.Task] = {}

_MUTATING_ACTIONS = {"bet"}
_processed_action_ids: dict[str, "OrderedDict[str, bool]"] = defaultdict(OrderedDict)
_MAX_TRACKED_ACTIONS_PER_TABLE = 500


def _already_processed(table_id: str, action_id: Optional[str]) -> bool:
    if not action_id:
        return False
    return action_id in _processed_action_ids[table_id]


def _mark_processed(table_id: str, action_id: Optional[str]) -> None:
    if not action_id:
        return
    bucket = _processed_action_ids[table_id]
    bucket[action_id] = True
    if len(bucket) > _MAX_TRACKED_ACTIONS_PER_TABLE:
        bucket.popitem(last=False)


def _authenticate(token: Optional[str]) -> Optional[tuple[str, str, bool]]:
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
        return user.id, user.username, user.is_18_plus


def _load_config(table_id: str) -> tuple[TableConfig, str]:
    with SessionLocal() as db:
        table = db.get(AndarBaharTable, table_id)
        if table is None:
            return TableConfig(), "virtual"
        return (
            TableConfig(betting_seconds=table.betting_seconds, max_players=table.max_players,
                        mode=table.mode.value),
            table.mode.value,
        )


async def _broadcast_state(table_id: str) -> None:
    live = andar_bahar_manager.get(table_id)
    if live is None:
        return
    await manager.broadcast(table_id, {"type": "state", "state": live.public_state()})


def _can_cover_stake(user_id: str, mode: str, stake: int) -> bool:
    with SessionLocal() as db:
        wallet = get_or_create_wallet(db, user_id)
        db.commit()  # persist a wallet row created by get_or_create_wallet for a brand-new user
        balance = wallet.virtual_chips if mode == "virtual" else wallet.real_paise
        return balance >= stake


def _cancel(store: dict, table_id: str) -> None:
    task = store.pop(table_id, None)
    if task and not task.done():
        task.cancel()


# ---- table lifecycle -------------------------------------------------------------------

def _join_and_kick_off(table_id: str, user_id: str, username: str) -> None:
    config, _mode = _load_config(table_id)
    live = andar_bahar_manager.get_or_create(table_id, config)
    live.add_participant(user_id, username)
    if live.phase == Phase.WAITING:
        _arm_betting_window(table_id)


def _arm_betting_window(table_id: str) -> None:
    live = andar_bahar_manager.get(table_id)
    if live is None or live.phase not in (Phase.WAITING, Phase.SETTLED):
        return
    if table_id in _betting_timers:
        return
    live.start_betting()
    _betting_timers[table_id] = asyncio.create_task(
        _betting_timeout(table_id, live.config.betting_seconds)
    )


async def _betting_timeout(table_id: str, seconds: int) -> None:
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        return
    finally:
        _betting_timers.pop(table_id, None)
    await _resolve_round(table_id)


async def _resolve_round(table_id: str) -> None:
    live = andar_bahar_manager.get(table_id)
    if live is None or live.phase != Phase.BETTING:
        return
    server_seed = engine.new_server_seed()
    live.deal(server_seed)
    await _settle_round(table_id, live)
    await _broadcast_state(table_id)
    await manager.broadcast(table_id, {
        "type": "event", "event": "round_settled",
        "winner": live.result.winner if live.result else None,
    })
    _settle_timers[table_id] = asyncio.create_task(_start_next_round_after_delay(table_id))


async def _settle_round(table_id: str, live) -> None:
    if live.result is None:
        return
    with SessionLocal() as db:
        table = db.get(AndarBaharTable, table_id)
        if table is None:
            return
        kind = WalletKind.VIRTUAL if table.mode.value == "virtual" else WalletKind.REAL
        round_key = f"{table_id}:{live.round_number}"
        for uid, bet in live.bets.items():
            stlmt = live.settlements.get(uid)
            if stlmt is None:
                continue
            try:
                debit(db, user_id=uid, amount_paise=bet.stake, txn_type=TxnType.GAME_STAKE,
                      idempotency_key=f"ab_stake_{round_key}_{uid}", kind=kind, reference=table_id)
            except InsufficientFunds:
                # Balance is checked upfront in _handle_action, so this only fires on a
                # genuine race (e.g. the same wallet drained by another concurrent bet
                # between accept-time and settlement). No debit means no history row for
                # this round either — nothing to reconcile.
                continue
            if stlmt["returned"] > 0:
                credit(db, user_id=uid, amount_paise=stlmt["returned"], txn_type=TxnType.GAME_PAYOUT,
                       idempotency_key=f"ab_payout_{round_key}_{uid}", kind=kind, reference=table_id)
            db.add(AndarBaharRound(
                user_id=uid, table_id=table_id, mode=table.mode.value, bet=bet.side,
                stake=bet.stake, winner=live.result.winner, payout=stlmt["payout"],
                won=stlmt["won"], cards_dealt=len(live.result.steps),
                client_seed=table_id, nonce=live.round_number,
                server_seed=live.server_seed or "",
                server_seed_hash=engine.server_seed_hash(live.server_seed) if live.server_seed else "",
            ))
        db.commit()


async def _start_next_round_after_delay(table_id: str) -> None:
    try:
        await asyncio.sleep(_SETTLE_PAUSE_SECONDS)
    except asyncio.CancelledError:
        return
    finally:
        _settle_timers.pop(table_id, None)
    live = andar_bahar_manager.get(table_id)
    if live is None or not live.participants:
        return
    # Unconditional — a finished round must go back to BETTING regardless of how
    # many participants are still connected, otherwise the table just stops (the
    # exact ordering bug caught in the Teen Patti build: don't gate this on a
    # side condition, always reset phase here).
    _arm_betting_window(table_id)
    await _broadcast_state(table_id)
    await manager.broadcast(table_id, {"type": "event", "event": "betting_open",
                                       "seconds": live.config.betting_seconds})


# ---- socket endpoint --------------------------------------------------------------------

@router.websocket("/ws/andar-bahar/{table_id}")
async def andar_bahar_socket(websocket: WebSocket, table_id: str) -> None:
    token = websocket.query_params.get("token")
    auth = _authenticate(token)
    if auth is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user_id, username, is_18_plus = auth

    _config, mode = _load_config(table_id)
    if mode == "real" and not is_18_plus:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    _join_and_kick_off(table_id, user_id, username)
    await manager.connect(table_id, user_id, websocket)
    await manager.send_to_user(table_id, user_id, {"type": "event", "event": "joined"})
    await _broadcast_state(table_id)

    try:
        while True:
            msg = await websocket.receive_json()
            await _handle_action(table_id, user_id, msg)
    except WebSocketDisconnect:
        await manager.disconnect(table_id, user_id)
        await manager.broadcast(table_id, {"type": "event", "event": "left", "user": user_id})
    except Exception as exc:  # pragma: no cover - defensive
        await manager.send_to_user(table_id, user_id, {"type": "error", "message": str(exc)})
        await manager.disconnect(table_id, user_id)


async def _handle_action(table_id: str, user_id: str, msg: dict) -> None:
    live = andar_bahar_manager.get(table_id)
    if live is None:
        return
    action = msg.get("action")
    action_id = msg.get("action_id")

    if action in _MUTATING_ACTIONS and _already_processed(table_id, action_id):
        await _broadcast_state(table_id)
        return

    if action == "bet":
        side = msg.get("side")
        stake = msg.get("stake")
        if side not in ("andar", "bahar") or not isinstance(stake, int) or stake <= 0:
            await manager.send_to_user(table_id, user_id, {"type": "error", "message": "invalid bet"})
            return
        if not _can_cover_stake(user_id, live.config.mode, stake):
            await manager.send_to_user(table_id, user_id, {"type": "error", "message": "insufficient balance"})
            return
        try:
            live.place_bet(user_id, side, stake)
        except ValueError as exc:
            await manager.send_to_user(table_id, user_id, {"type": "error", "message": str(exc)})
            return
        _mark_processed(table_id, action_id)
        await _broadcast_state(table_id)
    elif action == "sync":
        await _broadcast_state(table_id)
    else:
        await manager.send_to_user(table_id, user_id, {"type": "error", "message": f"unknown action {action}"})
