"""Meld validation for 13-card Indian Rummy.

A *meld* is a group of cards forming either a **sequence** (run) or a **set**.

Rules implemented (RummyCircle-style, documented in docs/GAME_RULES.md):

* Pure sequence  : 3+ cards, same suit, consecutive ranks, and **no joker at all**
                   (neither a printed joker nor a wild-rank card).
* Impure sequence: 3+ cards, same suit, consecutive ranks where one or more missing
                   positions are substituted by jokers (printed or wild-rank).
* Set            : 3 or 4 cards of the **same rank** with **distinct suits**; jokers
                   may substitute for missing members. Max 4 cards.
* Ace is low (A-2-3) or high (Q-K-A). A-K-2 wrap-around is **not** allowed.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from .cards import ACE, Card


class MeldType(str, Enum):
    PURE_SEQUENCE = "pure_sequence"
    IMPURE_SEQUENCE = "impure_sequence"
    SET = "set"
    INVALID = "invalid"


def _split_jokers(cards: List[Card], wild_rank: Optional[int]):
    jokers = [c for c in cards if c.is_wild(wild_rank)]
    naturals = [c for c in cards if not c.is_wild(wild_rank)]
    return jokers, naturals


def is_pure_sequence(cards: List[Card], wild_rank: Optional[int]) -> bool:
    if len(cards) < 3:
        return False
    # No jokers whatsoever.
    if any(c.is_wild(wild_rank) for c in cards):
        return False
    return _naturals_form_run(cards)


def _naturals_form_run(cards: List[Card]) -> bool:
    """True if these (non-joker) same-suit cards form a gapless consecutive run.

    Handles Ace-high (Q-K-A) by trying Ace as 14 when it helps.
    """
    if len({c.suit for c in cards}) != 1:
        return False
    ranks = sorted(c.rank for c in cards)
    # Duplicate ranks can never form a run.
    if len(set(ranks)) != len(ranks):
        return False
    if _is_consecutive(ranks):
        return True
    # Try Ace as high (14) for a Q-K-A style run.
    if ACE in ranks:
        high = sorted((14 if r == ACE else r) for r in ranks)
        if len(set(high)) == len(high) and _is_consecutive(high):
            return True
    return False


def _is_consecutive(sorted_ranks: List[int]) -> bool:
    return all(
        sorted_ranks[i + 1] - sorted_ranks[i] == 1 for i in range(len(sorted_ranks) - 1)
    )


def is_sequence(cards: List[Card], wild_rank: Optional[int]) -> bool:
    """Pure OR impure sequence."""
    return classify_meld(cards, wild_rank) in (
        MeldType.PURE_SEQUENCE,
        MeldType.IMPURE_SEQUENCE,
    )


def _impure_sequence_ok(naturals: List[Card], joker_count: int) -> bool:
    """Can the naturals + `joker_count` jokers form one same-suit consecutive run?"""
    if not naturals:
        # All jokers — not a valid sequence on its own (needs at least 2 naturals to
        # anchor a run direction; a lone natural + jokers is allowed).
        return False
    if len({c.suit for c in naturals}) != 1:
        return False
    ranks = sorted(c.rank for c in naturals)
    if len(set(ranks)) != len(ranks):
        return False

    def gaps_fillable(rseq: List[int]) -> bool:
        span = rseq[-1] - rseq[0] + 1
        # Jokers needed to fill internal gaps between the outermost naturals.
        internal_missing = span - len(rseq)
        if internal_missing < 0:
            return False
        if internal_missing > joker_count:
            return False
        leftover = joker_count - internal_missing
        total_len = span + leftover  # extend outward with remaining jokers
        # A sequence is at least length 3, and cannot exceed 13 distinct ranks.
        return 3 <= total_len <= 13

    if gaps_fillable(ranks):
        return True
    # Ace-high retry.
    if ACE in ranks:
        high = sorted((14 if r == ACE else r) for r in ranks)
        if len(set(high)) == len(high) and gaps_fillable(high):
            return True
    return False


def _is_set(cards: List[Card], wild_rank: Optional[int]) -> bool:
    n = len(cards)
    if n < 3 or n > 4:
        return False
    jokers, naturals = _split_jokers(cards, wild_rank)
    if not naturals:
        return False
    ranks = {c.rank for c in naturals}
    if len(ranks) != 1:  # all naturals must share one rank
        return False
    suits = [c.suit for c in naturals]
    if len(set(suits)) != len(suits):  # distinct suits, no duplicate suit
        return False
    # naturals + jokers must be <= 4 (already guaranteed by n<=4) and jokers fill rest.
    return len(naturals) + len(jokers) == n <= 4


def classify_meld(cards: List[Card], wild_rank: Optional[int]) -> MeldType:
    """Classify a group of cards into its strongest valid meld type."""
    if len(cards) < 3:
        return MeldType.INVALID
    if is_pure_sequence(cards, wild_rank):
        return MeldType.PURE_SEQUENCE
    jokers, naturals = _split_jokers(cards, wild_rank)
    if _impure_sequence_ok(naturals, len(jokers)):
        return MeldType.IMPURE_SEQUENCE
    if _is_set(cards, wild_rank):
        return MeldType.SET
    return MeldType.INVALID


def is_valid_meld(cards: List[Card], wild_rank: Optional[int]) -> bool:
    return classify_meld(cards, wild_rank) != MeldType.INVALID
