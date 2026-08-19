"""Declaration validation and hand scoring for Deals Rummy.

Two responsibilities:

1. `validate_declaration` — the winner submits an explicit grouping of their 13 cards.
   A valid declaration needs every group to be a valid meld, at least two sequences,
   and at least one of those a **pure** sequence.

2. `best_hand_score` — for a losing player we auto-arrange their hand to the lowest
   possible deadwood total. Standard rule: you may only deduct melds if you hold at
   least one pure sequence; otherwise the whole hand counts. Scores are capped at 80.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import List, Optional

from .cards import ACE, Card, rank_points
from .melds import MeldType, classify_meld

MAX_HAND_POINTS = 80
WRONG_DECLARE_POINTS = 80
FIRST_DROP_POINTS = 20
MIDDLE_DROP_POINTS = 40
HAND_SIZE = 13


@dataclass
class DeclarationResult:
    valid: bool
    reason: str = "ok"
    points: int = 0
    meld_types: List[MeldType] = field(default_factory=list)


def validate_declaration(
    groups: List[List[Card]], wild_rank: Optional[int]
) -> DeclarationResult:
    """Validate a winner's explicit grouping of all 13 cards."""
    total = sum(len(g) for g in groups)
    if total != HAND_SIZE:
        return DeclarationResult(
            False, f"declaration must use all {HAND_SIZE} cards (got {total})",
            points=WRONG_DECLARE_POINTS,
        )

    meld_types: List[MeldType] = []
    for g in groups:
        mt = classify_meld(g, wild_rank)
        if mt == MeldType.INVALID:
            return DeclarationResult(
                False, "one or more groups is not a valid meld",
                points=WRONG_DECLARE_POINTS, meld_types=meld_types,
            )
        meld_types.append(mt)

    sequences = [
        m for m in meld_types
        if m in (MeldType.PURE_SEQUENCE, MeldType.IMPURE_SEQUENCE)
    ]
    pure = [m for m in meld_types if m == MeldType.PURE_SEQUENCE]

    if len(sequences) < 2:
        return DeclarationResult(
            False, "need at least two sequences",
            points=WRONG_DECLARE_POINTS, meld_types=meld_types,
        )
    if len(pure) < 1:
        return DeclarationResult(
            False, "need at least one pure sequence",
            points=WRONG_DECLARE_POINTS, meld_types=meld_types,
        )
    return DeclarationResult(True, "ok", points=0, meld_types=meld_types)


# --------------------------------------------------------------------------------------
# Auto-arrangement scorer for losing hands.
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class _Candidate:
    mask: int          # bitmask over natural-card indices this meld covers
    joker_need: int    # jokers consumed
    covered: int       # deadwood points of the naturals covered
    is_pure: bool


def _generate_candidates(naturals: List[Card], joker_count: int) -> List[_Candidate]:
    cands: List[_Candidate] = []

    # ---- Sets: same rank, distinct suits (+ jokers) --------------------------------
    by_rank: dict[int, list[int]] = {}
    for i, c in enumerate(naturals):
        by_rank.setdefault(c.rank, []).append(i)
    for rank, idxs in by_rank.items():
        # keep at most one card per suit (a set needs distinct suits)
        seen_suit: dict = {}
        uniq: List[int] = []
        for i in idxs:
            s = naturals[i].suit
            if s not in seen_suit:
                seen_suit[s] = i
                uniq.append(i)
        pts = rank_points(rank)
        from itertools import combinations
        for a in range(1, min(4, len(uniq)) + 1):
            for combo in combinations(uniq, a):
                mask = 0
                for i in combo:
                    mask |= 1 << i
                for target in (3, 4):
                    need = target - a
                    if 0 <= need <= joker_count and a <= target:
                        cands.append(_Candidate(mask, need, a * pts, is_pure=False))

    # ---- Sequences: same suit, consecutive (+ jokers) ------------------------------
    by_suit: dict = {}
    for i, c in enumerate(naturals):
        by_suit.setdefault(c.suit, []).append(i)
    for suit, idxs in by_suit.items():
        # rank -> index (dedupe duplicate ranks within a suit; a run uses each rank once)
        rank_to_idx: dict[int, int] = {}
        for i in idxs:
            rank_to_idx.setdefault(naturals[i].rank, i)
        # Represent ace both low(1) and high(14).
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
                    covered_pts = 0
                    for r in inside:
                        i = rv[r]
                        mask |= 1 << i
                        covered_pts += rank_points(naturals[i].rank)
                    cands.append(
                        _Candidate(mask, need, covered_pts, is_pure=(need == 0))
                    )
    return cands


def best_hand_score(cards: List[Card], wild_rank: Optional[int]) -> int:
    """Minimum deadwood points for a hand, capped at 80.

    Deductions only apply when at least one pure sequence can be formed; otherwise the
    full natural-card count applies.
    """
    naturals = [c for c in cards if not c.is_wild(wild_rank)]
    joker_count = len(cards) - len(naturals)
    total_natural = sum(rank_points(c.rank) for c in naturals)
    if total_natural == 0:
        return 0

    cands = _generate_candidates(naturals, joker_count)

    # Group candidates by the lowest-index natural they cover, for fast recursion.
    m = len(naturals)

    @lru_cache(maxsize=None)
    def max_covered(used_mask: int, jokers: int) -> int:
        # first uncovered natural
        first = -1
        for i in range(m):
            if not (used_mask >> i) & 1:
                first = i
                break
        if first == -1:
            return 0
        # option 1: leave `first` as deadwood
        best = max_covered(used_mask | (1 << first), jokers)
        # option 2: use a candidate that covers `first`
        for cand in cands:
            if not (cand.mask >> first) & 1:
                continue
            if cand.mask & used_mask:
                continue
            if cand.joker_need > jokers:
                continue
            best = max(
                best,
                cand.covered + max_covered(used_mask | cand.mask, jokers - cand.joker_need),
            )
        return best

    # Require at least one pure sequence to unlock any deduction.
    best_with_pure = -1
    for p in cands:
        if not p.is_pure:
            continue
        if p.joker_need > joker_count:
            continue
        covered = p.covered + max_covered(p.mask, joker_count - p.joker_need)
        best_with_pure = max(best_with_pure, covered)

    if best_with_pure < 0:
        deadwood = total_natural  # no pure sequence → full count
    else:
        deadwood = total_natural - best_with_pure

    max_covered.cache_clear()
    return min(deadwood, MAX_HAND_POINTS)
