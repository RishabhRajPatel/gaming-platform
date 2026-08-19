"""Test helpers: build Card objects from short codes like '5S', 'KH', 'AD', 'PJ'."""
from app.game_engine.cards import Card, Suit

_RANK = {"A": 1, "J": 11, "Q": 12, "K": 13}
_SUIT = {"S": Suit.SPADES, "H": Suit.HEARTS, "D": Suit.DIAMONDS, "C": Suit.CLUBS}


def C(code: str, deck_index: int = 0) -> Card:
    """'5S' -> five of spades, '10H'/'TH' -> ten of hearts, 'PJ' -> printed joker."""
    code = code.upper()
    if code.startswith("PJ"):
        return Card(rank=0, suit=None, printed_joker=True, deck_index=deck_index)
    if code.startswith("10"):
        rank, suit = 10, code[2]
    elif code[0] in _RANK:
        rank, suit = _RANK[code[0]], code[1]
    else:
        rank, suit = int(code[0]), code[1]
    return Card(rank=rank, suit=_SUIT[suit], deck_index=deck_index)


def hand(*codes: str):
    return [C(c) for c in codes]
