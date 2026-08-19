from app.game_engine.melds import MeldType, classify_meld, is_pure_sequence
from tests.helpers import hand

NO_WILD = None


def test_pure_sequence_basic():
    assert is_pure_sequence(hand("4S", "5S", "6S"), NO_WILD)
    assert classify_meld(hand("4S", "5S", "6S"), NO_WILD) == MeldType.PURE_SEQUENCE


def test_pure_sequence_ace_low_and_high():
    assert is_pure_sequence(hand("AH", "2H", "3H"), NO_WILD)      # A-2-3
    assert is_pure_sequence(hand("QC", "KC", "AC"), NO_WILD)      # Q-K-A


def test_ace_wraparound_is_invalid():
    assert not is_pure_sequence(hand("KD", "AD", "2D"), NO_WILD)  # K-A-2 not allowed


def test_pure_sequence_rejects_offsuit_and_gaps():
    assert not is_pure_sequence(hand("4S", "5H", "6S"), NO_WILD)
    assert not is_pure_sequence(hand("4S", "6S", "7S"), NO_WILD)


def test_printed_joker_makes_impure():
    m = classify_meld(hand("4S", "PJ", "6S"), NO_WILD)
    assert m == MeldType.IMPURE_SEQUENCE


def test_wild_rank_card_is_joker_not_pure():
    # 7 is wild this deal; a spade run using a 7 is impure, not pure
    cards = hand("6S", "7S", "8S")
    assert classify_meld(cards, wild_rank=7) == MeldType.IMPURE_SEQUENCE


def test_valid_set_three_and_four():
    assert classify_meld(hand("9S", "9H", "9D"), NO_WILD) == MeldType.SET
    assert classify_meld(hand("9S", "9H", "9D", "9C"), NO_WILD) == MeldType.SET


def test_set_rejects_duplicate_suit():
    assert classify_meld(hand("9S", "9S", "9D"), NO_WILD) == MeldType.INVALID


def test_set_with_joker():
    assert classify_meld(hand("9S", "9H", "PJ"), NO_WILD) == MeldType.SET


def test_five_card_set_invalid():
    assert classify_meld(hand("9S", "9H", "9D", "9C", "PJ"), NO_WILD) == MeldType.INVALID
