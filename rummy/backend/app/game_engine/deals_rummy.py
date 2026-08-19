"""Deals Rummy — the game state machine.

Two table variants share this engine, distinguished by `GameConfig.pool_limit`:

* **Deals Rummy** (`pool_limit=None`, the default): played for a **fixed number of
  deals**. Every player starts with an equal number of chips; each deal's winner
  collects chips equal to the sum of all opponents' hand points (zero-sum). After
  `num_deals` deals, the player with the most chips wins.
* **Pool Rummy** (`pool_limit` set, e.g. 101 or 201): deals continue, accumulating
  each player's `total_score`, until only one player remains under the limit — anyone
  who crosses it is eliminated and sits out all further deals. The last player
  standing wins.

This module is pure Python — it holds no DB or network state. The service layer drives
it and persists results.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .cards import Card, Shoe
from .errors import CardNotInHand, GameStateError, InvalidAction, NotYourTurn
from .scoring import (
    FIRST_DROP_POINTS,
    MIDDLE_DROP_POINTS,
    best_hand_score,
    validate_declaration,
)

HAND_SIZE = 13


class Phase(str, Enum):
    WAITING = "waiting"          # not enough players / not started
    DEALING = "dealing"          # transient
    AWAIT_DRAW = "await_draw"    # current player must draw
    AWAIT_DISCARD = "await_discard"  # current player must discard
    DEAL_OVER = "deal_over"      # a deal finished, chips settled
    GAME_OVER = "game_over"      # all deals finished


class PlayerStatus(str, Enum):
    ACTIVE = "active"
    DROPPED = "dropped"
    WON = "won"
    LOST = "lost"


@dataclass
class Player:
    id: str
    name: str
    seat: int
    chips: int
    hand: List[Card] = field(default_factory=list)
    status: PlayerStatus = PlayerStatus.ACTIVE
    deal_points: int = 0
    total_score: int = 0    # Pool Rummy: cumulative points across deals
    eliminated: bool = False  # Pool Rummy: crossed pool_limit, sits out remaining deals

    def remove_card(self, code: str) -> Card:
        for i, c in enumerate(self.hand):
            if c.code == code:
                return self.hand.pop(i)
        raise CardNotInHand(f"card {code} not in hand")

    def find_card(self, code: str) -> Optional[Card]:
        return next((c for c in self.hand if c.code == code), None)


@dataclass
class GameConfig:
    num_deals: int = 2
    pool_limit: Optional[int] = None  # set (e.g. 101/201) for Pool Rummy instead of a fixed deal count
    turn_seconds: int = 30
    starting_chips: int = 160
    min_players: int = 2
    max_players: int = 4
    num_decks: int = 2
    printed_jokers: int = 2
    mode: str = "free"  # "free" | "real_money" — bots only ever fill free/practice tables


class DealsRummyGame:
    def __init__(self, table_id: str, config: Optional[GameConfig] = None):
        self.table_id = table_id
        self.config = config or GameConfig()
        self.players: List[Player] = []
        self.phase: Phase = Phase.WAITING
        self.deal_number: int = 0
        self.turn_index: int = 0
        self.dealer_index: int = 0
        self.shoe: Optional[Shoe] = None
        self.wild_joker: Optional[Card] = None
        self.wild_rank: Optional[int] = None
        self.last_declarer: Optional[str] = None
        self.winner_id: Optional[str] = None

    # ---- seating -------------------------------------------------------------------
    def add_player(self, player_id: str, name: str) -> Player:
        if self.phase not in (Phase.WAITING, Phase.DEAL_OVER):
            raise GameStateError("cannot join mid-deal")
        if any(p.id == player_id for p in self.players):
            raise InvalidAction("player already seated")
        if len(self.players) >= self.config.max_players:
            raise InvalidAction("table full")
        p = Player(id=player_id, name=name, seat=len(self.players),
                   chips=self.config.starting_chips)
        self.players.append(p)
        return p

    def _player(self, player_id: str) -> Player:
        p = next((p for p in self.players if p.id == player_id), None)
        if p is None:
            raise InvalidAction("unknown player")
        return p

    def current_player(self) -> Player:
        return self.players[self.turn_index]

    def _active_players(self) -> List[Player]:
        return [p for p in self.players if p.status == PlayerStatus.ACTIVE]

    def _live_players(self) -> List[Player]:
        """Pool Rummy: players still in the game (not yet eliminated). Outside Pool
        Rummy this is just everyone — nobody is ever eliminated."""
        return [p for p in self.players if not p.eliminated]

    def _next_active_seat(self, from_index: int) -> int:
        """Next seat (after `from_index`) whose player is ACTIVE this deal — used for
        picking the opening turn and rotating the dealer, both of which must land on
        a real (non-eliminated) player."""
        n = len(self.players)
        idx = from_index
        for _ in range(n):
            idx = (idx + 1) % n
            if self.players[idx].status == PlayerStatus.ACTIVE:
                return idx
        return from_index

    # ---- deal lifecycle ------------------------------------------------------------
    def start_deal(self, seed: Optional[int] = None) -> None:
        live = self._live_players()
        if len(live) < self.config.min_players:
            raise GameStateError("not enough players")
        if self.config.pool_limit is None and self.deal_number >= self.config.num_deals:
            raise GameStateError("all deals already played")
        self.deal_number += 1
        self.phase = Phase.DEALING
        self.shoe = Shoe(self.config.num_decks, self.config.printed_jokers, seed=seed)
        for p in self.players:
            p.hand = []
            p.deal_points = 0
            # Eliminated players sit out entirely — never reactivated, never dealt in.
            p.status = PlayerStatus.ACTIVE if not p.eliminated else PlayerStatus.LOST

        # deal 13 cards each, to live players only
        for _ in range(HAND_SIZE):
            for p in live:
                p.hand.append(self.shoe.draw_from_stock())

        # cut the wild joker
        self.wild_joker = self.shoe.draw_from_stock()
        # if the cut card is a printed joker, the wild rank is Ace by convention
        self.wild_rank = 1 if self.wild_joker.printed_joker else self.wild_joker.rank

        # seed the open pile with one card
        self.shoe.add_to_discard(self.shoe.draw_from_stock())

        # first turn: left of the dealer, skipping any eliminated seat
        self.turn_index = self._next_active_seat(self.dealer_index)
        self.phase = Phase.AWAIT_DRAW
        self.last_declarer = None
        self.winner_id = None

    def _advance_turn(self) -> None:
        n = len(self.players)
        for _ in range(n):
            self.turn_index = (self.turn_index + 1) % n
            if self.players[self.turn_index].status == PlayerStatus.ACTIVE:
                self.phase = Phase.AWAIT_DRAW
                return
        # nobody active — deal should already be over
        self.phase = Phase.DEAL_OVER

    def _require_turn(self, player_id: str, expected_phase: Phase) -> Player:
        p = self._player(player_id)
        if self.current_player().id != player_id:
            raise NotYourTurn(f"it is {self.current_player().id}'s turn")
        if self.phase != expected_phase:
            raise InvalidAction(f"expected {expected_phase.value}, phase is {self.phase.value}")
        if p.status != PlayerStatus.ACTIVE:
            raise InvalidAction("player is not active in this deal")
        return p

    # ---- actions -------------------------------------------------------------------
    def draw(self, player_id: str, source: str = "stock") -> Card:
        p = self._require_turn(player_id, Phase.AWAIT_DRAW)
        if source == "discard":
            card = self.shoe.draw_from_discard()
            if card is None:
                raise InvalidAction("discard pile is empty")
        elif source == "stock":
            if self.shoe.stock_count() == 0:
                self.shoe.recycle_discard_into_stock()
            card = self.shoe.draw_from_stock()
            if card is None:
                raise InvalidAction("no cards left to draw")
        else:
            raise InvalidAction("source must be 'stock' or 'discard'")
        p.hand.append(card)
        self.phase = Phase.AWAIT_DISCARD
        return card

    def discard(self, player_id: str, card_code: str) -> Card:
        p = self._require_turn(player_id, Phase.AWAIT_DISCARD)
        if len(p.hand) != HAND_SIZE + 1:
            raise InvalidAction("must draw before discarding")
        card = p.remove_card(card_code)
        self.shoe.add_to_discard(card)
        self._advance_turn()
        return card

    def drop(self, player_id: str) -> int:
        """Player drops out of the current deal. First drop = 20, middle drop = 40."""
        p = self._player(player_id)
        if p.status != PlayerStatus.ACTIVE:
            raise InvalidAction("player already out of this deal")
        if self.phase not in (Phase.AWAIT_DRAW, Phase.AWAIT_DISCARD):
            raise InvalidAction("cannot drop now")
        if self.current_player().id != player_id:
            raise NotYourTurn("can only drop on your turn")
        # first drop = hasn't drawn any card yet this deal (heuristic: still 13 cards
        # and it is the very first action of their turn in AWAIT_DRAW)
        first_drop = self.phase == Phase.AWAIT_DRAW and len(p.hand) == HAND_SIZE
        p.deal_points = FIRST_DROP_POINTS if first_drop else MIDDLE_DROP_POINTS
        p.status = PlayerStatus.DROPPED
        self._maybe_end_by_attrition_or_advance()
        return p.deal_points

    def declare(self, player_id: str, groups_codes: List[List[str]]):
        """Player declares with an explicit grouping (list of lists of card codes).

        On a valid declaration the deal ends immediately and chips are settled.
        On an invalid declaration the player is penalised the full 80 and is out.
        """
        p = self._require_turn(player_id, Phase.AWAIT_DISCARD)
        # Build Card groups from the player's post-draw hand (14 cards). A declaration
        # discards one card to the finish slot; here the 13 declared cards must be the
        # grouping and the 14th is the discard. We accept 13 grouped cards; the extra
        # card is treated as the finishing discard.
        code_to_card = {c.code: c for c in p.hand}
        groups: List[List[Card]] = []
        used = set()
        for grp in groups_codes:
            cards = []
            for code in grp:
                if code not in code_to_card or code in used:
                    raise InvalidAction(f"card {code} not available for declaration")
                used.add(code)
                cards.append(code_to_card[code])
            groups.append(cards)

        result = validate_declaration(groups, self.wild_rank)
        if not result.valid:
            # invalid show: full penalty, player out
            p.deal_points = result.points
            p.status = PlayerStatus.LOST
            self.last_declarer = player_id
            self._maybe_end_by_attrition_or_advance()
            return result

        # valid: discard the leftover card (the finish), settle the deal
        leftover = [c for c in p.hand if c.code not in used]
        if leftover:
            p.remove_card(leftover[0].code)
            self.shoe.add_to_discard(leftover[0])
        p.status = PlayerStatus.WON
        p.deal_points = 0
        self._settle_deal(winner=p)
        return result

    # ---- deal resolution -----------------------------------------------------------
    def _maybe_end_by_attrition_or_advance(self) -> None:
        active = self._active_players()
        if len(active) == 1:
            # last one standing wins the deal
            self._settle_deal(winner=active[0])
        elif len(active) == 0:
            self.phase = Phase.DEAL_OVER
            self._finish_or_next_deal()
        else:
            self._advance_turn()

    def _settle_deal(self, winner: Player) -> None:
        self.winner_id = winner.id
        winner.status = PlayerStatus.WON
        winner.deal_points = 0
        # score every non-winner who hasn't a fixed drop/penalty score
        for p in self.players:
            if p is winner:
                continue
            if p.status == PlayerStatus.ACTIVE:
                p.deal_points = best_hand_score(p.hand, self.wild_rank)
                p.status = PlayerStatus.LOST
            # dropped / invalid-show players keep their fixed penalty points
        pool = sum(p.deal_points for p in self.players if p is not winner)
        winner.chips += pool
        for p in self.players:
            if p is not winner:
                p.chips -= p.deal_points

        if self.config.pool_limit is not None:
            for p in self._live_players():
                p.total_score += p.deal_points
                if p.total_score >= self.config.pool_limit:
                    p.eliminated = True

        self.phase = Phase.DEAL_OVER
        self._finish_or_next_deal()

    def _finish_or_next_deal(self) -> None:
        if self.config.pool_limit is not None:
            live = self._live_players()
            if len(live) <= 1:
                self.phase = Phase.GAME_OVER
                self.winner_id = (
                    live[0].id if live else min(self.players, key=lambda p: p.total_score).id
                )
            else:
                self.dealer_index = self._next_active_seat(self.dealer_index)
        elif self.deal_number >= self.config.num_deals:
            self.phase = Phase.GAME_OVER
            self.winner_id = max(self.players, key=lambda p: p.chips).id
        else:
            # rotate dealer for the next deal
            self.dealer_index = (self.dealer_index + 1) % len(self.players)

    # ---- serialization -------------------------------------------------------------
    def public_state(self) -> dict:
        return {
            "table_id": self.table_id,
            "phase": self.phase.value,
            "deal_number": self.deal_number,
            "num_deals": self.config.num_deals,
            "pool_limit": self.config.pool_limit,
            "turn": self.current_player().id if self.players else None,
            "wild_joker": self.wild_joker.code if self.wild_joker else None,
            "wild_rank": self.wild_rank,
            "top_discard": self.shoe.top_discard().code if self.shoe and self.shoe.top_discard() else None,
            "stock_count": self.shoe.stock_count() if self.shoe else 0,
            "discard_count": len(self.shoe.discard) if self.shoe else 0,
            "winner_id": self.winner_id,
            "players": [
                {
                    "id": p.id,
                    "name": p.name,
                    "seat": p.seat,
                    "chips": p.chips,
                    "status": p.status.value,
                    "deal_points": p.deal_points,
                    "total_score": p.total_score,
                    "eliminated": p.eliminated,
                    "hand_count": len(p.hand),
                }
                for p in self.players
            ],
        }

    def private_hand(self, player_id: str) -> List[str]:
        """The card codes visible only to `player_id`."""
        return [c.code for c in self._player(player_id).hand]
