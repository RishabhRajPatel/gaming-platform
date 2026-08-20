"""Teen Patti — the hand state machine.

Structured like `game_engine/deals_rummy.py`: a `Phase` enum, a `Seat` dataclass, a
`GameConfig` dataclass, and a plain orchestrating class whose action methods are all
guarded by `_require_turn`. This module is pure Python — no DB or network state; the
REST router and the WebSocket table both drive it, persisting results themselves.

One engine, two callers:
* `play_full_hand()` drives *every* seat (including the requesting human's) through
  `bot_strategy` in one synchronous call — used by the one-shot REST endpoint, which
  has no interactive turn-by-turn channel.
* The WebSocket table drives human seats from real client messages and bot/empty
  seats through the same `bot_strategy` functions, calling the exact same `bet`/
  `pack`/`see`/`side_show`/`show` methods directly. No game logic is duplicated.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from app.game_engine.errors import GameStateError, InvalidAction, NotYourTurn

from .bot_strategy import Action, decide_action, decide_see, decide_side_show_accept
from .cards import Card, derive_seed, shuffled_deck
from .hand_rank import category_of, classify_hand, compare_hands


class Phase(str, Enum):
    WAITING = "waiting"    # not enough seats / not dealt yet
    PLAYING = "playing"    # hand in progress
    SHOWDOWN = "showdown"  # transient: exactly two seats called Show
    FINISHED = "finished"  # hand settled


@dataclass
class Seat:
    id: str
    name: str
    is_bot: bool = False
    cards: List[Card] = field(default_factory=list)
    seen: bool = False
    in_round: bool = True
    packed: bool = False
    reveal: bool = False
    blind_turns: int = 0
    bet_label: str = ""
    winner: bool = False


@dataclass
class GameConfig:
    boot: int = 10
    cap_multiplier: int = 128
    min_players: int = 2
    max_players: int = 4
    mode: str = "virtual"  # "virtual" | "real"
    turn_seconds: int = 15  # WS table only; unused by the one-shot auto-play path

    @property
    def cap(self) -> int:
        return self.boot * self.cap_multiplier


class TeenPattiHand:
    def __init__(self, table_id: str, config: Optional[GameConfig] = None):
        self.table_id = table_id
        self.config = config or GameConfig()
        self.seats: List[Seat] = []
        self.phase: Phase = Phase.WAITING
        self.pot: int = 0
        self.stake: int = self.config.boot
        self.cur: int = 0
        self.winner_seat: Optional[int] = None
        self.reason: str = ""
        self.actions: List[dict] = []
        self.server_seed: Optional[str] = None
        self.client_seed: Optional[str] = None
        self.nonce: Optional[int] = None

    # ---- seating ---------------------------------------------------------------------
    def add_seat(self, seat_id: str, name: str, is_bot: bool = False) -> Seat:
        if self.phase != Phase.WAITING:
            raise GameStateError("cannot join mid-hand")
        if any(s.id == seat_id for s in self.seats):
            raise InvalidAction("already seated")
        if len(self.seats) >= self.config.max_players:
            raise InvalidAction("table full")
        seat = Seat(id=seat_id, name=name, is_bot=is_bot)
        self.seats.append(seat)
        return seat

    def _seat(self, seat_id: str) -> Seat:
        s = next((s for s in self.seats if s.id == seat_id), None)
        if s is None:
            raise InvalidAction("unknown seat")
        return s

    def _seat_index(self, seat_id: str) -> int:
        for i, s in enumerate(self.seats):
            if s.id == seat_id:
                return i
        raise InvalidAction("unknown seat")

    def current_seat(self) -> Seat:
        return self.seats[self.cur]

    def active_seats(self) -> List[Seat]:
        return [s for s in self.seats if s.in_round and not s.packed]

    # ---- dealing -----------------------------------------------------------------
    def deal(self, server_seed: str, client_seed: str, nonce: int) -> None:
        if len(self.seats) < self.config.min_players:
            raise GameStateError("not enough players")
        self.server_seed = server_seed
        self.client_seed = client_seed
        self.nonce = nonce
        seed = derive_seed(server_seed, client_seed, nonce)
        deck = shuffled_deck(seed)
        for s in self.seats:
            s.cards = [deck.pop(), deck.pop(), deck.pop()]
            s.seen = False
            s.in_round = True
            s.packed = False
            s.reveal = False
            s.blind_turns = 0
            s.bet_label = ""
            s.winner = False
        self.pot = 0
        self.stake = self.config.boot
        self.phase = Phase.PLAYING
        self.winner_seat = None
        self.reason = ""
        self.actions = []
        for s in self.seats:
            self.pot += self.config.boot
            s.bet_label = f"boot {self.config.boot}"
            self._log(s, "boot", self.config.boot)
        self.cur = 0

    def _log(self, seat: Seat, action: str, amount: int = 0, **extra) -> None:
        entry = {"seat": self._seat_index(seat.id), "action": action, "amount": amount}
        entry.update(extra)
        self.actions.append(entry)

    def _require_turn(self, seat_id: str) -> Seat:
        s = self._seat(seat_id)
        if self.phase != Phase.PLAYING:
            raise InvalidAction(f"hand is not in playing phase (phase={self.phase.value})")
        if self.current_seat().id != seat_id:
            raise NotYourTurn(f"it is {self.current_seat().id}'s turn")
        if not s.in_round or s.packed:
            raise InvalidAction("seat is not active in this hand")
        return s

    def next_seat_index(self, from_index: int) -> int:
        n = len(self.seats)
        for step in range(1, n + 1):
            i = (from_index + step) % n
            s = self.seats[i]
            if s.in_round and not s.packed:
                return i
        return from_index

    def prev_seen_seat_index(self, from_index: int) -> Optional[int]:
        n = len(self.seats)
        for step in range(1, n + 1):
            i = (from_index - step) % n
            s = self.seats[i]
            if s.in_round and not s.packed and s.seen:
                return i
        return None

    # ---- actions -----------------------------------------------------------------
    def see(self, seat_id: str) -> None:
        """Seeing your cards happens as part of taking your turn (matches the
        client: the "See" affordance only ever appears on your own turn), not as a
        free-standing anytime action."""
        s = self._require_turn(seat_id)
        if s.seen:
            raise InvalidAction("already seen")
        s.seen = True
        self._log(s, "see")

    def bet(self, seat_id: str, raise_: bool = False) -> int:
        s = self._require_turn(seat_id)
        if raise_:
            self.stake = min(self.stake * 2, self.config.cap)
        amount = (2 if s.seen else 1) * self.stake
        self.pot += amount
        s.bet_label = f"{'chaal' if s.seen else 'blind'} {amount}"
        if not s.seen:
            s.blind_turns += 1
        self._log(s, "raise" if raise_ else ("chaal" if s.seen else "blind"), amount)
        self._advance()
        return amount

    def pack(self, seat_id: str) -> None:
        s = self._require_turn(seat_id)
        s.packed = True
        s.bet_label = "pack"
        self._log(s, "pack")
        self._advance()

    def side_show(
        self, seat_id: str, accept: Optional[bool] = None, rng: Optional[random.Random] = None,
    ) -> dict:
        """`accept` lets a caller (the WS table, relaying a real opponent's
        accept/reject) drive the outcome directly; `rng` lets a bot opponent decide
        for itself via `bot_strategy.decide_side_show_accept`. Exactly one must be
        given."""
        s = self._require_turn(seat_id)
        prev_idx = self.prev_seen_seat_index(self._seat_index(seat_id))
        if prev_idx is None:
            raise InvalidAction("no previous seen seat to compare with")
        opp = self.seats[prev_idx]
        amount = 2 * self.stake
        self.pot += amount
        self._log(s, "side_show", amount, target=prev_idx)

        if accept is None:
            if rng is None:
                raise InvalidAction("side_show needs an explicit accept or an rng to decide one")
            accept = decide_side_show_accept(category_of(opp.cards), rng)

        result = {"requester": self._seat_index(seat_id), "target": prev_idx, "accepted": accept}
        if accept:
            s.reveal = True
            opp.reveal = True
            requester_wins = compare_hands(s.cards, opp.cards) > 0
            loser = opp if requester_wins else s
            loser.packed = True
            result["winner"] = self._seat_index((s if requester_wins else opp).id)
        self._advance()
        return result

    def show(self, seat_id: str) -> None:
        s = self._require_turn(seat_id)
        active = self.active_seats()
        if len(active) != 2:
            raise InvalidAction("show is only available with exactly two players left")
        amount = 2 * self.stake
        self.pot += amount
        self._log(s, "show", amount)
        self.phase = Phase.SHOWDOWN
        for seat in active:
            seat.reveal = True
        best = active[0]
        for other in active[1:]:
            if compare_hands(other.cards, best.cards) > 0:
                best = other
        self._end(best, "show")

    def _advance(self) -> None:
        active = self.active_seats()
        if len(active) == 1:
            self._end(active[0], "last standing")
            return
        self.cur = self.next_seat_index(self.cur)

    def _end(self, winner: Seat, reason: str) -> None:
        self.phase = Phase.FINISHED
        self.winner_seat = self._seat_index(winner.id)
        self.reason = reason
        winner.winner = True
        winner.reveal = True
        for s in self.active_seats():
            s.reveal = True
        self._log(winner, "win", self.pot)

    # ---- serialization -------------------------------------------------------------
    def public_state(self) -> dict:
        return {
            "table_id": self.table_id,
            "phase": self.phase.value,
            "pot": self.pot,
            "stake": self.stake,
            "turn": self.current_seat().id if self.seats and self.phase == Phase.PLAYING else None,
            "winner_seat": self.winner_seat,
            "reason": self.reason,
            "seats": [
                {
                    "id": s.id,
                    "name": s.name,
                    "is_bot": s.is_bot,
                    "seen": s.seen,
                    "packed": s.packed,
                    "in_round": s.in_round,
                    "bet_label": s.bet_label,
                    "winner": s.winner,
                    "cards": [c.as_dict() for c in s.cards] if s.reveal else None,
                    "card_count": len(s.cards),
                }
                for s in self.seats
            ],
        }

    def private_hand(self, seat_id: str) -> List[dict]:
        return [c.as_dict() for c in self._seat(seat_id).cards]

    def as_dict(self) -> dict:
        """Full hand log for history/audit/replay."""
        return {
            **self.public_state(),
            "actions": self.actions,
            "seats_full": [
                {
                    "id": s.id,
                    "name": s.name,
                    "cards": [c.as_dict() for c in s.cards],
                    "category": classify_hand(s.cards).name,
                }
                for s in self.seats
            ],
        }


# ---- one-shot auto-play (drives every seat, including the human's) ------------------

def play_full_hand(
    server_seed: str,
    client_seed: str,
    nonce: int,
    seat_ids: List[Tuple[str, str]],
    config: Optional[GameConfig] = None,
) -> TeenPattiHand:
    """Auto-play a complete hand for every seat — used by the one-shot REST endpoint,
    which has no interactive turn-by-turn channel to ask the human anything. Every
    decision (see, bet/raise/pack, side-show, show) comes from `bot_strategy`, driven
    by an rng seeded from the same provably-fair seed as the shuffle, so the whole
    hand — cards *and* every decision — is reproducible from
    (server_seed, client_seed, nonce).
    """
    hand = TeenPattiHand(table_id="one-shot", config=config)
    for seat_id, name in seat_ids:
        hand.add_seat(seat_id, name, is_bot=True)
    rng = random.Random(derive_seed(server_seed, client_seed, nonce) ^ 0x5EED)
    hand.deal(server_seed, client_seed, nonce)

    # bot_strategy's raise/pack thresholds only fire for strong hands or a stake that
    # has already climbed — if none of the dealt hands are Color-or-better and nobody
    # rolls a raise, every active seat can just keep calling indefinitely. The browser
    # game never hits this because a human's 15s turn-timeout forces a pack; this
    # auto-played mode has no such external clock, so it forces one itself: if the
    # stake hasn't moved in a full lap-and-a-half around the table, the seat whose
    # turn it is packs instead of calling again. Bounds the loop to a small multiple
    # of the seat count no matter how the cards fall.
    stall_limit = 3 * max(len(hand.seats), 1)
    stall_turns = 0
    last_stake = hand.stake
    guard = 0
    while hand.phase == Phase.PLAYING:
        guard += 1
        if guard > 2000:
            raise GameStateError("hand did not terminate")  # defensive; should be unreachable
        seat = hand.current_seat()
        if not seat.seen and decide_see(seat.seen, seat.blind_turns, rng):
            hand.see(seat.id)

        if stall_turns >= stall_limit:
            hand.pack(seat.id)
        else:
            active = hand.active_seats()
            prev_idx = hand.prev_seen_seat_index(hand._seat_index(seat.id)) if seat.seen else None
            decision = decide_action(
                category=category_of(seat.cards),
                seen=seat.seen,
                active_count=len(active),
                stake=hand.stake,
                cap=hand.config.cap,
                boot=hand.config.boot,
                prev_seen_seat=prev_idx,
                rng=rng,
            )
            if decision.action == Action.PACK:
                hand.pack(seat.id)
            elif decision.action == Action.SHOW:
                hand.show(seat.id)
            elif decision.action == Action.SIDE_SHOW:
                hand.side_show(seat.id, rng=rng)
            elif decision.action == Action.RAISE:
                hand.bet(seat.id, raise_=True)
            else:
                hand.bet(seat.id, raise_=False)

        if hand.stake != last_stake:
            last_stake = hand.stake
            stall_turns = 0
        else:
            stall_turns += 1
    return hand
