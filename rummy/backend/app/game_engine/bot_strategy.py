"""Basic-strategy decisions for a practice-table bot opponent.

The bot never sees anything a human couldn't: it only ever looks at its own hand,
the wild rank, and the top discard card, all of which are already public/owned
information at that point in the turn. Three decisions, in order of a real turn:

1. `choose_draw_source` — take the top discard card only if it provably lowers
   the hand's minimum deadwood versus drawing blind from stock.
2. `try_find_declare` — after drawing (14 cards), see if 13 of them can be
   partitioned into a legal winning show (>=2 sequences, >=1 pure). Exact-cover
   search, so it only ever proposes declarations `validate_declaration` accepts.
3. `choose_discard` — otherwise, discard whichever card leaves the lowest
   resulting deadwood (ties broken toward shedding the highest-point card).

Deliberately conservative: if the exact-cover search can't find a legal show, the
bot just discards — it never risks the 80-point wrong-declare penalty on a hunch.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import List, Optional

from .cards import ACE, Card
from .scoring import best_hand_score

# Hard cap on partition-search branches explored per declare attempt, so a
# pathological hand can never make the bot's turn hang — it just gives up and
# discards normally instead.
_MAX_SEARCH_NODES = 40_000


def choose_draw_source(hand: List[Card], top_discard: Optional[Card], wild_rank: Optional[int]) -> str:
    if top_discard is None:
        return "stock"
    baseline = best_hand_score(hand, wild_rank)
    with_discard = hand + [top_discard]
    best_after = min(
        best_hand_score([c for c in with_discard if c is not x], wild_rank)
        for x in with_discard
    )
    return "discard" if best_after < baseline else "stock"


def choose_discard(hand: List[Card], wild_rank: Optional[int]) -> str:
    best_card = hand[0]
    best_score: Optional[int] = None
    for c in hand:
        remaining = [x for x in hand if x is not c]
        score = best_hand_score(remaining, wild_rank)
        if (
            best_score is None
            or score < best_score
            or (score == best_score and c.deadwood_points(wild_rank) > best_card.deadwood_points(wild_rank))
        ):
            best_score = score
            best_card = c
    return best_card.code


@dataclass(frozen=True)
class _Candidate:
    mask: int
    joker_need: int
    kind: str        # "set" | "sequence"
    is_pure: bool


def _generate_candidates(naturals: List[Card], joker_count: int) -> List[_Candidate]:
    cands: List[_Candidate] = []

    by_rank: dict[int, list[int]] = {}
    for i, c in enumerate(naturals):
        by_rank.setdefault(c.rank, []).append(i)
    for _rank, idxs in by_rank.items():
        seen_suit: dict = {}
        uniq: List[int] = []
        for i in idxs:
            s = naturals[i].suit
            if s not in seen_suit:
                seen_suit[s] = i
                uniq.append(i)
        for a in range(1, min(4, len(uniq)) + 1):
            for combo in combinations(uniq, a):
                mask = 0
                for i in combo:
                    mask |= 1 << i
                for target in (3, 4):
                    need = target - a
                    if 0 <= need <= joker_count:
                        cands.append(_Candidate(mask, need, kind="set", is_pure=False))

    by_suit: dict = {}
    for i, c in enumerate(naturals):
        by_suit.setdefault(c.suit, []).append(i)
    for _suit, idxs in by_suit.items():
        rank_to_idx: dict[int, int] = {}
        for i in idxs:
            rank_to_idx.setdefault(naturals[i].rank, i)
        rank_variants = [dict(rank_to_idx)]
        if ACE in rank_to_idx:
            high = {(14 if r == ACE else r): i for r, i in rank_to_idx.items()}
            rank_variants.append(high)
        for rv in rank_variants:
            present = sorted(rv.keys())
            if not present:
                continue
            lo_bound, hi_bound = present[0], present[-1]
            for lo in range(lo_bound, hi_bound + 1):
                for hi in range(lo + 2, min(hi_bound, lo + 12) + 1):
                    length = hi - lo + 1
                    inside = [r for r in present if lo <= r <= hi]
                    covered_ranks = len(inside)
                    if covered_ranks == 0:
                        continue
                    need = length - covered_ranks
                    if need < 0 or need > joker_count:
                        continue
                    mask = 0
                    for r in inside:
                        mask |= 1 << rv[r]
                    cands.append(_Candidate(mask, need, kind="sequence", is_pure=(need == 0)))
    return cands


class _SearchExhausted(Exception):
    pass


def _find_partition(naturals: List[Card], joker_count: int, cands: List[_Candidate]) -> Optional[List[_Candidate]]:
    m = len(naturals)
    full_mask = (1 << m) - 1
    by_first: dict[int, list[_Candidate]] = {}
    for cand in cands:
        first = (cand.mask & -cand.mask).bit_length() - 1
        by_first.setdefault(first, []).append(cand)

    nodes = 0

    def rec(used_mask: int, jokers_left: int, seq_count: int, pure_count: int) -> Optional[List[_Candidate]]:
        nonlocal nodes
        nodes += 1
        if nodes > _MAX_SEARCH_NODES:
            raise _SearchExhausted
        if used_mask == full_mask:
            if jokers_left == 0 and seq_count >= 2 and pure_count >= 1:
                return []
            return None
        first = (~used_mask & full_mask)
        first = (first & -first).bit_length() - 1
        for cand in by_first.get(first, ()):
            if cand.mask & used_mask:
                continue
            if cand.joker_need > jokers_left:
                continue
            is_seq = cand.kind == "sequence"
            result = rec(
                used_mask | cand.mask,
                jokers_left - cand.joker_need,
                seq_count + (1 if is_seq else 0),
                pure_count + (1 if cand.is_pure else 0),
            )
            if result is not None:
                return [cand] + result
        return None

    try:
        return rec(0, joker_count, 0, 0)
    except _SearchExhausted:
        return None


def try_find_declare(hand: List[Card], wild_rank: Optional[int]) -> Optional[List[List[str]]]:
    """`hand` is the bot's post-draw 14-card hand. Returns 13-card groups (by card
    code) for a legal declaration, or None if no legal show exists right now."""
    for leftover_idx in range(len(hand)):
        remaining = hand[:leftover_idx] + hand[leftover_idx + 1:]
        naturals = [c for c in remaining if not c.is_wild(wild_rank)]
        jokers = [c for c in remaining if c.is_wild(wild_rank)]
        if not naturals:
            continue  # an all-joker 13 cards can't seat a pure sequence
        cands = _generate_candidates(naturals, len(jokers))
        partition = _find_partition(naturals, len(jokers), cands)
        if partition is None:
            continue
        joker_pool = list(jokers)
        groups: List[List[str]] = []
        for cand in partition:
            codes = [naturals[i].code for i in range(len(naturals)) if (cand.mask >> i) & 1]
            for _ in range(cand.joker_need):
                codes.append(joker_pool.pop().code)
            groups.append(codes)
        return groups
    return None
