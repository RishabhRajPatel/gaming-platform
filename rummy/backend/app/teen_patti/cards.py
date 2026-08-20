"""Teen Patti deck (pure Python, no DB/network imports).

Own Card/Suit type: Teen Patti has no jokers and ranks Ace high (2..14), unlike
rummy's `game_engine/cards.py` (deadwood-scored rummy cards) or `andar_bahar`'s
(rank 1..13, ace low). Each game module in this codebase defines its own card model
rather than sharing one — same convention `andar_bahar` already follows.
"""
from __future__ import annotations

import hashlib
import hmac
import random
import secrets
from dataclasses import dataclass
from typing import List

SUITS = ("S", "H", "D", "C")


def is_red(suit: str) -> bool:
    return suit in ("H", "D")


@dataclass(frozen=True)
class Card:
    rank: int  # 2..14, Ace = 14 (high)
    suit: str

    def as_dict(self) -> dict:
        return {"rank": self.rank, "suit": self.suit}


def fresh_deck() -> List[Card]:
    return [Card(rank, suit) for suit in SUITS for rank in range(2, 15)]


# ---- provably fair — same HMAC-seed pattern as andar_bahar/engine.py ----------------
# The server commits to sha256(server_seed) up front and reveals server_seed after the
# hand so a player can reproduce and verify both the shuffle and (via bot_strategy's
# seeded rng) every bot decision.

def derive_seed(server_seed: str, client_seed: str, nonce: int) -> int:
    digest = hmac.new(
        server_seed.encode(), f"{client_seed}:{nonce}".encode(), hashlib.sha256
    ).hexdigest()
    return int(digest[:16], 16)


def server_seed_hash(server_seed: str) -> str:
    return hashlib.sha256(server_seed.encode()).hexdigest()


def new_server_seed() -> str:
    return secrets.token_hex(16)


def shuffled_deck(seed: int) -> List[Card]:
    rng = random.Random(seed)
    deck = fresh_deck()
    rng.shuffle(deck)
    return deck
