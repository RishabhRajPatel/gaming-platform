"""Cards, ranks, suits and the shoe (deck) for 13-card Indian Rummy.

Pure standard library. No framework, DB or network imports may ever be added here.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

# Cryptographically-strong RNG for shuffling (fair-play requirement).
_SECURE_RANDOM = random.SystemRandom()


class Suit(str, Enum):
    SPADES = "S"
    HEARTS = "H"
    DIAMONDS = "D"
    CLUBS = "C"


# Rank values: Ace = 1 (can also act high after King), J=11, Q=12, K=13.
ACE = 1
JACK = 11
QUEEN = 12
KING = 13
MIN_RANK = 1
MAX_RANK = 13

# Deadwood point value of a rank. A, J, Q, K are worth 10; others face value.
_TEN_POINT_RANKS = {ACE, JACK, QUEEN, KING}


def rank_points(rank: int) -> int:
    """Deadwood points for a natural (non-joker) rank."""
    return 10 if rank in _TEN_POINT_RANKS else rank


def rank_label(rank: int) -> str:
    return {1: "A", 11: "J", 12: "Q", 13: "K"}.get(rank, str(rank))


@dataclass(frozen=True)
class Card:
    """A single card.

    `printed_joker` marks the two extra jokers in the shoe (they have no suit/rank
    that matters and are always wild). Regular cards carry a real suit + rank.
    """

    rank: int
    suit: Optional[Suit] = None
    printed_joker: bool = False
    # Disambiguates the two identical copies of a card across the 2-deck shoe.
    deck_index: int = 0

    # ---- identity / serialization -------------------------------------------------
    @property
    def code(self) -> str:
        if self.printed_joker:
            return f"PJ{self.deck_index}"
        return f"{rank_label(self.rank)}{self.suit.value}{self.deck_index}"

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<{self.code}>"

    # ---- joker logic --------------------------------------------------------------
    def is_wild(self, wild_rank: Optional[int]) -> bool:
        """True if this card acts as a joker this deal.

        Printed jokers are always wild. A regular card is wild when its rank equals
        the cut/wild rank for the deal.
        """
        if self.printed_joker:
            return True
        return wild_rank is not None and self.rank == wild_rank

    def deadwood_points(self, wild_rank: Optional[int]) -> int:
        """Points this card contributes if left ungrouped. Jokers are worth 0."""
        if self.is_wild(wild_rank):
            return 0
        return rank_points(self.rank)


def build_shoe(num_decks: int = 2, printed_jokers: int = 2) -> List[Card]:
    """Build the shoe: `num_decks` × 52 standard cards + `printed_jokers` jokers.

    Two decks is the standard shoe for 2–6 player 13-card rummy.
    """
    cards: List[Card] = []
    for d in range(num_decks):
        for suit in Suit:
            for rank in range(MIN_RANK, MAX_RANK + 1):
                cards.append(Card(rank=rank, suit=suit, deck_index=d))
    for j in range(printed_jokers):
        cards.append(Card(rank=0, suit=None, printed_joker=True, deck_index=j))
    return cards


class Shoe:
    """A shuffled shoe with a closed (stock) pile and an open (discard) pile."""

    def __init__(self, num_decks: int = 2, printed_jokers: int = 2, seed: Optional[int] = None):
        self._rng = random.Random(seed) if seed is not None else _SECURE_RANDOM
        self.seed = seed
        self.stock: List[Card] = build_shoe(num_decks, printed_jokers)
        self.discard: List[Card] = []
        self._rng.shuffle(self.stock)

    def draw_from_stock(self) -> Optional[Card]:
        if not self.stock:
            return None
        return self.stock.pop()

    def top_discard(self) -> Optional[Card]:
        return self.discard[-1] if self.discard else None

    def draw_from_discard(self) -> Optional[Card]:
        if not self.discard:
            return None
        return self.discard.pop()

    def add_to_discard(self, card: Card) -> None:
        self.discard.append(card)

    def recycle_discard_into_stock(self) -> None:
        """When the stock runs dry, reshuffle the discard (keeping the top card)."""
        if len(self.discard) <= 1:
            return
        top = self.discard.pop()
        recycled = self.discard
        self.discard = [top]
        self._rng.shuffle(recycled)
        self.stock = recycled + self.stock

    def stock_count(self) -> int:
        return len(self.stock)
