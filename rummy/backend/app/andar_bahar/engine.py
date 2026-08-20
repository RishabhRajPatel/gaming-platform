"""Andar Bahar engine (pure Python, server-authoritative).

Rules mirror the mobile client:
  - Shuffle one 52-card deck; the top card is the middle/joker card.
  - Black middle card (♠/♣) starts on ANDAR, red (♥/♦) starts on BAHAR.
  - Deal alternately from the start side until a card of the middle's rank appears;
    that side wins.

Fairness: the shuffle seed is derived by HMAC-SHA256(server_seed, "client_seed:nonce").
The server commits to `sha256(server_seed)` and reveals `server_seed` after the round so a
player can reproduce and verify the outcome.
"""
from __future__ import annotations

import hashlib
import hmac
import random
import secrets
from dataclasses import dataclass, field
from typing import List, Literal

Side = Literal["andar", "bahar"]
SUITS = ("S", "H", "D", "C")


def is_red(suit: str) -> bool:
    return suit in ("H", "D")


@dataclass(frozen=True)
class Card:
    rank: int
    suit: str

    def as_dict(self) -> dict:
        return {"rank": self.rank, "suit": self.suit}


def fresh_deck() -> List[Card]:
    return [Card(rank, suit) for suit in SUITS for rank in range(1, 14)]


def start_side(middle: Card) -> Side:
    return "bahar" if is_red(middle.suit) else "andar"


def derive_seed(server_seed: str, client_seed: str, nonce: int) -> int:
    digest = hmac.new(
        server_seed.encode(), f"{client_seed}:{nonce}".encode(), hashlib.sha256
    ).hexdigest()
    return int(digest[:16], 16)


def server_seed_hash(server_seed: str) -> str:
    return hashlib.sha256(server_seed.encode()).hexdigest()


def new_server_seed() -> str:
    return secrets.token_hex(16)


@dataclass
class RoundResult:
    middle: Card
    start_side: Side
    steps: List[dict] = field(default_factory=list)  # [{"side","card"}]
    andar: List[Card] = field(default_factory=list)
    bahar: List[Card] = field(default_factory=list)
    winner: Side = "andar"

    def as_dict(self) -> dict:
        return {
            "middle": self.middle.as_dict(),
            "startSide": self.start_side,
            "steps": [{"side": s["side"], "card": s["card"].as_dict()} for s in self.steps],
            "andar": [c.as_dict() for c in self.andar],
            "bahar": [c.as_dict() for c in self.bahar],
            "winner": self.winner,
            "cardsDealt": len(self.steps),
        }


def play_round(deck: List[Card]) -> RoundResult:
    middle = deck[0]
    rest = deck[1:]
    side: Side = start_side(middle)
    res = RoundResult(middle=middle, start_side=side)
    for card in rest:
        (res.andar if side == "andar" else res.bahar).append(card)
        res.steps.append({"side": side, "card": card})
        if card.rank == middle.rank:
            res.winner = side
            return res
        side = "bahar" if side == "andar" else "andar"
    res.winner = side
    return res


def play_provably_fair(server_seed: str, client_seed: str, nonce: int) -> RoundResult:
    seed = derive_seed(server_seed, client_seed, nonce)
    rng = random.Random(seed)
    deck = fresh_deck()
    rng.shuffle(deck)
    return play_round(deck)


# Payouts (net multiplier on stake for the winning side).
PAYOUT = {"andar": 0.9, "bahar": 1.0}


def settle(bet: Side, stake: int, winner: Side) -> dict:
    won = bet == winner
    payout = round(stake * PAYOUT[bet]) if won else 0
    return {
        "won": won,
        "stake": stake,
        "payout": payout,
        "returned": stake + payout if won else 0,
    }
