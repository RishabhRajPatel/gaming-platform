"""Andar Bahar real-time table — a shared-outcome betting round, not a turn-based
game. Every connected player bets independently (Andar or Bahar) during one open
betting window; the server deals once and settles everyone against that single
result. No turn order, no opponents, no bots needed — a lone connected player can
bet and the round still resolves normally.

Built on top of the existing pure `engine.py` (unchanged, still used as-is by the
one-shot REST bet endpoint) — this module only adds the stateful "many players share
one round" bookkeeping the WebSocket table needs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from . import engine
from .engine import RoundResult, Side


class Phase(str, Enum):
    WAITING = "waiting"    # no one connected yet
    BETTING = "betting"    # betting window open
    DEALING = "dealing"    # transient: round just closed, about to resolve
    SETTLED = "settled"    # round resolved, wallets settled


@dataclass
class Bet:
    user_id: str
    name: str
    side: Side
    stake: int


@dataclass
class TableConfig:
    betting_seconds: int = 15
    mode: str = "virtual"  # "virtual" | "real"
    max_players: int = 8


class AndarBaharTable:
    def __init__(self, table_id: str, config: Optional[TableConfig] = None):
        self.table_id = table_id
        self.config = config or TableConfig()
        self.participants: Dict[str, str] = {}  # user_id -> name
        self.phase: Phase = Phase.WAITING
        self.round_number: int = 0
        self.bets: Dict[str, Bet] = {}
        self.result: Optional[RoundResult] = None
        self.settlements: Dict[str, dict] = {}
        self.server_seed: Optional[str] = None

    # ---- participants ----------------------------------------------------------------
    def add_participant(self, user_id: str, name: str) -> None:
        self.participants[user_id] = name

    # ---- round lifecycle ---------------------------------------------------------------
    def start_betting(self) -> None:
        self.round_number += 1
        self.bets = {}
        self.result = None
        self.settlements = {}
        self.server_seed = None
        self.phase = Phase.BETTING

    def place_bet(self, user_id: str, side: Side, stake: int) -> Bet:
        if self.phase != Phase.BETTING:
            raise ValueError("betting is closed for this round")
        if user_id in self.bets:
            raise ValueError("already bet this round")
        if stake <= 0:
            raise ValueError("stake must be positive")
        bet = Bet(user_id=user_id, name=self.participants.get(user_id, "?"), side=side, stake=stake)
        self.bets[user_id] = bet
        return bet

    def deal(self, server_seed: str) -> RoundResult:
        self.phase = Phase.DEALING
        self.server_seed = server_seed
        result = engine.play_provably_fair(server_seed, self.table_id, self.round_number)
        self.result = result
        self.settlements = {
            uid: engine.settle(bet.side, bet.stake, result.winner) for uid, bet in self.bets.items()
        }
        self.phase = Phase.SETTLED
        return result

    # ---- serialization -------------------------------------------------------------
    def public_state(self) -> dict:
        return {
            "table_id": self.table_id,
            "phase": self.phase.value,
            "round_number": self.round_number,
            "betting_seconds": self.config.betting_seconds,
            "bets": [
                {"user_id": uid, "name": b.name, "side": b.side, "stake": b.stake}
                for uid, b in self.bets.items()
            ],
            "round": self.result.as_dict() if self.result else None,
            "settlements": self.settlements,
        }
