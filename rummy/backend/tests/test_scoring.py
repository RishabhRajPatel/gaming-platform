from app.game_engine.scoring import (
    WRONG_DECLARE_POINTS,
    best_hand_score,
    validate_declaration,
)
from tests.helpers import hand

NO_WILD = None


def _winning_groups():
    # 13 cards: pure(3) + pure(3) + set(3) + set(4)
    return [
        hand("4S", "5S", "6S"),       # pure sequence
        hand("7H", "8H", "9H"),       # pure sequence
        hand("2C", "2D", "2S"),       # set
        hand("KC", "KD", "KH", "KS"), # set
    ]


def test_valid_declaration():
    res = validate_declaration(_winning_groups(), NO_WILD)
    assert res.valid
    assert res.points == 0


def test_declaration_needs_pure_sequence():
    groups = [
        hand("4S", "PJ", "6S"),       # impure
        hand("7H", "8H", "9H"),       # pure -> actually pure; swap to make no pure
    ]
    # force: two impure sequences + sets, no pure
    groups = [
        hand("4S", "PJ", "6S"),        # impure seq
        hand("9H", "PJ", "JH"),        # impure seq (9-10-J with joker)
        hand("2C", "2D", "2S"),        # set
        hand("KC", "KD", "KH", "KS"),  # set
    ]
    res = validate_declaration(groups, NO_WILD)
    assert not res.valid
    assert res.points == WRONG_DECLARE_POINTS


def test_declaration_wrong_card_count():
    groups = [hand("4S", "5S", "6S")]  # only 3 cards
    res = validate_declaration(groups, NO_WILD)
    assert not res.valid


def test_best_score_full_count_no_pure_sequence():
    # distinct ranks with strictly alternating suits: no run of 3 same-suit, no sets,
    # so no pure sequence is possible -> whole hand counts, capped at 80.
    h = hand("AS", "2H", "3S", "4H", "5S", "6H", "7S", "8H", "9S", "10H", "JS", "QH", "KS")
    score = best_hand_score(h, NO_WILD)
    assert score == 80  # capped


def test_best_score_deducts_with_pure_sequence():
    # pure run 4-5-6 spades (deducted) + deadwood K,Q = 20
    h = hand("4S", "5S", "6S", "KH", "QD")
    assert best_hand_score(h, NO_WILD) == 20


def test_best_score_jokers_are_zero_deadwood():
    h = hand("4S", "5S", "6S", "PJ", "KH")
    # pure run deducted, joker=0, K=10
    assert best_hand_score(h, NO_WILD) == 10


def test_best_score_zero_for_complete_hand():
    cards = []
    for g in _winning_groups():
        cards.extend(g)
    assert best_hand_score(cards, NO_WILD) == 0
