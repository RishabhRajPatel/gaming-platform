"""Real-time Deals Rummy WebSocket endpoint and protocol.

Client → server messages (JSON):
    {"action": "join"}
    {"action": "start", "action_id": "<uuid>"}
    {"action": "draw", "source": "stock"|"discard", "action_id": "<uuid>"}
    {"action": "discard", "card": "<code>", "action_id": "<uuid>"}
    {"action": "declare", "groups": [["4S","5S","6S"], ...], "action_id": "<uuid>"}
    {"action": "drop", "action_id": "<uuid>"}
    {"action": "sync"}

`action_id` is optional but recommended for every mutating action: a fresh UUID
generated once per user intent (the frontend does this automatically). If the same
action_id arrives twice for a table — a double-click, a flaky-network retry, a
reconnect resending an in-flight message — the second copy is a no-op (just a fresh
state resync) instead of re-applying the mutation, so a retried "draw" can never
draw two cards.

Server → client messages (JSON):
    {"type": "state", "state": {...}}     # public table state (broadcast)
    {"type": "hand", "cards": [...]}      # private hand (unicast)
    {"type": "event", "event": "...", ...}
    {"type": "error", "message": "..."}

The server is authoritative: clients send intents only, never results. A player only
ever receives their own hand.
"""
from __future__ import annotations

import asyncio
import random
from collections import OrderedDict, defaultdict
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.game_engine import bot_strategy
from app.game_engine.deals_rummy import DealsRummyGame, GameConfig, Phase, Player
from app.game_engine.errors import GameError
from app.models.game import GameTable, TableMode
from app.models.user import User
from app.models.wallet import TxnType, WalletKind
from app.services.game_manager import game_manager
from app.services.wallet import InsufficientFunds, credit, debit, get_or_create_wallet
from app.websocket.manager import manager

router = APIRouter()

# Per-table turn-timeout tasks.
_turn_timers: dict[str, asyncio.Task] = {}

# --- Practice-table bot opponent -----------------------------------------------------
# When a lone player sits at a free/practice table with nobody else joining, a bot
# fills the empty seat after a short wait so practice never just stalls forever. Bot
# ids are namespaced per table (`bot-<table_id>`) — the in-memory game engine doesn't
# care that they aren't real `users` rows, and free tables never touch the wallet, so
# there's nothing in the real-money settlement path that could ever see one.
_BOT_ID_PREFIX = "bot-"
_BOT_JOIN_DELAY_SECONDS = 18
_BOT_NAMES = ["Rummy Bot", "Asha (Bot)", "Rahul (Bot)", "Meera (Bot)", "Vikram (Bot)", "Priya (Bot)"]
_bot_join_timers: dict[str, asyncio.Task] = {}
_bot_turn_pending: set[str] = set()


def _is_bot(player_id: str) -> bool:
    return player_id.startswith(_BOT_ID_PREFIX)


def _maybe_schedule_bot_join(table_id: str) -> None:
    game = game_manager.get(table_id)
    if game is None or game.config.mode != "free":
        return
    if game.phase != Phase.WAITING or len(game.players) != 1:
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

    game = game_manager.get(table_id)
    if game is None or game.phase != Phase.WAITING or len(game.players) != 1:
        return
    lone = game.players[0]
    if lone.id not in manager.connected_users(table_id):
        return  # they left before the bot arrived — no point filling an empty table

    bot_id = f"{_BOT_ID_PREFIX}{table_id}"
    try:
        game.add_player(bot_id, random.choice(_BOT_NAMES))
    except GameError:
        return
    await manager.broadcast(table_id, {"type": "event", "event": "bot_joined", "player": bot_id})
    await _broadcast_state(table_id)


def _maybe_trigger_bot_turn(table_id: str) -> None:
    game = game_manager.get(table_id)
    if game is None or game.phase != Phase.AWAIT_DRAW or not game.players:
        return
    if not _is_bot(game.current_player().id):
        return
    if table_id in _bot_turn_pending:
        return
    _bot_turn_pending.add(table_id)
    asyncio.create_task(_run_bot_turn(table_id))


async def _run_bot_turn(table_id: str) -> None:
    try:
        await asyncio.sleep(random.uniform(1.2, 2.8))  # a beat, so it doesn't feel instant/robotic
        game = game_manager.get(table_id)
        if game is None or game.phase != Phase.AWAIT_DRAW or not game.players:
            return
        player: Player = game.current_player()
        if not _is_bot(player.id):
            return
        bot_id = player.id
        _cancel_timer(table_id)

        try:
            source = bot_strategy.choose_draw_source(player.hand, game.shoe.top_discard(), game.wild_rank)
            game.draw(bot_id, source)

            declare_groups = bot_strategy.try_find_declare(player.hand, game.wild_rank)
            if declare_groups is not None:
                result = game.declare(bot_id, declare_groups)
                await manager.broadcast(table_id, {"type": "event", "event": "declared",
                                                   "player": bot_id, "valid": result.valid,
                                                   "reason": result.reason})
            else:
                discard_code = bot_strategy.choose_discard(player.hand, game.wild_rank)
                game.discard(bot_id, discard_code)
        except GameError:
            return

        await _broadcast_state(table_id)

        if game.phase == Phase.GAME_OVER:
            _cancel_timer(table_id)
            _settle_real_money(table_id, game)
            await manager.broadcast(table_id, {"type": "event", "event": "game_over",
                                               "winner": game.winner_id})
        elif game.phase == Phase.DEAL_OVER:
            _cancel_timer(table_id)
            _settle_real_money(table_id, game)
            await manager.broadcast(table_id, {"type": "event", "event": "deal_over"})
        elif game.phase in (Phase.AWAIT_DRAW, Phase.AWAIT_DISCARD):
            _arm_timer(table_id)
    finally:
        _bot_turn_pending.discard(table_id)
        # Rare (2 bots at one table isn't possible today, but stay defensive): if it's
        # still/again a bot's turn, keep the chain going instead of stalling the table.
        _maybe_trigger_bot_turn(table_id)

# Per-table idempotency tracking: table_id -> {action_id: True}, insertion-ordered so
# we can evict the oldest once a table accumulates too much history. Only successfully
# *applied* mutations are recorded — a failed/rejected action can always be retried.
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


def _load_config(table_id: str) -> GameConfig:
    with SessionLocal() as db:
        table = db.get(GameTable, table_id)
        if table is None:
            return GameConfig()
        return GameConfig(
            num_deals=table.num_deals,
            pool_limit=table.pool_limit,
            turn_seconds=table.turn_seconds,
            starting_chips=table.starting_chips,
            max_players=table.max_players,
            mode=table.mode.value,
        )


async def _broadcast_state(table_id: str) -> None:
    game = game_manager.get(table_id)
    if game is None:
        return
    await manager.broadcast(table_id, {"type": "state", "state": game.public_state()})
    for uid in manager.connected_users(table_id):
        try:
            hand = game.private_hand(uid)
        except Exception:
            hand = []
        await manager.send_to_user(table_id, uid, {"type": "hand", "cards": hand})


def _cancel_timer(table_id: str) -> None:
    task = _turn_timers.pop(table_id, None)
    if task and not task.done():
        task.cancel()


def _arm_timer(table_id: str) -> None:
    _cancel_timer(table_id)
    game = game_manager.get(table_id)
    if game is None or game.phase not in (Phase.AWAIT_DRAW, Phase.AWAIT_DISCARD):
        return
    _turn_timers[table_id] = asyncio.create_task(_turn_timeout(table_id, game.config.turn_seconds))


async def _turn_timeout(table_id: str, seconds: int) -> None:
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        return
    game = game_manager.get(table_id)
    if game is None:
        return
    # auto-play the missed turn: draw from stock then discard the drawn card.
    try:
        current = game.current_player().id
        if game.phase == Phase.AWAIT_DRAW:
            drawn = game.draw(current, "stock")
            game.discard(current, drawn.code)
        elif game.phase == Phase.AWAIT_DISCARD:
            # discard the highest-point deadwood card
            worst = max(game.current_player().hand, key=lambda c: c.deadwood_points(game.wild_rank))
            game.discard(current, worst.code)
    except GameError:
        return
    await manager.broadcast(table_id, {"type": "event", "event": "turn_timeout", "player": current})
    await _broadcast_state(table_id)
    if game.phase in (Phase.AWAIT_DRAW, Phase.AWAIT_DISCARD):
        _arm_timer(table_id)
    _maybe_trigger_bot_turn(table_id)


def _settle_real_money(table_id: str, game: DealsRummyGame) -> None:
    """Turn this deal's points into real wallet movements for real-money tables.

    `entry_fee_paise` doubles as the per-point value (see the "Point Value ₹X" label
    the frontend shows for Points Rummy tables). Idempotent per (table, deal, player)
    key, so this is safe to call repeatedly (e.g. on every subsequent broadcast while
    the table sits in deal_over/game_over) without double-crediting or double-debiting.

    Dev-scope only: there's no upfront stake/escrow, so a loser's debit is capped at
    their current balance rather than allowed to go negative. A production real-money
    system would hold funds at buy-in instead of trusting post-hoc settlement.
    """
    if game.winner_id is None:
        return
    with SessionLocal() as db:
        table = db.get(GameTable, table_id)
        if table is None or table.mode != TableMode.REAL_MONEY:
            return
        point_value = table.entry_fee_paise
        if point_value <= 0:
            return

        deal_key = f"{table_id}:{game.deal_number}"
        total_credit = 0
        for p in game.players:
            if p.id == game.winner_id or p.deal_points <= 0:
                continue
            amount = p.deal_points * point_value
            try:
                debit(db, user_id=p.id, amount_paise=amount, txn_type=TxnType.GAME_STAKE,
                      idempotency_key=f"stake_{deal_key}_{p.id}", kind=WalletKind.REAL,
                      reference=table_id)
                total_credit += amount
            except InsufficientFunds:
                wallet = get_or_create_wallet(db, p.id)
                if wallet.real_paise > 0:
                    debit(db, user_id=p.id, amount_paise=wallet.real_paise, txn_type=TxnType.GAME_STAKE,
                          idempotency_key=f"stake_{deal_key}_{p.id}", kind=WalletKind.REAL,
                          reference=table_id)
                    total_credit += wallet.real_paise

        if total_credit > 0:
            credit(db, user_id=game.winner_id, amount_paise=total_credit, txn_type=TxnType.GAME_PAYOUT,
                   idempotency_key=f"payout_{deal_key}", kind=WalletKind.REAL, reference=table_id)
        db.commit()


@router.websocket("/ws/game/{table_id}")
async def game_socket(websocket: WebSocket, table_id: str) -> None:
    token = websocket.query_params.get("token")
    auth = _authenticate(token)
    if auth is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user_id, username = auth

    game = game_manager.get_or_create(table_id, _load_config(table_id))
    await manager.connect(table_id, user_id, websocket)

    # (re)seat the player
    try:
        if not any(p.id == user_id for p in game.players):
            game.add_player(user_id, username)
    except GameError as exc:
        await manager.send_to_user(table_id, user_id, {"type": "error", "message": str(exc)})

    await manager.send_to_user(table_id, user_id, {"type": "event", "event": "joined"})
    await _broadcast_state(table_id)
    _maybe_schedule_bot_join(table_id)
    _maybe_trigger_bot_turn(table_id)

    try:
        while True:
            msg = await websocket.receive_json()
            await _handle_action(table_id, user_id, msg)
    except WebSocketDisconnect:
        await manager.disconnect(table_id, user_id)
        await manager.broadcast(table_id, {"type": "event", "event": "left", "player": user_id})
    except Exception as exc:  # pragma: no cover - defensive
        await manager.send_to_user(table_id, user_id, {"type": "error", "message": str(exc)})
        await manager.disconnect(table_id, user_id)


_MUTATING_ACTIONS = {"start", "draw", "discard", "drop", "declare"}


async def _handle_action(table_id: str, user_id: str, msg: dict) -> None:
    game = game_manager.get(table_id)
    if game is None:
        return
    action = msg.get("action")
    action_id = msg.get("action_id")

    if action in _MUTATING_ACTIONS and _already_processed(table_id, action_id):
        # Duplicate of an action we already applied (double-click, retry, reconnect
        # resend) — resync state instead of drawing/discarding/declaring a second time.
        await _broadcast_state(table_id)
        return

    try:
        if action == "start":
            game.start_deal()
            await manager.broadcast(table_id, {"type": "event", "event": "deal_started",
                                               "deal": game.deal_number})
        elif action == "draw":
            game.draw(user_id, msg.get("source", "stock"))
        elif action == "discard":
            game.discard(user_id, msg["card"])
        elif action == "drop":
            game.drop(user_id)
        elif action == "declare":
            result = game.declare(user_id, msg.get("groups", []))
            await manager.broadcast(table_id, {"type": "event", "event": "declared",
                                               "player": user_id, "valid": result.valid,
                                               "reason": result.reason})
        elif action == "sync":
            pass
        else:
            await manager.send_to_user(table_id, user_id,
                                       {"type": "error", "message": f"unknown action {action}"})
            return
    except GameError as exc:
        await manager.send_to_user(table_id, user_id, {"type": "error", "message": str(exc)})
        return

    if action in _MUTATING_ACTIONS:
        _mark_processed(table_id, action_id)

    await _broadcast_state(table_id)

    if game.phase == Phase.GAME_OVER:
        _cancel_timer(table_id)
        _settle_real_money(table_id, game)
        await manager.broadcast(table_id, {"type": "event", "event": "game_over",
                                           "winner": game.winner_id})
    elif game.phase == Phase.DEAL_OVER:
        _cancel_timer(table_id)
        _settle_real_money(table_id, game)
        await manager.broadcast(table_id, {"type": "event", "event": "deal_over"})
    elif game.phase in (Phase.AWAIT_DRAW, Phase.AWAIT_DISCARD):
        _arm_timer(table_id)

    _maybe_trigger_bot_turn(table_id)
