"""Real-time Teen Patti WebSocket table.

Client -> server (JSON):
    {"action": "see", "action_id": "<uuid>"}
    {"action": "bet", "raise": bool, "action_id": "<uuid>"}
    {"action": "pack", "action_id": "<uuid>"}
    {"action": "side_show", "action_id": "<uuid>"}
    {"action": "side_show_respond", "accept": bool, "action_id": "<uuid>"}
    {"action": "show", "action_id": "<uuid>"}
    {"action": "sync"}

`action_id` de-duplicates retries/double-clicks per table, same idempotency pattern as
`websocket/game_ws.py`.

Server -> client (JSON):
    {"type": "state", "state": {...}}     # public table state (broadcast)
    {"type": "hand", "cards": [...]}      # private hand (unicast)
    {"type": "event", "event": "...", ...}
    {"type": "error", "message": "..."}

The server is authoritative: clients send intents only, never results. Empty seats
fill with bots after a short wait so a table never just stalls; bots decide via
`bot_strategy`, seeded per-table so a table's bot behaviour is reproducible for replay.
"""
from __future__ import annotations

import asyncio
import json
import random
from collections import OrderedDict, defaultdict
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.game_engine.errors import GameError
from app.models.user import User
from app.models.wallet import TxnType, WalletKind
from app.services.wallet import InsufficientFunds, credit, debit
from app.teen_patti.bot_strategy import Action, decide_action, decide_see
from app.teen_patti.cards import new_server_seed, server_seed_hash
from app.teen_patti.engine import GameConfig, Phase, TeenPattiHand
from app.teen_patti.hand_rank import category_of
from app.teen_patti.manager import teen_patti_manager
from app.teen_patti.models import TeenPattiHandHistory, TeenPattiTable
from app.websocket.manager import manager

router = APIRouter()

_BOT_ID_PREFIX = "bot-"
_BOT_JOIN_DELAY_SECONDS = 20
_START_COUNTDOWN_SECONDS = 3
_NEXT_HAND_DELAY_SECONDS = 6
_BOT_NAMES = ["Ravi", "Priya", "Sam", "Meera"]

_turn_timers: dict[str, asyncio.Task] = {}
_start_timers: dict[str, asyncio.Task] = {}
_bot_join_timers: dict[str, asyncio.Task] = {}
_bot_turn_pending: set[str] = set()
_pending_side_show: dict[str, dict] = {}
_hand_number: dict[str, int] = defaultdict(int)
_table_rng: dict[str, random.Random] = {}
# Users who connected while a hand was already in progress (add_seat rejects mid-hand
# joins) — seated for real as soon as the table goes back to WAITING for its next deal,
# instead of being stuck watching forever with no retry.
_spectators: dict[str, dict[str, str]] = defaultdict(dict)

_MUTATING_ACTIONS = {"see", "bet", "pack", "side_show", "side_show_respond", "show"}
_processed_action_ids: dict[str, "OrderedDict[str, bool]"] = defaultdict(OrderedDict)
_MAX_TRACKED_ACTIONS_PER_TABLE = 500


def _is_bot(seat_id: str) -> bool:
    return seat_id.startswith(_BOT_ID_PREFIX)


def _rng(table_id: str) -> random.Random:
    r = _table_rng.get(table_id)
    if r is None:
        r = random.Random()
        _table_rng[table_id] = r
    return r


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


def _load_config(table_id: str) -> tuple[GameConfig, str]:
    with SessionLocal() as db:
        table = db.get(TeenPattiTable, table_id)
        if table is None:
            return GameConfig(), "virtual"
        return (
            GameConfig(boot=table.boot_amount, max_players=table.max_players,
                       turn_seconds=table.turn_seconds),
            table.mode.value,
        )


async def _broadcast_state(table_id: str) -> None:
    hand = teen_patti_manager.get(table_id)
    if hand is None:
        return
    await manager.broadcast(table_id, {"type": "state", "state": hand.public_state()})
    for uid in manager.connected_users(table_id):
        try:
            cards = hand.private_hand(uid)
        except Exception:
            cards = []
        await manager.send_to_user(table_id, uid, {"type": "hand", "cards": cards})


def _cancel(store: dict, table_id: str) -> None:
    task = store.pop(table_id, None)
    if task and not task.done():
        task.cancel()


# ---- seating / table lifecycle -------------------------------------------------------

def _seat_and_kick_off(table_id: str, user_id: str, username: str) -> None:
    config, _mode = _load_config(table_id)
    hand = teen_patti_manager.get_or_create(table_id, config)
    if not any(s.id == user_id for s in hand.seats):
        try:
            hand.add_seat(user_id, username, is_bot=False)
            _spectators.get(table_id, {}).pop(user_id, None)
        except GameError:
            # Table's mid-hand right now — queue them, seated for real once the
            # table returns to WAITING for its next deal (see _seat_pending_spectators).
            _spectators[table_id][user_id] = username
    _maybe_schedule_bot_join(table_id)
    _maybe_start_hand(table_id)


def _seat_pending_spectators(table_id: str, hand: TeenPattiHand) -> None:
    pending = _spectators.get(table_id)
    if not pending:
        return
    for uid in list(pending.keys()):
        if len(hand.seats) >= hand.config.max_players:
            break
        name = pending.pop(uid)
        try:
            hand.add_seat(uid, name, is_bot=False)
        except GameError:
            pass


def _maybe_schedule_bot_join(table_id: str) -> None:
    hand = teen_patti_manager.get(table_id)
    if hand is None or hand.phase != Phase.WAITING:
        return
    if len(hand.seats) >= hand.config.min_players:
        return
    if table_id in _bot_join_timers:
        return
    _bot_join_timers[table_id] = asyncio.create_task(_bot_join_after_delay(table_id))


async def _bot_join_after_delay(table_id: str) -> None:
    try:
        await asyncio.sleep(_BOT_JOIN_DELAY_SECONDS)
    except asyncio.CancelledError:
        return
    finally:
        _bot_join_timers.pop(table_id, None)

    hand = teen_patti_manager.get(table_id)
    if hand is None or hand.phase != Phase.WAITING or len(hand.seats) >= hand.config.min_players:
        return
    while len(hand.seats) < hand.config.min_players and len(hand.seats) < hand.config.max_players:
        idx = len(hand.seats)
        try:
            hand.add_seat(f"{_BOT_ID_PREFIX}{table_id}-{idx}", _BOT_NAMES[idx % len(_BOT_NAMES)], is_bot=True)
        except GameError:
            break
    await manager.broadcast(table_id, {"type": "event", "event": "bots_joined"})
    await _broadcast_state(table_id)
    _maybe_start_hand(table_id)


def _maybe_start_hand(table_id: str) -> None:
    hand = teen_patti_manager.get(table_id)
    if hand is None or hand.phase != Phase.WAITING:
        return
    if len(hand.seats) < hand.config.min_players:
        return
    if table_id in _start_timers:
        return
    _start_timers[table_id] = asyncio.create_task(_start_hand_after_delay(table_id))


async def _start_hand_after_delay(table_id: str) -> None:
    try:
        await manager.broadcast(table_id, {"type": "event", "event": "starting",
                                           "seconds": _START_COUNTDOWN_SECONDS})
        await asyncio.sleep(_START_COUNTDOWN_SECONDS)
    except asyncio.CancelledError:
        return
    finally:
        _start_timers.pop(table_id, None)
    await _deal_if_ready(table_id)


async def _start_next_hand_after_delay(table_id: str) -> None:
    try:
        await asyncio.sleep(_NEXT_HAND_DELAY_SECONDS)
    except asyncio.CancelledError:
        return
    finally:
        _start_timers.pop(table_id, None)
    hand = teen_patti_manager.get(table_id)
    if hand is None:
        return
    # A finished hand must go back to WAITING before _deal_if_ready will touch it —
    # do this unconditionally, not just in the "not enough players" branch below,
    # otherwise a table with plenty of seated players just stops after one hand.
    hand.phase = Phase.WAITING
    if len(hand.seats) < hand.config.min_players:
        await _broadcast_state(table_id)
        _maybe_schedule_bot_join(table_id)
        return
    await _deal_if_ready(table_id)


async def _deal_if_ready(table_id: str) -> None:
    hand = teen_patti_manager.get(table_id)
    if hand is None or hand.phase != Phase.WAITING:
        return
    _seat_pending_spectators(table_id, hand)
    if len(hand.seats) < hand.config.min_players:
        return
    _hand_number[table_id] += 1
    hand.deal(new_server_seed(), table_id, _hand_number[table_id])
    await _broadcast_state(table_id)
    await manager.broadcast(table_id, {"type": "event", "event": "hand_started"})
    _arm_turn_timer(table_id)
    _maybe_trigger_bot_turn(table_id)


# ---- turn timer -----------------------------------------------------------------------

def _arm_turn_timer(table_id: str) -> None:
    _cancel(_turn_timers, table_id)
    hand = teen_patti_manager.get(table_id)
    if hand is None or hand.phase != Phase.PLAYING or table_id in _pending_side_show:
        return
    _turn_timers[table_id] = asyncio.create_task(_turn_timeout(table_id, hand.config.turn_seconds))


async def _turn_timeout(table_id: str, seconds: int) -> None:
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        return
    hand = teen_patti_manager.get(table_id)
    if hand is None or hand.phase != Phase.PLAYING:
        return
    current = hand.current_seat().id
    try:
        hand.pack(current)
    except GameError:
        return
    await manager.broadcast(table_id, {"type": "event", "event": "turn_timeout", "seat": current})
    await _after_action(table_id)


# ---- bots -------------------------------------------------------------------------------

def _maybe_trigger_bot_turn(table_id: str) -> None:
    hand = teen_patti_manager.get(table_id)
    if hand is None or hand.phase != Phase.PLAYING or table_id in _pending_side_show:
        return
    if not _is_bot(hand.current_seat().id):
        return
    if table_id in _bot_turn_pending:
        return
    _bot_turn_pending.add(table_id)
    asyncio.create_task(_run_bot_turn(table_id))


async def _run_bot_turn(table_id: str) -> None:
    try:
        await asyncio.sleep(random.uniform(0.8, 1.8))  # a beat, so it doesn't feel robotic
        hand = teen_patti_manager.get(table_id)
        if hand is None or hand.phase != Phase.PLAYING:
            return
        seat = hand.current_seat()
        if not _is_bot(seat.id):
            return
        _cancel(_turn_timers, table_id)
        rng = _rng(table_id)
        try:
            if not seat.seen and decide_see(seat.seen, seat.blind_turns, rng):
                hand.see(seat.id)
            active = hand.active_seats()
            prev_idx = hand.prev_seen_seat_index(hand._seat_index(seat.id)) if seat.seen else None
            decision = decide_action(
                category=category_of(seat.cards), seen=seat.seen, active_count=len(active),
                stake=hand.stake, cap=hand.config.cap, boot=hand.config.boot,
                prev_seen_seat=prev_idx, rng=rng,
            )
            if decision.action == Action.PACK:
                hand.pack(seat.id)
            elif decision.action == Action.SHOW:
                hand.show(seat.id)
            elif decision.action == Action.SIDE_SHOW:
                target = hand.seats[decision.target_seat]
                if _is_bot(target.id):
                    hand.side_show(seat.id, rng=rng)
                else:
                    await _request_side_show(table_id, seat.id, target.id)
                    return  # waits for the human target's response
            elif decision.action == Action.RAISE:
                hand.bet(seat.id, raise_=True)
            else:
                hand.bet(seat.id, raise_=False)
        except GameError:
            return
        await _after_action(table_id)
    finally:
        _bot_turn_pending.discard(table_id)


# ---- side-show request/response --------------------------------------------------------

async def _request_side_show(table_id: str, requester_id: str, target_id: str) -> None:
    _cancel(_turn_timers, table_id)
    _pending_side_show[table_id] = {"requester": requester_id, "target": target_id}
    await manager.send_to_user(table_id, target_id, {
        "type": "event", "event": "side_show_request", "requester": requester_id,
    })
    await manager.broadcast(table_id, {
        "type": "event", "event": "side_show_pending", "requester": requester_id, "target": target_id,
    })
    hand = teen_patti_manager.get(table_id)
    seconds = hand.config.turn_seconds if hand else 15
    _turn_timers[table_id] = asyncio.create_task(_side_show_timeout(table_id, seconds))


async def _side_show_timeout(table_id: str, seconds: int) -> None:
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        return
    if table_id not in _pending_side_show:
        return
    await _resolve_side_show(table_id, accept=False)  # no response in time = decline


async def _resolve_side_show(table_id: str, accept: bool) -> None:
    pending = _pending_side_show.pop(table_id, None)
    if pending is None:
        return
    hand = teen_patti_manager.get(table_id)
    if hand is None:
        return
    try:
        result = hand.side_show(pending["requester"], accept=accept)
    except GameError:
        return
    await manager.broadcast(table_id, {"type": "event", "event": "side_show_result", **result})
    await _after_action(table_id)


# ---- wallet settlement + history --------------------------------------------------------

async def _settle_hand(table_id: str, hand: TeenPattiHand) -> None:
    if hand.winner_seat is None:
        return
    with SessionLocal() as db:
        table = db.get(TeenPattiTable, table_id)
        if table is None:
            return
        kind = WalletKind.VIRTUAL if table.mode.value == "virtual" else WalletKind.REAL
        hand_key = f"{table_id}:{_hand_number[table_id]}"
        hand_dict_json = json.dumps(hand.as_dict())
        s_seed_hash = server_seed_hash(hand.server_seed) if hand.server_seed else ""

        for i, s in enumerate(hand.seats):
            if _is_bot(s.id):
                continue
            won_this = i == hand.winner_seat
            try:
                debit(db, user_id=s.id, amount_paise=table.boot_amount, txn_type=TxnType.GAME_STAKE,
                      idempotency_key=f"tp_stake_{hand_key}_{s.id}", kind=kind, reference=table_id)
            except InsufficientFunds:
                pass  # dev-scope: settlement isn't blocked by a player who can't cover the boot
            payout = 0
            if won_this:
                payout = hand.pot - table.boot_amount
                credit(db, user_id=s.id, amount_paise=hand.pot, txn_type=TxnType.GAME_PAYOUT,
                       idempotency_key=f"tp_payout_{hand_key}", kind=kind, reference=table_id)
            db.add(TeenPattiHandHistory(
                user_id=s.id, table_id=table_id, mode=table.mode.value, boot=table.boot_amount,
                pot=hand.pot, winner_seat=hand.winner_seat, won=won_this, payout=payout,
                hand_json=hand_dict_json, client_seed=hand.client_seed or "",
                nonce=hand.nonce or 0, server_seed=hand.server_seed or "", server_seed_hash=s_seed_hash,
            ))
        db.commit()


# ---- shared post-action pipeline ---------------------------------------------------------

async def _after_action(table_id: str) -> None:
    hand = teen_patti_manager.get(table_id)
    if hand is None:
        return
    await _broadcast_state(table_id)
    if hand.phase == Phase.FINISHED:
        _cancel(_turn_timers, table_id)
        await _settle_hand(table_id, hand)
        await manager.broadcast(table_id, {
            "type": "event", "event": "hand_over", "winner_seat": hand.winner_seat, "reason": hand.reason,
        })
        _start_timers[table_id] = asyncio.create_task(_start_next_hand_after_delay(table_id))
    elif hand.phase == Phase.PLAYING and table_id not in _pending_side_show:
        _arm_turn_timer(table_id)
        _maybe_trigger_bot_turn(table_id)


# ---- socket endpoint --------------------------------------------------------------------

@router.websocket("/ws/teen-patti/{table_id}")
async def teen_patti_socket(websocket: WebSocket, table_id: str) -> None:
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

    _seat_and_kick_off(table_id, user_id, username)
    await manager.connect(table_id, user_id, websocket)
    await manager.send_to_user(table_id, user_id, {"type": "event", "event": "joined"})
    await _broadcast_state(table_id)

    try:
        while True:
            msg = await websocket.receive_json()
            await _handle_action(table_id, user_id, msg)
    except WebSocketDisconnect:
        await manager.disconnect(table_id, user_id)
        await manager.broadcast(table_id, {"type": "event", "event": "left", "seat": user_id})
    except Exception as exc:  # pragma: no cover - defensive
        await manager.send_to_user(table_id, user_id, {"type": "error", "message": str(exc)})
        await manager.disconnect(table_id, user_id)


async def _handle_action(table_id: str, user_id: str, msg: dict) -> None:
    hand = teen_patti_manager.get(table_id)
    if hand is None:
        return
    action = msg.get("action")
    action_id = msg.get("action_id")

    if action in _MUTATING_ACTIONS and _already_processed(table_id, action_id):
        await _broadcast_state(table_id)
        return

    try:
        if action == "see":
            hand.see(user_id)
        elif action == "bet":
            hand.bet(user_id, raise_=bool(msg.get("raise", False)))
        elif action == "pack":
            hand.pack(user_id)
        elif action == "show":
            hand.show(user_id)
        elif action == "side_show":
            target_idx = hand.prev_seen_seat_index(hand._seat_index(user_id))
            if target_idx is None:
                await manager.send_to_user(table_id, user_id,
                                           {"type": "error", "message": "no seen seat to compare with"})
                return
            target = hand.seats[target_idx]
            if _is_bot(target.id):
                hand.side_show(user_id, rng=_rng(table_id))
            else:
                _mark_processed(table_id, action_id)
                await _request_side_show(table_id, user_id, target.id)
                return
        elif action == "side_show_respond":
            pending = _pending_side_show.get(table_id)
            if pending is None or pending["target"] != user_id:
                await manager.send_to_user(table_id, user_id,
                                           {"type": "error", "message": "no side-show pending for you"})
                return
            _mark_processed(table_id, action_id)
            await _resolve_side_show(table_id, accept=bool(msg.get("accept")))
            return
        elif action == "sync":
            pass
        else:
            await manager.send_to_user(table_id, user_id, {"type": "error", "message": f"unknown action {action}"})
            return
    except GameError as exc:
        await manager.send_to_user(table_id, user_id, {"type": "error", "message": str(exc)})
        return

    if action in _MUTATING_ACTIONS:
        _mark_processed(table_id, action_id)

    await _after_action(table_id)
