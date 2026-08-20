"""Teen Patti bot decisions — a direct port of the client's `botAct`/`doSee`
(`teen-patti/web/teen-patti.html`), rewritten as pure functions over an explicit
`random.Random` instead of `Math.random()`.

Each function takes primitive/enum state and an rng, and returns a decision — it never
mutates a hand itself. The caller (the engine's `play_full_hand` for the one-shot REST
path, or the WS table for bot-filled seats) applies the decision by calling the
matching `TeenPattiHand` method. Seeding the rng from the same provably-fair seed as
the deal makes an entire hand — cards *and* every bot decision — reproducible from
(server_seed, client_seed, nonce).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .hand_rank import HandRank


class Action(str, Enum):
    BET = "bet"          # blind or chaal, no raise
    RAISE = "raise"       # blind/chaal at double the current stake
    PACK = "pack"
    SHOW = "show"          # only valid with exactly two active seats
    SIDE_SHOW = "side_show"


@dataclass(frozen=True)
class Decision:
    action: Action
    target_seat: Optional[int] = None  # SIDE_SHOW only


def decide_see(seen: bool, blind_turns: int, rng: random.Random) -> bool:
    if seen:
        return True
    return blind_turns >= 2 or (blind_turns >= 1 and rng.random() < 0.5)


def decide_action(
    *,
    category: HandRank,
    seen: bool,
    active_count: int,
    stake: int,
    cap: int,
    boot: int,
    prev_seen_seat: Optional[int],
    rng: random.Random,
) -> Decision:
    if not seen:
        if stake > boot * 8 and rng.random() < 0.4:
            return Decision(Action.PACK)
        should_raise = stake < cap / 2 and rng.random() < 0.18
        return Decision(Action.RAISE if should_raise else Action.BET)

    if active_count == 2:
        if category >= HandRank.SEQUENCE or (category >= HandRank.PAIR and rng.random() < 0.5):
            return Decision(Action.SHOW)
        if category <= HandRank.HIGH_CARD and rng.random() < 0.6:
            return Decision(Action.PACK)

    if (
        prev_seen_seat is not None
        and active_count > 2
        and category >= HandRank.COLOR
        and rng.random() < 0.22
        and stake < cap / 2
    ):
        return Decision(Action.SIDE_SHOW, target_seat=prev_seen_seat)
    if category <= HandRank.HIGH_CARD and stake > boot * 4 and rng.random() < 0.7:
        return Decision(Action.PACK)
    if category == HandRank.PAIR and stake > boot * 16 and rng.random() < 0.5:
        return Decision(Action.PACK)
    should_raise = category >= HandRank.COLOR and stake < cap / 2 and rng.random() < 0.45
    return Decision(Action.RAISE if should_raise else Action.BET)


def decide_side_show_accept(opponent_category: HandRank, rng: random.Random) -> bool:
    threshold = 0.5 if opponent_category >= HandRank.COLOR else 0.75
    return rng.random() < threshold
