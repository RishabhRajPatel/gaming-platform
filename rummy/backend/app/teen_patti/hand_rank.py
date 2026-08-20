"""Teen Patti hand ranking — a direct Python port of the client's `evalHand`/`cmp`
(`teen-patti/web/teen-patti.html`), kept in exact agreement with the JS so a replayed
hand's category names and ordering never disagree between server and browser.

Ranking (highest first): Trail > Pure Sequence (A-2-3 ranks just below K-Q-J, same as
the client) > Sequence > Color > Pair > High Card.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import List, Tuple

from .cards import Card

_RANK_LABEL = {14: "A", 13: "K", 12: "Q", 11: "J"}


def rank_label(rank: int) -> str:
    return _RANK_LABEL.get(rank, str(rank))


class HandRank(IntEnum):
    HIGH_CARD = 1
    PAIR = 2
    COLOR = 3
    SEQUENCE = 4
    PURE_SEQUENCE = 5
    TRAIL = 6


@dataclass(frozen=True)
class HandResult:
    category: HandRank
    tiebreak: Tuple[float, ...]
    name: str


def classify_hand(cards: List[Card]) -> HandResult:
    if len(cards) != 3:
        raise ValueError("a Teen Patti hand is exactly 3 cards")
    rs = sorted((c.rank for c in cards), reverse=True)
    flush = cards[0].suit == cards[1].suit == cards[2].suit
    uniq = len(set(rs)) == 3
    seq = False
    top: float = rs[0]
    if uniq:
        if rs[0] - rs[1] == 1 and rs[1] - rs[2] == 1:
            seq = True
            top = rs[0]
        elif rs[0] == 14 and rs[1] == 3 and rs[2] == 2:
            seq = True
            top = 13.5  # A-2-3: second-best pure sequence, ranks just below K-Q-J

    if rs[0] == rs[1] == rs[2]:
        return HandResult(HandRank.TRAIL, (HandRank.TRAIL, rs[0]), f"Trail {rank_label(rs[0])}")
    if seq and flush:
        return HandResult(HandRank.PURE_SEQUENCE, (HandRank.PURE_SEQUENCE, top), "Pure Sequence")
    if seq:
        return HandResult(HandRank.SEQUENCE, (HandRank.SEQUENCE, top), "Sequence")
    if flush:
        return HandResult(HandRank.COLOR, (HandRank.COLOR, *rs), "Color")
    if rs[0] == rs[1] or rs[1] == rs[2]:
        pair_rank = rs[1]
        kicker = rs[2] if rs[0] == rs[1] else rs[0]
        return HandResult(HandRank.PAIR, (HandRank.PAIR, pair_rank, kicker), f"Pair {rank_label(pair_rank)}")
    return HandResult(HandRank.HIGH_CARD, (HandRank.HIGH_CARD, *rs), f"High {rank_label(rs[0])}")


def category_of(cards: List[Card]) -> HandRank:
    return classify_hand(cards).category


def compare_hands(a: List[Card], b: List[Card]) -> int:
    """>0 if `a` beats `b`, <0 if `b` beats `a`, 0 for an exact tie."""
    ta, tb = classify_hand(a).tiebreak, classify_hand(b).tiebreak
    for i in range(max(len(ta), len(tb))):
        x = ta[i] if i < len(ta) else 0
        y = tb[i] if i < len(tb) else 0
        if x != y:
            return 1 if x > y else -1
    return 0
